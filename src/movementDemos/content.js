/**
 * Movement Demonstration content — the three baseline assessment
 * demonstrations, plus one for each of the twenty Exercise Library entries
 * (backend/exercise_library/data.py): twenty-three demonstrations in total.
 * The first ten exercise demos were authored in Phase 2 on top of the
 * Phase 0 framework (schema.js, MovementDemo.jsx, registry.js); a second
 * batch of ten was added later alongside the second ten library entries,
 * following the exact same registerMovementDemo() shape and demonstration_id
 * convention (movementId === `exercise-${exercise_id}`).
 *
 * Each demo's phases are written directly from that exercise's own written
 * instructions (or, for the three assessment demos, the panel copy already
 * shown in ShoulderPanel.jsx / FtsstPanel.jsx / BalancePanel.jsx) — nothing
 * here invents a technique. The pose numbers are illustrative angles chosen
 * to make each phase visually distinct, not measured or clinical values;
 * see schema.js for the pose vocabulary they use.
 *
 * Importing this module (which registry.js does, once, at the bottom)
 * registers all twenty-three demos. Nothing else needs to import this file
 * directly — consumers ask the registry for a demo by id.
 */

import { registerMovementDemo } from "./registry.js";

// ---------------------------------------------------------------------------
// Baseline assessment demonstrations
// ---------------------------------------------------------------------------

registerMovementDemo({
  movementId: "assessment-shoulder-raise",
  title: "Shoulder Movement Check",
  category: "assessment",
  durationSeconds: 6,
  phases: [
    {
      id: "start",
      label: "Arms relaxed at your sides",
      holdSeconds: 2,
      pose: { armAngleDeg: { left: 0, right: 0 } },
    },
    {
      id: "raised",
      label: "Both arms raised out to the side",
      holdSeconds: 2,
      pose: { armAngleDeg: { left: 80, right: 80 } },
    },
    {
      id: "lowered",
      label: "Lower back down with control",
      holdSeconds: 2,
      pose: { armAngleDeg: { left: 20, right: 20 } },
    },
  ],
  instructions: [
    "Face the camera, feet about hip width apart.",
    "Raise both arms out to the side, then lower them again.",
  ],
  keyPoints: [
    "Move only as far as is comfortable.",
    "Keep your body upright rather than leaning to help the arm up.",
  ],
  commonMistakes: [
    "Leaning the trunk to help one arm go higher.",
    "Shrugging the shoulders instead of lifting from the side.",
  ],
  repetitions: 3,
  reference: null,
});

registerMovementDemo({
  movementId: "assessment-chair-sit-to-stand",
  title: "Sit to Stand Check",
  category: "assessment",
  durationSeconds: 6,
  phases: [
    {
      id: "seated",
      label: "Seated, arms folded across your chest",
      holdSeconds: 2,
      pose: { stance: "sitting", armAngleDeg: { left: 60, right: 60 } },
    },
    {
      id: "rising",
      label: "Stand up without pushing off",
      holdSeconds: 2,
      pose: { stance: "standing", leanDeg: 15, armAngleDeg: { left: 60, right: 60 } },
    },
    {
      id: "standing",
      label: "Fully standing",
      holdSeconds: 2,
      pose: { stance: "standing", armAngleDeg: { left: 60, right: 60 } },
    },
  ],
  instructions: [
    "Use a stable chair without wheels, seen from the side by the camera.",
    "Sit down, then stand up and sit back down five times at your own pace.",
  ],
  keyPoints: [
    "Fold your arms across your chest so you do not push off the seat.",
    "Stop straight away if you feel unsteady, dizzy, or any pain.",
  ],
  commonMistakes: [
    "Pushing off the armrests or knees with the hands.",
    "Rushing the movement instead of a steady pace.",
  ],
  repetitions: 5,
  reference: null,
});

