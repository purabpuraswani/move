import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { calculateLiveMoveWellScore } from '../orchestrator/workflowOrchestrator.js';

const DEFAULT_MODEL = process.env.OPENROUTER_MODEL || 'openai/gpt-4o-mini';

const logSleepTool = {
  type: 'function',
  function: {
    name: 'log_sleep_record',
    description: 'Saves a daily sleep and recovery log for the user into the MoveWell SQLite database. Call this whenever the user shares information about how long they slept, their sleep quality, stress levels, or how rested they feel.',
    parameters: {
      type: 'object',
      properties: {
        sleep_duration: {
          type: 'number',
          description: 'Hours of sleep (e.g. 7.5, 6, 8.2)'
        },
        sleep_quality: {
          type: 'string',
          enum: ['POOR', 'FAIR', 'GOOD', 'EXCELLENT'],
          description: 'Subjective quality of sleep'
        },
        stress_level: {
          type: 'integer',
          description: 'ONLY set this if the user EXPLICITLY stated a numeric stress rating from 1 to 10 (e.g. "my stress is 7", "rated a 4"). NEVER guess, estimate, or assume a number. If the user mentions stress without giving a specific number, omit this parameter.'
        },
        recovery_notes: {
          type: 'string',
          description: 'Contextual notes about sleep interruptions, fatigue, soreness, or stressors'
        },
        record_date: {
          type: 'string',
          description: 'Date in YYYY-MM-DD format (defaults to today if omitted)'
        }
      },
      required: ['sleep_duration', 'sleep_quality']
    }
  }
};

