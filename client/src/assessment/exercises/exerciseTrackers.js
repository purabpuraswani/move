import { calculateAngle } from '../pose/poseEngine';

/**
 * Creates an exercise state machine for tracking repetitions and form quality.
 */
export function createExerciseTracker(exerciseName) {
  let state = 'WAITING_FOR_START'; // 'WAITING_FOR_START', 'IN_PROGRESS', 'PEAK', 'RETURNING'
  let reps = 0;
  let repInProgress = false;
  let feedback = 'Position yourself in front of the camera';
  let qualityScore = 100;
  let holdSeconds = 0;
  let holdStartTime = null;

  // Stability & Anti-Jitter parameters
  let smoothedAngle = null;
  let peakFrames = 0;
  let lastRepTimestamp = 0;

  function smooth(rawAngle) {
    if (rawAngle === null || isNaN(rawAngle)) return null;
    if (smoothedAngle === null) {
      smoothedAngle = rawAngle;
    } else {
      smoothedAngle = Math.round(smoothedAngle * 0.6 + rawAngle * 0.4);
    }
    return smoothedAngle;
  }

  function canCountRep() {
    const now = Date.now();
    if (now - lastRepTimestamp > 800 && peakFrames >= 2) {
      lastRepTimestamp = now;
      peakFrames = 0;
      return true;
    }
    return false;
  }

  return {
    getStats() {
      return {
        reps,
        state,
        feedback,
        qualityScore,
        holdSeconds
      };
    },

    reset() {
      state = 'WAITING_FOR_START';
      reps = 0;
      repInProgress = false;
      feedback = 'Position yourself in front of the camera';
      qualityScore = 100;
      holdSeconds = 0;
      holdStartTime = null;
      smoothedAngle = null;
      peakFrames = 0;
      lastRepTimestamp = 0;
    },

    processFrame(keypoints) {
      if (!keypoints || keypoints.length === 0) {
        feedback = 'No body detected in camera frame';
        return this.getStats();
      }

      const kp = {};
      keypoints.forEach(k => { kp[k.name] = k; });

      const nameLower = (exerciseName || '').toLowerCase();

      // 1. GLUTE BRIDGE
      if (nameLower.includes('bridge')) {
        const hip = kp.left_hip?.score > 0.3 ? kp.left_hip : kp.right_hip;
        const shoulder = kp.left_shoulder?.score > 0.3 ? kp.left_shoulder : kp.right_shoulder;
        const knee = kp.left_knee?.score > 0.3 ? kp.left_knee : kp.right_knee;

        if (!hip || !shoulder || !knee) {
          feedback = 'Ensure shoulders, hips, and knees are clearly visible';
          return this.getStats();
        }

        const rawAngle = calculateAngle(shoulder, hip, knee);
        const hipAngle = smooth(rawAngle);
        if (hipAngle === null) return this.getStats();

        if (hipAngle < 145) {
          // Starting / Lowered position
          if (state === 'PEAK' && canCountRep()) {
            reps += 1;
            state = 'WAITING_FOR_START';
            repInProgress = false;
            feedback = `Rep ${reps} complete! Great bridge. Lift again when ready.`;
          } else {
            feedback = 'Drive through heels and squeeze glutes upward';
          }
        } else if (hipAngle >= 165) {
          // Peak bridge extension
          state = 'PEAK';
          peakFrames += 1;
          repInProgress = true;
          feedback = 'Hold top bridge position! Keep hips fully aligned';
        } else if (hipAngle >= 145 && hipAngle < 165) {
          state = 'IN_PROGRESS';
          feedback = 'Lifting... Push hips slightly higher';
        }
      }

      // 2. SHOULDER WALL SLIDE
      else if (nameLower.includes('wall slide') || nameLower.includes('slide')) {
        const lShoulder = kp.left_shoulder;
        const lElbow = kp.left_elbow;
        const lWrist = kp.left_wrist;
        const lHip = kp.left_hip;

        if (!lShoulder || !lElbow || !lWrist) {
          feedback = 'Ensure upper body and arms are visible';
          return this.getStats();
        }

        const rawAngle = calculateAngle(lHip, lShoulder, lElbow);
        const leftArmAngle = smooth(rawAngle);

        if (leftArmAngle !== null) {
          if (leftArmAngle < 110) {
            // Starting position (elbows bent in W-shape)
            if (state === 'PEAK' && canCountRep()) {
              reps += 1;
              state = 'WAITING_FOR_START';
              feedback = `Rep ${reps} complete! Excellent slide.`;
            } else {
              feedback = 'Start with elbows at 90° against wall. Slide arms upward.';
            }
          } else if (leftArmAngle >= 145) {
            state = 'PEAK';
            peakFrames += 1;
            feedback = 'Peak overhead reach! Keep forearms in contact with wall.';
          } else {
            state = 'IN_PROGRESS';
            feedback = 'Gliding upward... Avoid shrugging shoulders.';
          }
        }
      }

      // 3. SIT-TO-STAND
      else if (nameLower.includes('sit') || nameLower.includes('stand')) {
        const hip = kp.left_hip?.score > 0.3 ? kp.left_hip : kp.right_hip;
        const knee = kp.left_knee?.score > 0.3 ? kp.left_knee : kp.right_knee;
        const ankle = kp.left_ankle?.score > 0.3 ? kp.left_ankle : kp.right_ankle;

        if (!hip || !knee || !ankle) {
          feedback = 'Position chair so side profile of hips and legs is visible';
          return this.getStats();
        }

        const rawAngle = calculateAngle(hip, knee, ankle);
        const kneeAngle = smooth(rawAngle);

        if (kneeAngle !== null) {
          if (kneeAngle < 115) {
            // Seated position
            if (state === 'PEAK' && canCountRep()) {
              reps += 1;
              state = 'WAITING_FOR_START';
              feedback = `Rep ${reps} complete! Good controlled descent.`;
            } else {
              feedback = 'Seated. Lean slightly forward and push through feet to stand.';
            }
          } else if (kneeAngle >= 165) {
            // Standing lockout
            state = 'PEAK';
            peakFrames += 1;
            feedback = 'Full standing position reached! Slowly lower back down.';
          } else {
            state = 'IN_PROGRESS';
            feedback = 'Standing up... Keep knees aligned over toes.';
          }
        }
      }

      // 4. STANDING SIDE LEG RAISE
      else if (nameLower.includes('side leg') || nameLower.includes('leg raise')) {
        const lHip = kp.left_hip;
        const rHip = kp.right_hip;
        const lAnkle = kp.left_ankle;
        const rAnkle = kp.right_ankle;

        if (!lHip || !rHip || !lAnkle || !rAnkle) {
          feedback = 'Step back so full body and legs are visible in camera';
          return this.getStats();
        }

        const ankleDistance = Math.abs(lAnkle.x - rAnkle.x);
        const hipWidth = Math.abs(lHip.x - rHip.x) || 50;
        const rawRatio = (ankleDistance / hipWidth) * 100;
        const spreadRatio = (smooth(rawRatio) || rawRatio) / 100;

        if (spreadRatio < 1.3) {
          // Neutral feet together
          if (state === 'PEAK' && canCountRep()) {
            reps += 1;
            state = 'WAITING_FOR_START';
            feedback = `Rep ${reps} complete! Good leg raise.`;
          } else {
            feedback = 'Standing tall. Lift one leg directly sideways.';
          }
        } else if (spreadRatio >= 1.9) {
          // Leg abducted sideways
          state = 'PEAK';
          peakFrames += 1;
          feedback = 'Peak leg raise hold! Avoid leaning your upper body.';
        } else {
          state = 'IN_PROGRESS';
          feedback = 'Abducting leg... Maintain upright torso.';
        }
      }

      // 5. SUPPORTED SINGLE-LEG BALANCE
      else if (nameLower.includes('balance') || nameLower.includes('single-leg')) {
        const lAnkle = kp.left_ankle;
        const rAnkle = kp.right_ankle;

        if (!lAnkle || !rAnkle || lAnkle.score < 0.25 || rAnkle.score < 0.25) {
          feedback = 'Step back so your feet and ankles are clearly visible';
          return this.getStats();
        }

        const ankleHeightDelta = Math.abs(lAnkle.y - rAnkle.y);
        const isFootLifted = ankleHeightDelta > 25;

        if (isFootLifted) {
          if (!holdStartTime) holdStartTime = Date.now();
          holdSeconds = Math.round((Date.now() - holdStartTime) / 1000);
          state = 'IN_PROGRESS';
          feedback = `Balancing on one leg: ${holdSeconds}s held. Keep eyes focused forward.`;

          if (holdSeconds >= 10 && reps === 0) {
            reps = 1;
          }
        } else {
          holdStartTime = null;
          state = 'WAITING_FOR_START';
          feedback = 'Shift weight to one leg and lift the other foot off the ground.';
        }
      }

      // Default fallback tracker
      else {
        feedback = 'Exercise tracking active. Follow prescribed repetitions.';
      }

      return this.getStats();
    }
  };
}