registerMovementDemo({
  movementId: "assessment-one-leg-stand",
  title: "One-Leg Stand Check",
  category: "assessment",
  durationSeconds: 6,
  phases: [
    {
      id: "ready",
      label: "Standing on both feet",
      holdSeconds: 2,
      pose: {},
    },
    {
      id: "lifted",
      label: "One foot lifted, holding position",
      holdSeconds: 3,
      pose: { legLift: { side: "left", liftAngleDeg: 20 } },
    },
  ],
  instructions: [
    "Face the camera, with something sturdy nearby to hold if needed.",
    "Lift one foot off the floor and hold for as long as comfortable.",
  ],
  keyPoints: [
    "Keep your eyes open and look ahead.",
    "Put your foot down as soon as you feel unsteady.",
  ],
  commonMistakes: [
    "Holding onto furniture throughout instead of only if needed.",
    "Looking down at the feet instead of ahead.",
  ],
  repetitions: null,
  reference: null,
});

// ---------------------------------------------------------------------------
// Exercise Library demonstrations
// ---------------------------------------------------------------------------

registerMovementDemo({
  movementId: "exercise-chair-sit-to-stand",
  title: "Chair Sit-to-Stand",
  category: "exercise",
  durationSeconds: 6,
  phases: [
    { id: "seated", label: "Seated, feet flat on the floor", holdSeconds: 2, pose: { stance: "sitting" } },
    { id: "rising", label: "Push up to standing using your legs", holdSeconds: 2, pose: { stance: "standing", leanDeg: 15 } },
    { id: "standing", label: "Stand fully upright", holdSeconds: 2, pose: { stance: "standing" } },
  ],
  instructions: [
    "Sit toward the front of a stable chair, feet flat on the floor.",
    "Stand up fully, then lower yourself back down with control.",
  ],
  keyPoints: ["Keep the movement slow and controlled on the way down."],
  commonMistakes: ["Using momentum to rock forward instead of leg strength.", "Not standing fully upright at the top."],
  repetitions: 10,
  reference: "NIA Go4Life (go4life.nia.nih.gov/exercise)",
});

registerMovementDemo({
  movementId: "exercise-wall-sit",
  title: "Wall Sit",
  category: "exercise",
  durationSeconds: 6,
  phases: [
    { id: "start", label: "Back against the wall, standing", holdSeconds: 2, pose: { stance: "standing", leanDeg: 0 } },
    { id: "hold", label: "Slide down and hold", holdSeconds: 3, pose: { stance: "sitting", leanDeg: 0 } },
  ],
  instructions: [
    "Stand with your back against a wall and slide down until your knees are comfortably bent.",
    "Hold the position, then slide back up.",
  ],
  keyPoints: ["Only bend your knees as far as is comfortable — this is not a deep squat."],
  commonMistakes: ["Letting the knees go past the toes.", "Holding the breath instead of breathing normally."],
  repetitions: null,
  reference: "NIA Go4Life (go4life.nia.nih.gov/exercise)",
});

registerMovementDemo({
  movementId: "exercise-standing-knee-raise",
  title: "Standing Knee Raise",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Standing on both feet", holdSeconds: 2, pose: {} },
    { id: "raised", label: "Raise one knee toward hip height", holdSeconds: 2, pose: { legLift: { side: "right", liftAngleDeg: 15 } } },
  ],
  instructions: [
    "Stand tall, holding a stable surface if needed.",
    "Lift one knee up toward hip height, then lower it with control.",
  ],
  keyPoints: ["Keep your standing leg steady rather than leaning to one side."],
  commonMistakes: ["Leaning the trunk away from the raised leg.", "Swinging the leg up instead of lifting with control."],
  repetitions: 10,
  reference: "NIA Go4Life (go4life.nia.nih.gov/exercise)",
});

registerMovementDemo({
  movementId: "exercise-supported-calf-raise",
  title: "Supported Calf Raise",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Standing, heels flat", holdSeconds: 2, pose: { heelRaiseDeg: 0 } },
    { id: "raised", label: "Heels lifted, holding a stable surface", holdSeconds: 2, pose: { heelRaiseDeg: 25 } },
  ],
  instructions: [
    "Stand behind a chair or counter, holding on for support.",
    "Rise up onto the balls of your feet, then lower back down slowly.",
  ],
  keyPoints: ["Rise straight up rather than rolling onto the outer edges of the feet."],
  commonMistakes: ["Bouncing at the top instead of a brief pause.", "Not lowering all the way back down between reps."],
  repetitions: 10,
  reference: "NIA Go4Life (go4life.nia.nih.gov/exercise)",
});

