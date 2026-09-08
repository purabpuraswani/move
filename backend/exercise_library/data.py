"""The twenty intervention exercises, as data.

The first ten (Phase 2) were drafted from two public, freely citable sources
aimed at exactly this population — older or deconditioned adults, everyday
functional movement and fall prevention:

    NIA Go4Life    National Institute on Aging exercise program
                   (go4life.nia.nih.gov/exercise). Confirmed to publish, by
                   name, several of the exercises drafted here (including a
                   "Wall Push-Up Strength Exercise" page).
    CDC STEADI     the 4-Stage Balance Test (single-leg stance and tandem
                   stance are two of its four stages), part of CDC's Stopping
                   Elderly Accidents, Deaths & Injuries initiative.

The second ten were added later to reach twenty, drawn from general,
well-established wellness/mobility/strength exercise knowledge rather than
one additional named source, and cited with `GENERAL_REFERENCE` below
instead of overclaiming a specific program page for each. They fill gaps the
first ten left: more `mobility_training` entries, an `advanced` difficulty
exercise, and a wider mix of honestly-marked movenet_support (several of
these ten are genuinely not measurable from a single front-facing 2D camera
— depth-axis rotation, fine-motor joint circles, or floor-based positions —
and are marked `supported: false` rather than forcing a fake metric).

Every `instructions`/`common_mistakes`/`safety_constraints`/`progression`/
`regression` string below is this project's own plain-language adaptation —
not a verbatim clinical protocol, and not a claim that a named source
endorses this exact wording. `reference` records which source (or general
attribution) each entry was adapted from, so a healthcare/physio reviewer has
a starting point rather than an unfounded claim to take on faith. None of
these twenty exercises name a disease, condition, or diagnosis, and none is
described as treatment.
"""

GO4LIFE_REFERENCE = "National Institute on Aging – Go4Life exercise program (go4life.nia.nih.gov/exercise)"
STEADI_REFERENCE = "CDC STEADI initiative – 4-Stage Balance Test (single-leg and tandem stance stages)"
GENERAL_REFERENCE = (
    "General mobility, stability, and strength-training principles, "
    "consistent with common physical-therapy and general-fitness guidance "
    "(not tied to a single named program page, unlike the Go4Life/STEADI "
    "citations above)."
)


def _movenet(*, supported, implemented, metrics, notes=None):
    return {
        "supported": supported,
        "implemented": implemented,
        "metrics": list(metrics),
        "notes": notes,
    }