export async function handleRecoveryVoiceConversation(userId, message, conversationHistory = []) {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    return {
      reply: "I'm your MoveWell Recovery Coach! To chat with me and auto-log your sleep using OpenRouter, please add your OPENROUTER_API_KEY to the server/.env file.",
      loggedRecord: null,
      needsApiKey: true
    };
  }

  let model = process.env.OPENROUTER_MODEL || DEFAULT_MODEL;
  if (model === 'openai/o4-mini' || model === 'o4-mini' || model === 'gpt-4o-mini') {
    model = 'openai/gpt-4o-mini';
  }

  const db = getDb();

  // 1. Fetch user context
  const user = db.prepare('SELECT name FROM users WHERE id = ?').get(userId);
  const profile = db.prepare('SELECT sleep_hours, sleep_quality, stress_level FROM user_profiles WHERE user_id = ?').get(userId);
  const recentRecords = db.prepare('SELECT sleep_duration, sleep_quality, stress_level, record_date FROM sleep_records WHERE user_id = ? ORDER BY record_date DESC LIMIT 5').all(userId);
  const latestPlan = db.prepare('SELECT id FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1').get(userId);
  
  let planActivities = [];
  if (latestPlan) {
    planActivities = db.prepare("SELECT activity_title, time_block, completion_status FROM plan_activities WHERE plan_id = ? AND specialist_name = 'WELLNESS_RECOVERY'").all(latestPlan.id);
  }

  const systemInstruction = `
You are the MoveWell AI Wellness & Recovery Specialist and personal voice coach for ${user?.name || 'the user'}.
Your clinical focus is sleep hygiene, central nervous system (CNS) restoration, circadian rhythm alignment, and stress regulation.

Current User Context:
- Target Sleep: ${profile?.sleep_hours || 7.5} hours
- Baseline Sleep Quality: ${profile?.sleep_quality || 'Unknown'}
- Recent Sleep Logs: ${recentRecords.length > 0 ? JSON.stringify(recentRecords) : 'None logged yet'}
- Scheduled Recovery Plan: ${JSON.stringify(planActivities)}

CRITICAL Clinical Stress Protocol (Zero Guesswork):
- NEVER assume, estimate, or invent a numerical stress rating (1 to 10).
- If the user mentions stress, work pressure, anxiety, or feeling overwhelmed, BUT did NOT provide a specific number from 1 to 10:
  1. Do NOT set 'stress_level' in the tool call.
  2. In your spoken reply, acknowledge their stress empathetically and explicitly ask them: "On a scale of 1 to 10, how would you rate your stress today?"
- ONLY record a 'stress_level' when the user explicitly provides a number (e.g., "it's a 7", "about 5", "stress is 8").
- If the user provides sleep hours without mentioning stress, you may also casually ask how their stress or energy levels are feeling.

Your Capabilities:
1. Normal Conversation: You can have natural, warm, empathetic, and scientifically grounded conversations about sleep science, fatigue, stress reduction, bedtime routines, breathing pacing, and readiness for physical exercise.
2. Auto-Logging: Whenever the user shares their sleep duration and quality, call the 'log_sleep_record' tool. Include 'stress_level' ONLY if they gave a clear number (1-10); otherwise ask them for the number.
3. Conversational Style: Keep your responses warm, concise, and easy to listen to when spoken aloud (1-2 sentences per turn). Avoid robotic bulleted lists or markdown tables unless specifically requested.
`;

  // Build OpenAI-compatible messages array
  const messages = [
    { role: 'system', content: systemInstruction }
  ];

  for (const turn of conversationHistory) {
    if (turn.content) {
      messages.push({
        role: turn.role === 'model' || turn.role === 'assistant' ? 'assistant' : 'user',
        content: turn.content
      });
    }
  }

  // Ensure message is not duplicated if already last turn
  const lastTurn = messages[messages.length - 1];
  if (!lastTurn || lastTurn.role !== 'user' || lastTurn.content !== message) {
    messages.push({
      role: 'user',
      content: message
    });
  }

  try {
    const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey.trim()}`,
        'HTTP-Referer': 'http://localhost:5173',
        'X-Title': 'MoveWell AI Recovery Coach',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model,
        messages,
        max_tokens: 500,
        tools: [logSleepTool]
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`OpenRouter error (${response.status}): ${errorText}`);
    }

    const data = await response.json();
    const choice = data.choices?.[0];
    const messageObj = choice?.message;

    if (!messageObj) {
      throw new Error('No message returned from OpenRouter.');
    }

    let loggedRecord = null;
    let updatedScore = null;

    // Check if user or previous turn explicitly mentioned a stress number
    const mentionsStressQualitatively = /(stress|pressure|tense|anxious|overwhelm|frustrat|burden)/i.test(message);
    const previousAskedForStress = conversationHistory.some(turn =>
      (turn.role === 'model' || turn.role === 'assistant') &&
      turn.content &&
      /(scale of 1 to 10|rate your stress|stress.*10)/i.test(turn.content)
    );
    const mentionsStressNumber = previousAskedForStress ||
      /\b([0-9]|10)\s*(\/|\s*out of\s*)?\s*10\b|\bstress\D*?([0-9]|10)\b|\b([0-9]|10)\D*?stress\b|\b(level|rate|rating|at|is|a|around|about|maybe|probably)\s*([0-9]|10)\b/i.test(message) ||
      (/\b([1-9]|10)\b/.test(message) && mentionsStressQualitatively);

    // Check if OpenRouter model called any tools
    if (messageObj.tool_calls && messageObj.tool_calls.length > 0) {
      messages.push(messageObj);

      for (const toolCall of messageObj.tool_calls) {
        if (toolCall.function?.name === 'log_sleep_record') {
          let args = {};
          try {
            args = typeof toolCall.function.arguments === 'string'
              ? JSON.parse(toolCall.function.arguments)
              : (toolCall.function.arguments || {});
          } catch {
            args = {};
          }

          const duration = Math.max(1, Math.min(24, parseFloat(args.sleep_duration) || 7.0));

          let quality = (args.sleep_quality || 'GOOD').toUpperCase();
          if (!['POOR', 'FAIR', 'GOOD', 'EXCELLENT'].includes(quality)) {
            if (quality.includes('POOR') || quality.includes('BAD')) quality = 'POOR';
            else if (quality.includes('EXCELLENT') || quality.includes('GREAT')) quality = 'EXCELLENT';
            else if (quality.includes('FAIR') || quality.includes('OK') || quality.includes('MODERATE')) quality = 'FAIR';
            else quality = 'GOOD';
          }

          // Anti-guess safeguard: Only record stress if user provided a number
          const parsedStress = Number(args.stress_level);
          const hasValidNumber = Number.isFinite(parsedStress) && parsedStress >= 1 && parsedStress <= 10;
          const stress = (hasValidNumber && mentionsStressNumber) ? Math.round(parsedStress) : null;

          const notes = args.recovery_notes || 'Logged via OpenRouter Voice Coach';
          const date = args.record_date || new Date().toISOString().substring(0, 10);
          const recordId = uuidv4();

          db.prepare(`
            INSERT INTO sleep_records (id, user_id, sleep_duration, sleep_quality, stress_level, recovery_notes, record_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
          `).run(recordId, userId, duration, quality, stress, notes, date);

          db.prepare(`
            UPDATE user_profiles 
            SET sleep_hours = ?, sleep_quality = ?, stress_level = coalesce(?, stress_level), updated_at = datetime('now')
            WHERE user_id = ?
          `).run(duration, quality, stress, userId);

          const liveScore = calculateLiveMoveWellScore(userId);
          updatedScore = liveScore.overall_score;

          loggedRecord = {
            id: recordId,
            sleep_duration: duration,
            sleep_quality: quality,
            stress_level: stress,
            recovery_notes: notes,
            record_date: date
          };

          const followUpInstruction = (mentionsStressQualitatively && !mentionsStressNumber)
            ? `Logged ${duration} hours (${quality} quality) into SQLite database. The user mentioned stress but did NOT give a 1-10 number. In your reply, confirm the sleep was logged and explicitly ask them: "On a scale of 1 to 10, how would you rate your stress today?"`
            : `Logged ${duration} hours (${quality} quality) with stress level ${stress ?? 'not reported'} into SQLite database. Current MoveWell score: ${updatedScore}.`;

          messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            content: JSON.stringify({
              success: true,
              message: followUpInstruction
            })
          });
        } else {
          messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            content: JSON.stringify({ success: true })
          });
        }
      }

      // Second turn: model produces conversational reply
      try {
        const followUpRes = await fetch('https://openrouter.ai/api/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${apiKey.trim()}`,
            'HTTP-Referer': 'http://localhost:5173',
            'X-Title': 'MoveWell AI Recovery Coach',
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            model,
            messages,
            max_tokens: 500
          })
        });

        if (followUpRes.ok) {
          const followUpData = await followUpRes.json();
          let secondReply = followUpData.choices?.[0]?.message?.content;
          if (secondReply) {
            // Ensure the question about 1-10 scale is present if user mentioned stress without rating
            if (mentionsStressQualitatively && !mentionsStressNumber && !secondReply.includes('10')) {
              secondReply += " On a scale of 1 to 10, how would you rate your stress today?";
            }
            return {
              reply: secondReply,
              loggedRecord,
              updatedScore,
              modelUsed: model
            };
          }
        }
      } catch (fErr) {
        console.warn('Follow-up completion notice:', fErr);
      }

      let fallbackReply = `I've logged your ${loggedRecord.sleep_duration} hours of sleep (${loggedRecord.sleep_quality} quality) into your MoveWell records!`;
      if (mentionsStressQualitatively && !mentionsStressNumber) {
        fallbackReply += " On a scale of 1 to 10, how would you rate that work stress today?";
      } else {
        fallbackReply += " How are your energy levels feeling today?";
      }

      return {
        reply: fallbackReply,
        loggedRecord,
        updatedScore,
        modelUsed: model
      };
    }

    // No tool was called: if user mentioned stress, make sure the model asks for rating
    let textReply = messageObj.content || "I'm here to support your recovery. How can I help you today?";
    if (mentionsStressQualitatively && !mentionsStressNumber && !textReply.includes('10')) {
      textReply += " On a scale of 1 to 10, how would you rate your stress today?";
    }

    return {
      reply: textReply,
      loggedRecord: null,
      updatedScore: null,
      modelUsed: model
    };
  } catch (err) {
    console.error('Error in recovery voice agent conversation:', err);
    return {
      reply: `I encountered an issue connecting to OpenRouter: ${err.message}. Please check your OPENROUTER_API_KEY.`,
      error: err.message
    };
  }
}