registerMovementDemo({
  movementId: "exercise-wall-push-up",
  title: "Wall Push-Up",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Arms extended against the wall", holdSeconds: 2, pose: { leanDeg: 12, armBendDeg: { left: 5, right: 5 } } },
    { id: "bent", label: "Elbows bent, leaning into the wall", holdSeconds: 2, pose: { leanDeg: 22, armBendDeg: { left: 35, right: 35 } } },
  ],
  instructions: [
    "Stand at arm's length from a wall, hands flat against it at shoulder height.",
    "Bend your elbows to bring your chest toward the wall, then push back to start.",
  ],
  keyPoints: ["Keep your body in a straight line from head to heels."],
  commonMistakes: ["Letting the hips sag or pike during the movement.", "Placing the hands too close together."],
  repetitions: 10,
  reference: "NIA Go4Life (go4life.nia.nih.gov/exercise)",
});

registerMovementDemo({
  movementId: "exercise-standing-side-leg-raise",
  title: "Standing Side Leg Raise",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Standing on both feet", holdSeconds: 2, pose: {} },
    { id: "raised", label: "One leg lifted out to the side", holdSeconds: 2, pose: { sideLegLift: { side: "right", liftAngleDeg: 25 } } },
  ],
  instructions: [
    "Stand tall behind a chair, holding on for balance.",
    "Lift one leg out to the side, keeping it straight, then lower it with control.",
  ],
  keyPoints: ["Keep your toes pointing forward and your trunk upright."],
  commonMistakes: ["Leaning the trunk to the opposite side to lift the leg higher.", "Rotating the hip so the toes point up instead of forward."],
  repetitions: 10,
  reference: "NIA Go4Life (go4life.nia.nih.gov/exercise)",
});

registerMovementDemo({
  movementId: "exercise-standing-hip-extension",
  title: "Standing Hip Extension",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Standing on both feet", holdSeconds: 2, pose: {} },
    { id: "raised", label: "One leg lifted straight back", holdSeconds: 2, pose: { hipExtension: { side: "right", liftAngleDeg: 20 } } },
  ],
  instructions: [
    "Stand tall behind a chair, holding on for balance.",
    "Lift one leg straight back without bending your knee, then lower it with control.",
  ],
  keyPoints: ["Keep your trunk upright rather than leaning forward to lift the leg higher."],
  commonMistakes: ["Leaning the trunk forward to raise the leg further.", "Arching the lower back."],
  repetitions: 10,
  reference: "NIA Go4Life (go4life.nia.nih.gov/exercise)",
});

registerMovementDemo({
  movementId: "exercise-heel-to-toe-stand",
  title: "Heel-to-Toe / Tandem Stand",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Standing on both feet, hip width apart", holdSeconds: 2, pose: {} },
    { id: "tandem", label: "Feet placed heel-to-toe in a line", holdSeconds: 3, pose: { tandemStance: true } },
  ],
  instructions: [
    "Stand near a wall or sturdy surface for support if needed.",
    "Place one foot directly in front of the other, heel touching toe, and hold.",
  ],
  keyPoints: ["Look straight ahead rather than down at your feet."],
  commonMistakes: ["Leaving a gap between the heel and toe.", "Holding onto support throughout instead of only if needed."],
  repetitions: null,
  reference: "CDC STEADI 4-Stage Balance Test",
});

registerMovementDemo({
  movementId: "exercise-supported-single-leg-stand",
  title: "Supported Single-Leg Stand",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Standing, holding a stable surface", holdSeconds: 2, pose: {} },
    { id: "lifted", label: "One foot lifted, holding position", holdSeconds: 3, pose: { legLift: { side: "left", liftAngleDeg: 15 } } },
  ],
  instructions: [
    "Stand next to a chair or counter, holding on lightly for support.",
    "Lift one foot off the floor and hold, then switch sides.",
  ],
  keyPoints: ["Use the support only as much as you need to feel steady."],
  commonMistakes: ["Gripping the support tightly with the whole body tensed.", "Looking down instead of ahead."],
  repetitions: null,
  reference: "CDC STEADI 4-Stage Balance Test",
});