EXERCISES = [
    {
        "exercise_id": "chair-sit-to-stand",
        "name": "Chair Sit-to-Stand",
        "category": "lower_body_strength",
        "target_capability": ["functional_movement", "strength"],
        "target_body_area": ["legs", "hips", "core"],
        "difficulty": "beginner",
        "equipment": ["chair"],
        "instructions": [
            "Sit toward the front of a stable chair with no wheels, feet flat "
            "on the floor about hip width apart.",
            "Lean slightly forward and press through your feet to stand up "
            "fully, using your hands on the armrests only as much as you "
            "need to.",
            "Pause briefly standing, then lower yourself back down under "
            "control.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Reduce how much you push off the armrests, or use a lower seat.",
        "regression": "Use a higher seat, or push off firmly with both hands.",
        "common_mistakes": [
            "Using momentum to rock up rather than pressing through the legs.",
            "Not standing all the way up before sitting back down.",
        ],
        "safety_constraints": [
            "Use a chair without wheels, on a stable, non-slip floor.",
            "Stop if you feel dizzy, unsteady, or have joint pain.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["repetitions", "durationSeconds", "completion"],
            notes=(
                "Same measurable shape as the FTSST baseline test (a knee-"
                "angle sit/stand transition), reusing the same kind of "
                "detection approach rather than the same test."
            ),
        ),
        "measurable_metrics": ["repetitions", "durationSeconds", "completion"],
        "demonstration_id": "exercise-chair-sit-to-stand",
        "reference": GO4LIFE_REFERENCE,
    },
    {
        "exercise_id": "wall-sit",
        "name": "Wall Sit",
        "category": "lower_body_strength",
        "target_capability": ["strength"],
        "target_body_area": ["legs", "knees"],
        "difficulty": "intermediate",
        "equipment": ["wall"],
        "instructions": [
            "Stand with your back flat against a wall, feet shoulder width "
            "apart and a small step out from the wall.",
            "Slide down the wall until your knees are comfortably bent — a "
            "shallow bend is fine to start.",
            "Hold the position, then slide back up to standing.",
        ],
        "sets": 2,
        "repetitions": None,
        "duration_seconds": 20,
        "progression": "Hold for longer, or bend the knees a little more (toward 90 degrees).",
        "regression": "Use a shallower knee bend, a shorter hold, or hands on a table for support.",
        "common_mistakes": [
            "Letting the knees travel forward past the toes.",
            "Holding the breath throughout the hold.",
        ],
        "safety_constraints": [
            "Stop immediately if you feel knee pain.",
            "Not recommended without guidance if you have a significant "
            "knee condition.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["durationSeconds", "completion"],
        ),
        "measurable_metrics": ["durationSeconds", "completion"],
        "demonstration_id": "exercise-wall-sit",
        "reference": GO4LIFE_REFERENCE,
    },
    {
        "exercise_id": "standing-knee-raise",
        "name": "Standing Knee Raise",
        "category": "mobility_training",
        "target_capability": ["mobility", "stability"],
        "target_body_area": ["hips", "legs"],
        "difficulty": "beginner",
        "equipment": ["chair"],
        "instructions": [
            "Stand tall, holding a chair back or counter for support if "
            "needed.",
            "Slowly raise one knee toward your chest as far as is "
            "comfortable, without leaning back.",
            "Lower it under control, then repeat with the other leg.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Hold briefly at the top, or reduce hand support.",
        "regression": "Keep a firm hold on support and raise the knee a smaller amount.",
        "common_mistakes": [
            "Leaning the torso backward to help lift the leg.",
            "Rushing the movement instead of controlling it.",
        ],
        "safety_constraints": [
            "Keep a hand on support if balance feels uncertain.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["repetitions", "rangeOfMotion", "symmetry"],
        ),
        "measurable_metrics": ["repetitions", "rangeOfMotion", "symmetry"],
        "demonstration_id": "exercise-standing-knee-raise",
        "reference": GO4LIFE_REFERENCE,
    },
    {
        "exercise_id": "supported-calf-raise",
        "name": "Supported Calf Raise",
        "category": "lower_body_strength",
        "target_capability": ["strength", "mobility"],
        "target_body_area": ["calves", "ankles"],
        "difficulty": "beginner",
        "equipment": ["chair", "wall"],
        "instructions": [
            "Stand behind a chair or facing a wall, hands resting lightly on "
            "it for balance.",
            "Rise up onto the balls of both feet as high as is comfortable.",
            "Lower back down slowly, under control.",
        ],
        "sets": 2,
        "repetitions": 15,
        "duration_seconds": None,
        "progression": "Try one leg at a time, or use less hand support.",
        "regression": "Use a smaller range of motion and both hands on support.",
        "common_mistakes": [
            "Rocking onto the outer or inner edge of the foot.",
            "Bouncing quickly instead of moving with control.",
        ],
        "safety_constraints": [
            "Wear non-slip footwear or perform on a non-slip surface.",
        ],
        "movenet_support": _movenet(
            supported=False,
            implemented=False,
            metrics=[],
            notes=(
                "A heel raise is not observable with this pose model. MoveNet "
                "estimates 17 body points and none of them is the heel or the "
                "toe -- the ankle is the lowest point it locates -- so the "
                "few centimetres the heel actually travels cannot be seen. "
                "This entry previously claimed an implemented assessment; it "
                "was corrected rather than backed by a proxy measurement, "
                "because a number derived from something the camera cannot "
                "see is an invention, not a measurement."
            ),
        ),
        "measurable_metrics": [],
        "demonstration_id": "exercise-supported-calf-raise",
        "reference": GO4LIFE_REFERENCE,
    },
    {
        "exercise_id": "wall-push-up",
        "name": "Wall Push-Up",
        "category": "upper_body_strength",
        "target_capability": ["strength"],
        "target_body_area": ["shoulders", "arms", "core"],
        "difficulty": "beginner",
        "equipment": ["wall"],
        "instructions": [
            "Stand facing a wall, a little farther than arm's length away, "
            "and place both hands on the wall at shoulder height and width.",
            "Bend your elbows to bring your chest toward the wall, keeping "
            "your body in a straight line.",
            "Push back to the starting position.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Stand farther from the wall, or progress to an incline push-up on a sturdy counter.",
        "regression": "Stand closer to the wall, or do fewer repetitions.",
        "common_mistakes": [
            "Letting the hips sag or pike instead of staying in a straight line.",
            "Flaring the elbows straight out to the sides.",
        ],
        "safety_constraints": [
            "Keep wrists in a comfortable, neutral position; stop if it "
            "causes wrist pain.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["repetitions", "rangeOfMotion", "movementQuality"],
        ),
        "measurable_metrics": ["repetitions", "rangeOfMotion", "movementQuality"],
        "demonstration_id": "exercise-wall-push-up",
        "reference": GO4LIFE_REFERENCE,
    },
    {
        "exercise_id": "standing-side-leg-raise",
        "name": "Standing Side Leg Raise",
        "category": "lower_body_strength",
        "target_capability": ["strength", "stability"],
        "target_body_area": ["hips", "legs"],
        "difficulty": "beginner",
        "equipment": ["chair"],
        "instructions": [
            "Stand behind a chair, holding the back of it with both hands.",
            "Keeping your leg straight and toes facing forward, lift one leg "
            "out to the side.",
            "Lower it under control, then repeat with the other leg.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Use less hand support, or hold briefly at the top.",
        "regression": "Lift a smaller amount and keep both hands firmly on support.",
        "common_mistakes": [
            "Leaning the torso to the opposite side instead of lifting the leg.",
            "Rotating the hip so the toes point upward instead of forward.",
        ],
        "safety_constraints": [
            "Move slowly and with control; stop if you feel unsteady.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["repetitions", "rangeOfMotion", "symmetry"],
        ),
        "measurable_metrics": ["repetitions", "rangeOfMotion", "symmetry"],
        "demonstration_id": "exercise-standing-side-leg-raise",
        "reference": GO4LIFE_REFERENCE,
    },
    {
        "exercise_id": "standing-hip-extension",
        "name": "Standing Hip Extension",
        "category": "lower_body_strength",
        "target_capability": ["strength", "stability"],
        "target_body_area": ["hips", "legs", "core"],
        "difficulty": "beginner",
        "equipment": ["chair"],
        "instructions": [
            "Stand facing a chair or counter, holding it with both hands.",
            "Keeping your leg straight, lift it backward without leaning "
            "your torso forward.",
            "Lower it under control, then repeat with the other leg.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Use less hand support, or hold briefly at the top.",
        "regression": "Lift a smaller amount and keep both hands firmly on support.",
        "common_mistakes": [
            "Arching the lower back instead of moving from the hip.",
            "Leaning the torso forward to swing the leg higher.",
        ],
        "safety_constraints": [
            "Keep the range of motion small and controlled to avoid "
            "straining the lower back.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["repetitions", "rangeOfMotion"],
        ),
        "measurable_metrics": ["repetitions", "rangeOfMotion"],
        "demonstration_id": "exercise-standing-hip-extension",
        "reference": GO4LIFE_REFERENCE,
    },
    {
        "exercise_id": "heel-to-toe-stand",
        "name": "Heel-to-Toe / Tandem Stand",
        "category": "balance_training",
        "target_capability": ["stability"],
        "target_body_area": ["legs", "ankles", "core"],
        "difficulty": "intermediate",
        "equipment": ["wall"],
        "instructions": [
            "Stand near a wall or sturdy support you can reach if needed.",
            "Place one foot directly in front of the other, heel touching "
            "toe, in a straight line.",
            "Hold the position, looking forward rather than down at your "
            "feet, then relax and switch which foot is in front.",
        ],
        "sets": 2,
        "repetitions": None,
        "duration_seconds": 10,
        "progression": "Hold for longer, or walk heel-to-toe for a short distance (with support nearby).",
        "regression": "Stand with feet closer together rather than fully aligned, keeping a hand on support.",
        "common_mistakes": [
            "Looking down at the feet the whole time instead of ahead.",
            "Feet not actually aligned heel-to-toe.",
        ],
        "safety_constraints": [
            "Always perform near a wall or sturdy support.",
            "Use caution or check with a healthcare professional first if "
            "you have a recent history of falls.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=False,
            metrics=[],
            notes=(
                "The stance itself (front/back foot alignment, hold time) is "
                "plausible to detect from a front-facing camera, but reliable "
                "foot-alignment geometry was not implemented in Phase 2 — "
                "only the hold-duration engine's foundation exists (see "
                "src/exerciseAssessment/). Marking this honestly as "
                "supported-but-not-yet-implemented rather than claiming "
                "metrics the current code does not produce."
            ),
        ),
        "measurable_metrics": [],
        "demonstration_id": "exercise-heel-to-toe-stand",
        "reference": STEADI_REFERENCE,
    },
    {
        "exercise_id": "supported-single-leg-stand",
        "name": "Supported Single-Leg Stand",
        "category": "balance_training",
        "target_capability": ["stability"],
        "target_body_area": ["legs", "ankles", "core"],
        "difficulty": "beginner",
        "equipment": ["chair", "wall"],
        "instructions": [
            "Stand behind a chair or beside a wall, with fingertips resting "
            "on it for support.",
            "Shift your weight onto one leg and lift the other foot slightly "
            "off the floor.",
            "Hold the position, then lower the foot and repeat on the other "
            "side.",
        ],
        "sets": 2,
        "repetitions": None,
        "duration_seconds": 10,
        "progression": "Use lighter fingertip support, and gradually work toward none.",
        "regression": "Keep a firm hold on support and hold for a shorter time.",
        "common_mistakes": [
            "Hiking the hip up on the lifted side instead of standing tall.",
            "Holding the breath during the hold.",
        ],
        "safety_constraints": [
            "Always perform near a stable chair or wall.",
            "Stop immediately if you feel unsteady.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["durationSeconds", "completion", "symmetry"],
            notes=(
                "The same measurable shape as the balance baseline test "
                "(one foot lifted, hold timed), reusing the same kind of "
                "detection approach rather than the same test or its "
                "protocol thresholds."
            ),
        ),
        "measurable_metrics": ["durationSeconds", "completion", "symmetry"],
        "demonstration_id": "exercise-supported-single-leg-stand",
        "reference": STEADI_REFERENCE,
    },
    {
        "exercise_id": "standing-shoulder-raise",
        "name": "Standing Shoulder/Arm Raise",
        "category": "upper_body_strength",
        "target_capability": ["mobility", "strength"],
        "target_body_area": ["shoulders", "arms"],
        "difficulty": "beginner",
        "equipment": [],
        "instructions": [
            "Stand tall with arms relaxed at your sides.",
            "Raise both arms out in front of you (or out to the sides) to "
            "about shoulder height, or as high as is comfortable.",
            "Lower them back down under control.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Hold a light weight in each hand, or raise a little higher.",
        "regression": "Raise through a smaller range, or perform seated.",
        "common_mistakes": [
            "Shrugging the shoulders up toward the ears.",
            "Using a fast, swinging motion instead of a controlled one.",
        ],
        "safety_constraints": [
            "Stop if you feel shoulder pain, and only raise as far as is "
            "comfortable.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["repetitions", "rangeOfMotion", "symmetry"],
            notes=(
                "The same measurable shape as the shoulder baseline test "
                "(arm elevation angle), reusing the same kind of detection "
                "approach rather than the same test or its protocol "
                "thresholds."
            ),
        ),
        "measurable_metrics": ["repetitions", "rangeOfMotion", "symmetry"],
        "demonstration_id": "exercise-standing-shoulder-raise",
        "reference": GO4LIFE_REFERENCE,
    },

    {
        "exercise_id": "seated-marching",
        "name": "Seated Marching",
        "category": "lower_body_strength",
        "target_capability": ["functional_movement", "strength"],
        "target_body_area": ["legs", "hips", "core"],
        "difficulty": "beginner",
        "equipment": ["chair"],
        "instructions": [
            "Sit toward the front of a stable chair, feet flat on the floor, "
            "back upright and not leaning on the backrest.",
            "Lift one knee up toward your chest as far as is comfortable, "
            "then lower it with control.",
            "Repeat, alternating legs, as if marching in place while seated.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "March a little faster, or hold light hand weights.",
        "regression": "Lift the knee a smaller amount, or rest hands on the chair seat for stability.",
        "common_mistakes": [
            "Leaning back on the backrest instead of sitting upright.",
            "Rushing the movement instead of controlling the lift and lower.",
        ],
        "safety_constraints": [
            "Use a stable chair without wheels on a non-slip floor.",
            "Stop if you feel dizzy or unsteady.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["repetitions", "symmetry"],
        ),
        "measurable_metrics": ["repetitions", "symmetry"],
        "demonstration_id": "exercise-seated-marching",
        "reference": GENERAL_REFERENCE,
    },
    {
        "exercise_id": "standing-trunk-rotation",
        "name": "Standing Trunk Rotation",
        "category": "mobility_training",
        "target_capability": ["mobility"],
        "target_body_area": ["core"],
        "difficulty": "beginner",
        "equipment": [],
        "instructions": [
            "Stand tall with feet hip width apart and arms relaxed or "
            "crossed lightly over your chest.",
            "Slowly rotate your upper body to one side as far as is "
            "comfortable, keeping your hips facing forward.",
            "Return to center, then rotate to the other side.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Increase how far you rotate, within a comfortable range.",
        "regression": "Rotate through a smaller range, or perform seated.",
        "common_mistakes": [
            "Letting the hips and feet twist along with the torso.",
            "Using a fast, jerky motion instead of a slow, controlled one.",
        ],
        "safety_constraints": [
            "Move only as far as is comfortable; stop if you feel back pain.",
            "Keep the movement slow and controlled rather than a fast twist.",
        ],
        "movenet_support": _movenet(
            supported=False,
            implemented=False,
            metrics=[],
            notes=(
                "This rotation happens largely around the body's vertical "
                "axis, so a front-facing 2D camera sees shoulder keypoints "
                "moving toward and away from it rather than a clean lateral "
                "displacement it can measure — the same ambiguity a single "
                "2D keypoint set has with any depth-axis motion. Honestly "
                "marked as not MoveNet-supported rather than forcing a "
                "rotation-angle metric the current pipeline cannot produce "
                "reliably from one camera view."
            ),
        ),
        "measurable_metrics": [],
        "demonstration_id": "exercise-standing-trunk-rotation",
        "reference": GENERAL_REFERENCE,
    },
    {
        "exercise_id": "standing-shoulder-rolls",
        "name": "Standing Shoulder Rolls",
        "category": "mobility_training",
        "target_capability": ["mobility"],
        "target_body_area": ["shoulders"],
        "difficulty": "beginner",
        "equipment": [],
        "instructions": [
            "Stand or sit tall with arms relaxed at your sides.",
            "Slowly roll both shoulders up, back, and down in a circular "
            "motion.",
            "Repeat for several slow circles, then reverse the direction.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Make the circles larger, within a comfortable range.",
        "regression": "Make the circles smaller and slower.",
        "common_mistakes": [
            "Rolling only the shoulders forward and skipping the backward "
            "part of the circle.",
            "Rushing through the circles instead of moving slowly.",
        ],
        "safety_constraints": [
            "Stop if you feel shoulder or neck pain.",
            "Keep the motion slow and gentle rather than forceful.",
        ],
        "movenet_support": _movenet(
            supported=False,
            implemented=False,
            metrics=[],
            notes=(
                "A shoulder roll is a small circular motion at the shoulder "
                "joint with a meaningful front-to-back (depth) component "
                "relative to a front-facing camera, and its amplitude is "
                "small relative to the keypoint jitter MoveNet's shoulder "
                "landmarks already have — not a movement this project's "
                "single-camera 2D pipeline can reliably measure."
            ),
        ),
        "measurable_metrics": [],
        "demonstration_id": "exercise-standing-shoulder-rolls",
        "reference": GENERAL_REFERENCE,
    },
    {
        "exercise_id": "standing-ankle-circles",
        "name": "Standing Ankle Circles",
        "category": "mobility_training",
        "target_capability": ["mobility"],
        "target_body_area": ["ankles"],
        "difficulty": "beginner",
        "equipment": ["chair", "wall"],
        "instructions": [
            "Stand holding a chair or wall for support, and shift your "
            "weight onto one leg.",
            "Lift the other foot slightly off the floor and slowly trace "
            "circles with your toes, moving from the ankle.",
            "Repeat for several circles, then reverse direction and repeat "
            "on the other foot.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Make the circles larger, or reduce hand support.",
        "regression": "Make the circles smaller and keep a firm hold on support.",
        "common_mistakes": [
            "Moving the whole leg from the hip instead of just the ankle.",
            "Losing balance by not holding support firmly enough.",
        ],
        "safety_constraints": [
            "Always perform near a stable chair or wall.",
            "Stop if you feel ankle pain or instability.",
        ],
        "movenet_support": _movenet(
            supported=False,
            implemented=False,
            metrics=[],
            notes=(
                "Ankle circles are a small, fine-motor rotation of the foot "
                "that MoveNet's 17 keypoints (no toe or arch landmarks) do "
                "not resolve at that resolution, and a meaningful part of "
                "the circular path moves toward and away from a "
                "front-facing camera rather than across it. Marked "
                "honestly as not supported rather than claiming a "
                "range-of-motion metric the pipeline cannot actually "
                "produce."
            ),
        ),
        "measurable_metrics": [],
        "demonstration_id": "exercise-standing-ankle-circles",
        "reference": GENERAL_REFERENCE,
    },
    {
        "exercise_id": "standing-hamstring-stretch",
        "name": "Standing Hamstring Stretch",
        "category": "mobility_training",
        "target_capability": ["mobility"],
        "target_body_area": ["legs", "hips"],
        "difficulty": "beginner",
        "equipment": ["chair"],
        "instructions": [
            "Stand behind a chair, holding the back of it for support, and "
            "place one heel on the floor a step in front of you with the "
            "toes pointed up.",
            "Keeping that leg straight and your back flat, hinge forward at "
            "the hips until you feel a gentle stretch behind the thigh.",
            "Hold the position, then return to standing and repeat on the "
            "other leg.",
        ],
        "sets": 2,
        "repetitions": None,
        "duration_seconds": 20,
        "progression": "Hinge a little further forward, within a comfortable stretch.",
        "regression": "Hinge only slightly forward and hold on with both hands.",
        "common_mistakes": [
            "Rounding the back instead of hinging from the hips.",
            "Bouncing in the stretch instead of holding it still.",
        ],
        "safety_constraints": [
            "Stretch only to a gentle pull, never to the point of pain.",
            "Keep a hand on support if balance feels uncertain.",
        ],
        "movenet_support": _movenet(
            supported=False,
            implemented=False,
            metrics=[],
            notes=(
                "A hamstring stretch is judged by where the stretch is felt "
                "and by whether the back stays long, neither of which this "
                "camera setup can see. The trunk-hinge angle it can measure "
                "does not distinguish a well-performed stretch from a rounded "
                "back, so scoring it would reward the wrong thing. Follow the "
                "demonstration instead."
            ),
        ),
        "measurable_metrics": [],
        "demonstration_id": "exercise-standing-hamstring-stretch",
        "reference": GENERAL_REFERENCE,
    },
    {
        "exercise_id": "glute-bridge",
        "name": "Glute Bridge",
        "category": "lower_body_strength",
        "target_capability": ["strength"],
        "target_body_area": ["hips", "legs", "core"],
        "difficulty": "beginner",
        "equipment": ["mat"],
        "instructions": [
            "Lie on your back on a mat with knees bent and feet flat on the "
            "floor, hip width apart.",
            "Press through your feet to lift your hips up until your body "
            "forms a straight line from shoulders to knees.",
            "Hold briefly, then lower your hips back down with control.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Hold the top position longer, or lift one leg straight at the top.",
        "regression": "Lift through a smaller range of motion.",
        "common_mistakes": [
            "Overarching the lower back instead of lifting from the hips.",
            "Letting the knees fall outward or inward during the lift.",
        ],
        "safety_constraints": [
            "Stop if you feel lower back or hip pain.",
            "Perform on a mat or padded, non-slip surface.",
        ],
        "movenet_support": _movenet(
            supported=False,
            implemented=False,
            metrics=[],
            notes=(
                "Performed lying on the floor, which is outside the "
                "standing/seated, front-facing camera framing every other "
                "exercise and demonstration in this library assumes (see "
                "exerciseAssessment/ and the other movenet_support entries "
                "above) — the current pipeline has no supported camera "
                "position for a supine view, so hip-lift height is not "
                "something it can observe, let alone measure reliably."
            ),
        ),
        "measurable_metrics": [],
        "demonstration_id": "exercise-glute-bridge",
        "reference": GENERAL_REFERENCE,
    },
    {
        "exercise_id": "quadruped-bird-dog",
        "name": "Quadruped Bird-Dog",
        "category": "balance_training",
        "target_capability": ["stability", "strength"],
        "target_body_area": ["core", "hips", "shoulders"],
        "difficulty": "intermediate",
        "equipment": ["mat"],
        "instructions": [
            "Start on your hands and knees on a mat, hands under your "
            "shoulders and knees under your hips.",
            "Keeping your back flat, slowly extend one arm forward and the "
            "opposite leg backward, in line with your body.",
            "Hold briefly, then return to the starting position and repeat "
            "with the other arm and leg.",
        ],
        "sets": 2,
        "repetitions": 8,
        "duration_seconds": None,
        "progression": "Hold the extended position for longer, or add a light ankle weight.",
        "regression": "Extend just the arm or just the leg on its own, not both together.",
        "common_mistakes": [
            "Arching or rounding the lower back instead of keeping it flat.",
            "Rushing the movement instead of holding it steady.",
        ],
        "safety_constraints": [
            "Perform on a mat or padded, non-slip surface.",
            "Stop if you feel wrist, knee, or lower back pain.",
        ],
        "movenet_support": _movenet(
            supported=False,
            implemented=False,
            metrics=[],
            notes=(
                "A floor-based, hands-and-knees position outside the "
                "standing/seated front-facing framing this project's "
                "camera setup supports, and the arm/leg extension moves "
                "substantially toward and away from a camera placed to "
                "view it — the same depth-axis limitation as the other "
                "exercises marked unsupported above, compounded by an "
                "unsupported camera angle."
            ),
        ),
        "measurable_metrics": [],
        "demonstration_id": "exercise-quadruped-bird-dog",
        "reference": GENERAL_REFERENCE,
    },
    {
        "exercise_id": "standing-overhead-reach",
        "name": "Standing Overhead Reach",
        "category": "upper_body_strength",
        "target_capability": ["mobility", "strength"],
        "target_body_area": ["shoulders", "arms"],
        "difficulty": "beginner",
        "equipment": [],
        "instructions": [
            "Stand tall with feet hip width apart, arms relaxed at your "
            "sides.",
            "Raise both arms overhead as far as is comfortable, reaching "
            "upward without arching your lower back.",
            "Lower them back down under control.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Hold a light weight in each hand, or reach a little higher.",
        "regression": "Raise through a smaller range, or perform seated.",
        "common_mistakes": [
            "Arching the lower back to reach higher.",
            "Shrugging the shoulders up toward the ears.",
        ],
        "safety_constraints": [
            "Stop if you feel shoulder pain, and only raise as far as is "
            "comfortable.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["repetitions", "rangeOfMotion", "symmetry"],
        ),
        "measurable_metrics": ["repetitions", "rangeOfMotion", "symmetry"],
        "demonstration_id": "exercise-standing-overhead-reach",
        "reference": GENERAL_REFERENCE,
    },
    {
        "exercise_id": "seated-knee-extension",
        "name": "Seated Knee Extension",
        "category": "lower_body_strength",
        "target_capability": ["strength"],
        "target_body_area": ["legs", "knees"],
        "difficulty": "beginner",
        "equipment": ["chair"],
        "instructions": [
            "Sit toward the back of a stable chair, feet flat on the "
            "floor.",
            "Slowly straighten one knee, lifting the foot until the leg is "
            "extended out in front of you.",
            "Lower it back down with control, then repeat with the other "
            "leg.",
        ],
        "sets": 2,
        "repetitions": 10,
        "duration_seconds": None,
        "progression": "Add a light ankle weight, or hold the extended position briefly.",
        "regression": "Extend through a smaller range of motion.",
        "common_mistakes": [
            "Swinging the leg up quickly instead of moving with control.",
            "Leaning back in the chair to help lift the leg.",
        ],
        "safety_constraints": [
            "Stop if you feel knee pain.",
            "Use a stable chair without wheels.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["repetitions", "rangeOfMotion", "symmetry"],
        ),
        "measurable_metrics": ["repetitions", "rangeOfMotion", "symmetry"],
        "demonstration_id": "exercise-seated-knee-extension",
        "reference": GENERAL_REFERENCE,
    },
    {
        "exercise_id": "single-leg-reach-balance",
        "name": "Single-Leg Reach Balance",
        "category": "balance_training",
        "target_capability": ["stability"],
        "target_body_area": ["legs", "hips", "core"],
        "difficulty": "advanced",
        "equipment": [],
        "instructions": [
            "Stand tall near a wall or sturdy support you can reach if "
            "needed, but do not hold on to start.",
            "Shift your weight onto one leg and reach both arms forward "
            "while keeping the standing leg steady.",
            "Hold the position, then return to standing on both feet and "
            "repeat on the other side.",
        ],
        "sets": 2,
        "repetitions": None,
        "duration_seconds": 10,
        "progression": "Reach farther forward, or close your eyes briefly while holding.",
        "regression": "Keep a hand on support and reach only slightly forward.",
        "common_mistakes": [
            "Locking the standing knee instead of keeping a soft bend.",
            "Rushing back to two feet at the first sign of a wobble instead "
            "of resetting calmly.",
        ],
        "safety_constraints": [
            "Always perform within reach of a wall or sturdy support.",
            "Stop immediately if you feel unsteady or dizzy.",
        ],
        "movenet_support": _movenet(
            supported=True,
            implemented=True,
            metrics=["durationSeconds", "completion", "symmetry"],
            notes=(
                "The same measurable shape as Supported Single-Leg Stand "
                "and the balance baseline test (one foot lifted, hold "
                "timed), reusing the same kind of detection approach for a "
                "harder, less-supported variant."
            ),
        ),
        "measurable_metrics": ["durationSeconds", "completion", "symmetry"],
        "demonstration_id": "exercise-single-leg-reach-balance",
        "reference": GENERAL_REFERENCE,
    },
]
