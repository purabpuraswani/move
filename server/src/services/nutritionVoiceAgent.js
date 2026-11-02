import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { calculateLiveMoveWellScore } from '../orchestrator/workflowOrchestrator.js';

const DEFAULT_MODEL = process.env.OPENROUTER_MODEL || 'openai/gpt-4o-mini';

const nutritionTools = [
  {
    type: 'function',
    function: {
      name: 'log_meal',
      description: 'Logs a meal or snack the user has eaten into the MoveWell SQLite database. Call this whenever the user shares what they ate.',
      parameters: {
        type: 'object',
        properties: {
          meal_type: {
            type: 'string',
            enum: ['BREAKFAST', 'LUNCH', 'DINNER', 'SNACK'],
            description: 'Type of meal'
          },
          food_description: {
            type: 'string',
            description: 'Clear description of the food/drink consumed (e.g. "Oatmeal with berries and protein shake", "Grilled chicken salad")'
          },
          portion: {
            type: 'string',
            description: 'Portion estimate (e.g. "1 bowl", "1 plate", "2 slices")'
          },
          calories_optional: {
            type: 'integer',
            description: 'Estimated calories if mentioned or reasonably inferable'
          },
          notes: {
            type: 'string',
            description: 'Nutritional notes (e.g. high protein, anti-inflammatory, feeling energetic)'
          }
        },
        required: ['meal_type', 'food_description']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'schedule_full_day_meal_plan',
      description: 'Prepares and saves a full-day scheduled meal plan (Breakfast, Lunch, Dinner, Snacks) into the user\'s active Daily Health Plan in SQLite. Call this whenever the user asks to prepare, plan, schedule, or recommend their meals for the day.',
      parameters: {
        type: 'object',
        properties: {
          plan_summary: {
            type: 'string',
            description: 'Brief overview of the day\'s nutritional focus (e.g. "High-Protein Anti-Inflammatory Recovery Day")'
          },
          meals: {
            type: 'array',
            description: 'The scheduled meals across the day',
            items: {
              type: 'object',
              properties: {
                meal_type: {
                  type: 'string',
                  enum: ['BREAKFAST', 'LUNCH', 'DINNER', 'SNACK'],
                  description: 'Category of meal'
                },
                time_block: {
                  type: 'string',
                  enum: ['MORNING', 'AFTERNOON', 'EVENING'],
                  description: 'Schedule block for the meal'
                },
                title: {
                  type: 'string',
                  description: 'Short enticing recipe or meal title (e.g. "Protein Oatmeal with Blueberries")'
                },
                description: {
                  type: 'string',
                  description: 'Nutritional benefit or macro summary (e.g. "Complex carbohydrates & antioxidant recovery")'
                },
                instructions: {
                  type: 'string',
                  description: 'Specific recipe components, ingredients, or preparation steps'
                },
                dosage: {
                  type: 'string',
                  description: 'Macro & calorie estimates (e.g. "~450 kcal, 30g protein")'
                },
                caution: {
                  type: 'string',
                  description: 'Allergy or restriction notes (e.g. "Gluten-free as per profile")'
                }
              },
              required: ['meal_type', 'time_block', 'title', 'instructions']
            }
          }
        },
        required: ['meals']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'log_water_intake',
      description: 'Updates daily hydration volume in liters for the user.',
      parameters: {
        type: 'object',
        properties: {
          water_liters: {
            type: 'number',
            description: 'Total daily water intake in liters (e.g. 2.0, 2.5)'
          }
        },
        required: ['water_liters']
      }
    }
  }
];

export async function handleNutritionVoiceConversation(userId, message, conversationHistory = []) {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    return {
      reply: "I'm your MoveWell Nutrition Specialist! To chat and prepare your meal schedules with OpenRouter, please add your OPENROUTER_API_KEY to the server/.env file.",
      loggedMeal: null,
      scheduledPlan: null,
      needsApiKey: true
    };
  }

  let model = process.env.OPENROUTER_MODEL || DEFAULT_MODEL;
  if (model === 'openai/o4-mini' || model === 'o4-mini' || model === 'gpt-4o-mini') {
    model = 'openai/gpt-4o-mini';
  }

  const db = getDb();

  // Gather user nutritional context
  const user = db.prepare('SELECT name FROM users WHERE id = ?').get(userId);
  const profile = db.prepare('SELECT water_intake_liters, fruit_veg_servings, food_preferences, food_restrictions, allergies, nutrition_goals FROM user_profiles WHERE user_id = ?').get(userId);
  const recentMeals = db.prepare('SELECT meal_type, food_description, portion, logged_at FROM meal_logs WHERE user_id = ? ORDER BY logged_at DESC LIMIT 6').all(userId);
  const latestPlan = db.prepare('SELECT id FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1').get(userId);
  let activePlanMeals = [];
  if (latestPlan) {
    activePlanMeals = db.prepare("SELECT activity_title, time_block, completion_status FROM plan_activities WHERE plan_id = ? AND specialist_name = 'NUTRITION'").all(latestPlan.id);
  }

  const systemInstruction = `
You are the MoveWell AI Nutrition & Metabolic Health Specialist and personal voice coach for ${user?.name || 'the user'}.
Your clinical focus is nutrient density, anti-inflammatory protocols, tissue repair support, metabolic balance, and hydration.

Current User Profile:
- Dietary Restrictions: ${profile?.food_restrictions || 'None'}
- Allergies: ${profile?.allergies || 'None'}
- Food Preferences: ${profile?.food_preferences || 'Whole food focus'}
- Nutrition Goals: ${profile?.nutrition_goals || 'Energy, muscle recovery & wellness'}
- Reported Daily Water: ${profile?.water_intake_liters || 2.0} L
- Recent Meals Logged: ${recentMeals.length > 0 ? JSON.stringify(recentMeals) : 'None recently'}
- Current Scheduled Meal Routine: ${JSON.stringify(activePlanMeals)}

Your Capabilities:
1. Prepare Full-Day Meal Schedules: When the user asks to plan, prepare, schedule, or recommend their meals for the day, ALWAYS use the 'schedule_full_day_meal_plan' tool with 3-4 structured meals (Breakfast, Lunch, Dinner, Snack) tailored to their allergies and dietary restrictions.
2. Auto-Logging Meals: When the user tells you what they ate (e.g. "I had eggs and toast for breakfast"), use the 'log_meal' tool to persist it immediately.
3. Hydration Logging: When the user mentions water intake, use 'log_water_intake'.
4. Normal Conversational Guidance: You can freely discuss macro ratios, meal timing, hydration strategies, anti-inflammatory foods for tendon/muscle healing, and recipe suggestions.
5. Conversational Style: Keep your spoken responses warm, energizing, and concise (1-2 sentences per turn). Avoid long unformatted blocks that sound awkward when spoken aloud.
`;

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
        'X-Title': 'MoveWell AI Nutrition Specialist',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model,
        messages,
        max_tokens: 600,
        tools: nutritionTools
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
      throw new Error('No response from OpenRouter.');
    }

    let loggedMeal = null;
    let scheduledPlan = null;
    let loggedWater = null;

    if (messageObj.tool_calls && messageObj.tool_calls.length > 0) {
      messages.push(messageObj);

      for (const toolCall of messageObj.tool_calls) {
        let args = {};
        try {
          args = typeof toolCall.function.arguments === 'string'
            ? JSON.parse(toolCall.function.arguments)
            : (toolCall.function.arguments || {});
        } catch {
          args = {};
        }

        if (toolCall.function?.name === 'log_meal') {
          const mealId = uuidv4();
          const mealType = (args.meal_type || 'LUNCH').toUpperCase();
          const foodDesc = args.food_description || 'Balanced meal';
          const portion = args.portion || '1 standard portion';
          const calories = args.calories_optional ? parseInt(args.calories_optional) : null;
          const notes = args.notes || 'Logged via Voice Nutrition Coach';

          db.prepare(`
            INSERT INTO meal_logs (id, user_id, meal_type, food_description, portion, calories_optional, notes, logged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
          `).run(mealId, userId, mealType, foodDesc, portion, calories, notes);

          loggedMeal = {
            id: mealId,
            meal_type: mealType,
            food_description: foodDesc,
            portion,
            calories_optional: calories
          };

          messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            content: JSON.stringify({
              success: true,
              message: `Logged ${mealType}: ${foodDesc} to SQLite meal_logs.`
            })
          });
        } else if (toolCall.function?.name === 'schedule_full_day_meal_plan') {
          const rawMeals = Array.isArray(args.meals) ? args.meals : [];
          
          let plan = db.prepare('SELECT id FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1').get(userId);
          if (!plan) {
            const planId = uuidv4();
            db.prepare(`
              INSERT INTO health_plans (id, user_id, workflow_id, plan_date, summary, overall_score)
              VALUES (?, ?, ?, date('now'), 'MoveWell Personal Health Plan', 60)
            `).run(planId, userId, uuidv4());
            plan = { id: planId };
          }

          // Clear existing nutrition activities in the plan and replace with the scheduled meals
          db.prepare("DELETE FROM plan_activities WHERE plan_id = ? AND specialist_name = 'NUTRITION'").run(plan.id);

          const insertActivity = db.prepare(`
            INSERT INTO plan_activities (id, plan_id, specialist_name, activity_title, description, instructions, time_block, dosage, caution, activity_type, completion_status)
            VALUES (?, ?, 'NUTRITION', ?, ?, ?, ?, ?, ?, 'NUTRITION', 'PENDING')
          `);

          const savedMeals = [];
          for (const m of rawMeals) {
            const actId = uuidv4();
            const timeBlock = ['MORNING', 'AFTERNOON', 'EVENING'].includes(m.time_block) ? m.time_block : 'MORNING';
            insertActivity.run(
              actId,
              plan.id,
              m.title || `${m.meal_type || 'Nutritious'} Meal`,
              m.description || 'Structured balanced meal plan',
              m.instructions || null,
              timeBlock,
              m.dosage || null,
              m.caution || null
            );
            savedMeals.push({
              id: actId,
              title: m.title,
              time_block: timeBlock,
              meal_type: m.meal_type,
              instructions: m.instructions,
              dosage: m.dosage
            });
          }

          scheduledPlan = {
            plan_id: plan.id,
            summary: args.plan_summary || 'Full Day Scheduled Meal Plan',
            meals: savedMeals
          };

          messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            content: JSON.stringify({
              success: true,
              message: `Saved ${savedMeals.length} scheduled meals into active Daily Health Plan.`
            })
          });
        } else if (toolCall.function?.name === 'log_water_intake') {
          const liters = parseFloat(args.water_liters) || 2.0;
          db.prepare('UPDATE user_profiles SET water_intake_liters = ?, updated_at = datetime(\'now\') WHERE user_id = ?').run(liters, userId);
          loggedWater = liters;
          messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            content: JSON.stringify({ success: true, message: `Updated water intake to ${liters}L.` })
          });
        } else {
          messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            content: JSON.stringify({ success: true })
          });
        }
      }

      // Second turn: model provides spoken response
      try {
        const followUpRes = await fetch('https://openrouter.ai/api/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${apiKey.trim()}`,
            'HTTP-Referer': 'http://localhost:5173',
            'X-Title': 'MoveWell AI Nutrition Specialist',
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
          const secondReply = followUpData.choices?.[0]?.message?.content;
          if (secondReply) {
            return {
              reply: secondReply,
              loggedMeal,
              scheduledPlan,
              loggedWater,
              modelUsed: model
            };
          }
        }
      } catch (fErr) {
        console.warn('Follow-up completion error in nutrition agent:', fErr);
      }

      let fallbackReply = 'Your nutrition updates have been saved to your health plan!';
      if (loggedMeal) fallbackReply = `I've logged your ${loggedMeal.meal_type.toLowerCase()}: ${loggedMeal.food_description}. Keep nourishing your body!`;
      if (scheduledPlan) fallbackReply = `I've prepared and scheduled ${scheduledPlan.meals.length} meals into your Daily Health Plan. You can view them right now!`;

      return {
        reply: fallbackReply,
        loggedMeal,
        scheduledPlan,
        loggedWater,
        modelUsed: model
      };
    }

    return {
      reply: messageObj.content || "I'm your MoveWell Nutrition Specialist. How can I help fuel your day?",
      loggedMeal: null,
      scheduledPlan: null,
      modelUsed: model
    };
  } catch (err) {
    console.error('Error in nutrition voice agent:', err);
    return {
      reply: `I encountered an issue connecting to the nutrition service: ${err.message}. Please try again shortly.`,
      error: err.message
    };
  }
}