registerMovementDemo({
  movementId: "exercise-standing-shoulder-raise",
  title: "Standing Shoulder/Arm Raise",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Arms relaxed at your sides", holdSeconds: 2, pose: { armAngleDeg: { left: 0, right: 0 } } },
    { id: "raised", label: "Both arms raised out to the side", holdSeconds: 2, pose: { armAngleDeg: { left: 85, right: 85 } } },
  ],
  instructions: [
    "Stand tall, feet hip width apart.",
    "Raise both arms out to the side to shoulder height, then lower with control.",
  ],
  keyPoints: ["Move only as far as is comfortable."],
  commonMistakes: ["Shrugging the shoulders instead of lifting from the side.", "Lowering the arms too quickly."],
  repetitions: 10,
  reference: "NIA Go4Life (go4life.nia.nih.gov/exercise)",
});

registerMovementDemo({
  movementId: "exercise-seated-marching",
  title: "Seated Marching",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Seated, feet flat on the floor", holdSeconds: 2, pose: { stance: "sitting" } },
    { id: "raised", label: "One knee lifted toward the chest", holdSeconds: 2, pose: { stance: "sitting", legLift: { side: "right", liftAngleDeg: 40 } } },
  ],
  instructions: [
    "Sit toward the front of a stable chair, back upright.",
    "Lift one knee toward your chest, then lower it, alternating legs as if marching.",
  ],
  keyPoints: ["Sit upright rather than leaning on the backrest."],
  commonMistakes: ["Leaning back on the backrest instead of sitting upright.", "Rushing the lift and lower."],
  repetitions: 10,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});

registerMovementDemo({
  movementId: "exercise-standing-trunk-rotation",
  title: "Standing Trunk Rotation",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Standing tall, facing forward", holdSeconds: 2, pose: {} },
    { id: "rotated", label: "Upper body rotated to one side", holdSeconds: 2, pose: { leanDeg: 0 } },
  ],
  instructions: [
    "Stand tall, feet hip width apart, arms relaxed or crossed over your chest.",
    "Slowly rotate your upper body to one side, then return to center and rotate the other way.",
  ],
  keyPoints: ["Keep your hips facing forward rather than twisting with the torso."],
  commonMistakes: ["Letting the hips and feet twist along with the torso.", "Rotating too fast."],
  repetitions: 10,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});

registerMovementDemo({
  movementId: "exercise-standing-shoulder-rolls",
  title: "Standing Shoulder Rolls",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Arms relaxed at your sides", holdSeconds: 2, pose: { armAngleDeg: { left: 0, right: 0 } } },
    { id: "rolled", label: "Shoulders rolled up and back", holdSeconds: 2, pose: { armAngleDeg: { left: 0, right: 0 } } },
  ],
  instructions: [
    "Stand or sit tall with arms relaxed at your sides.",
    "Slowly roll both shoulders up, back, and down, then reverse the direction.",
  ],
  keyPoints: ["Move slowly and gently rather than forcefully."],
  commonMistakes: ["Rolling only forward and skipping the backward part.", "Rushing through the circles."],
  repetitions: 10,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});

registerMovementDemo({
  movementId: "exercise-standing-ankle-circles",
  title: "Standing Ankle Circles",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Standing, holding a chair or wall", holdSeconds: 2, pose: {} },
    { id: "lifted", label: "One foot lifted, tracing a circle", holdSeconds: 2, pose: { legLift: { side: "left", liftAngleDeg: 8 } } },
  ],
  instructions: [
    "Stand holding a chair or wall for support, and shift your weight onto one leg.",
    "Lift the other foot slightly and slowly trace circles with your toes, then reverse direction.",
  ],
  keyPoints: ["Move from the ankle, not the whole leg."],
  commonMistakes: ["Moving the whole leg from the hip instead of just the ankle.", "Losing balance."],
  repetitions: 10,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});

registerMovementDemo({
  movementId: "exercise-standing-hamstring-stretch",
  title: "Standing Hamstring Stretch",
  category: "exercise",
  durationSeconds: 6,
  phases: [
    { id: "start", label: "Standing, heel forward on the floor", holdSeconds: 2, pose: { stance: "standing", leanDeg: 0 } },
    { id: "hinge", label: "Hinged forward at the hips, holding the stretch", holdSeconds: 3, pose: { stance: "standing", leanDeg: 20 } },
  ],
  instructions: [
    "Stand behind a chair for support, one heel forward with toes pointed up.",
    "Hinge forward at the hips, keeping your back flat, until you feel a gentle stretch, then hold.",
  ],
  keyPoints: ["Hinge from the hips rather than rounding the back."],
  commonMistakes: ["Rounding the back instead of hinging from the hips.", "Bouncing in the stretch."],
  repetitions: null,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});

registerMovementDemo({
  movementId: "exercise-glute-bridge",
  title: "Glute Bridge",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Lying on your back, knees bent", holdSeconds: 2, pose: { stance: "sitting" } },
    { id: "lifted", label: "Hips lifted into a straight line", holdSeconds: 2, pose: { stance: "sitting", leanDeg: 0 } },
  ],
  instructions: [
    "Lie on your back with knees bent and feet flat on the floor.",
    "Press through your feet to lift your hips into a straight line, hold briefly, then lower with control.",
  ],
  keyPoints: ["Lift from the hips rather than overarching the lower back."],
  commonMistakes: ["Overarching the lower back.", "Letting the knees fall inward or outward."],
  repetitions: 10,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});

registerMovementDemo({
  movementId: "exercise-quadruped-bird-dog",
  title: "Quadruped Bird-Dog",
  category: "exercise",
  durationSeconds: 6,
  phases: [
    { id: "start", label: "On hands and knees, back flat", holdSeconds: 2, pose: {} },
    { id: "extended", label: "One arm and the opposite leg extended", holdSeconds: 2, pose: { legLift: { side: "right", liftAngleDeg: 10 } } },
  ],
  instructions: [
    "Start on your hands and knees, hands under shoulders and knees under hips.",
    "Keeping your back flat, extend one arm forward and the opposite leg back, hold, then return and switch sides.",
  ],
  keyPoints: ["Keep the back flat rather than arching or rounding."],
  commonMistakes: ["Arching or rounding the lower back.", "Rushing instead of holding steady."],
  repetitions: 8,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});

registerMovementDemo({
  movementId: "exercise-standing-overhead-reach",
  title: "Standing Overhead Reach",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Arms relaxed at your sides", holdSeconds: 2, pose: { armAngleDeg: { left: 0, right: 0 } } },
    { id: "raised", label: "Both arms reached overhead", holdSeconds: 2, pose: { armAngleDeg: { left: 170, right: 170 } } },
  ],
  instructions: [
    "Stand tall, feet hip width apart, arms relaxed at your sides.",
    "Raise both arms overhead as far as is comfortable, then lower them back down under control.",
  ],
  keyPoints: ["Avoid arching your lower back to reach higher."],
  commonMistakes: ["Arching the lower back to reach higher.", "Shrugging the shoulders up toward the ears."],
  repetitions: 10,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});

registerMovementDemo({
  movementId: "exercise-seated-knee-extension",
  title: "Seated Knee Extension",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Seated, feet flat on the floor", holdSeconds: 2, pose: { stance: "sitting" } },
    { id: "extended", label: "One knee straightened, leg extended", holdSeconds: 2, pose: { stance: "sitting", legLift: { side: "right", liftAngleDeg: 45 } } },
  ],
  instructions: [
    "Sit toward the back of a stable chair, feet flat on the floor.",
    "Slowly straighten one knee until the leg is extended, then lower it back down with control.",
  ],
  keyPoints: ["Move with control rather than swinging the leg up."],
  commonMistakes: ["Swinging the leg up quickly.", "Leaning back in the chair to help lift the leg."],
  repetitions: 10,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});

registerMovementDemo({
  movementId: "exercise-single-leg-reach-balance",
  title: "Single-Leg Reach Balance",
  category: "exercise",
  durationSeconds: 5,
  phases: [
    { id: "start", label: "Standing, near support but not holding on", holdSeconds: 2, pose: {} },
    { id: "reach", label: "One leg lifted, arms reaching forward", holdSeconds: 3, pose: { legLift: { side: "left", liftAngleDeg: 15 } } },
  ],
  instructions: [
    "Stand tall near a wall or sturdy support you can reach if needed, but do not hold on to start.",
    "Shift your weight onto one leg and reach both arms forward, hold, then return and repeat on the other side.",
  ],
  keyPoints: ["Reset calmly to two feet if you feel a wobble, rather than rushing back."],
  commonMistakes: ["Locking the standing knee.", "Rushing back to two feet at the first wobble."],
  repetitions: null,
  reference: "General mobility/strength-training principles, consistent with common physical-therapy and general-fitness guidance.",
});
