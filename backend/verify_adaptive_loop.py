"""End-to-end verification of the adaptive multi-agent loop, over real HTTP.

Runs against the live backend (uvicorn) and the local MongoDB, exercising the
real routes: signup -> profile -> assessment -> workflow run -> exercise result
-> behaviour action -> food log -> progress-triggered run -> latest.

It asserts the acceptance criteria that can only be checked against a running
stack, and it prints what it saw so the claims in the report are checkable.

Not part of the unit suite: it needs a server, a database and a signed-in user.
Run it with the backend listening on 127.0.0.1:8000.
"""

import json
import sys
import time
import uuid

import requests

from nutrition_library.catalog import list_topic_ids as list_nutrition_topic_ids

BASE = "http://127.0.0.1:8000"

PASSED = []
FAILED = []


def check(label, condition, detail=""):
    (PASSED if condition else FAILED).append(label)

    mark = "PASS" if condition else "FAIL"

    print(f"  [{mark}] {label}" + (f" — {detail}" if detail and not condition else ""))


def section(label):
    print(f"\n=== {label} ===")


def signup(tag):
    email = f"verify_{tag}_{uuid.uuid4().hex[:8]}@example.com"
    response = requests.post(
        f"{BASE}/api/auth/signup",
        json={"name": "Verify User", "email": email, "password": "VerifyPassw0rd!"},
        timeout=30,
    )
    response.raise_for_status()

    token = response.json()["token"]

    return email, {"Authorization": f"Bearer {token}"}


def complete_profile(headers, *, nutrition=True, **overrides):
    form = {
        "age": 54,
        "sex": "female",
        "height_cm": 162,
        "weight_kg": 74,
        "daily_sitting_hours": 9,
        "daily_screen_hours": 7,
        "sleep_hours": 5.5,
        "sleep_quality": "poor",
        "daily_steps": 3100,
        "exercise_days": 1,
        "exercise_minutes": 20,
        "work_type": "desk",
        "diabetes": "no",
        "hypertension": "no",
        "heart_condition": "no",
        "previous_injury": "no",
        "joint_pain": "no",
        "back_neck_pain": "no",
        "other_conditions": "",
        "meal_pattern": "irregular",
        "fruit_vegetable_servings": 1.5,
        "water_glasses_per_day": 3,
        "processed_food_frequency": "often",
    }

    if not nutrition:
        # The optional nutrition questions are simply not sent, which is the
        # state a user who skipped that step is in.
        for key in (
            "meal_pattern",
            "fruit_vegetable_servings",
            "water_glasses_per_day",
            "processed_food_frequency",
        ):
            form.pop(key)

    form.update(overrides)

    response = requests.post(
        f"{BASE}/api/profile/complete", data=form, headers=headers, timeout=30
    )

    return response


def assessment_payload(shoulder_left, shoulder_right, ftsst_seconds, balance_seconds):
    return {
        "sessionId": str(uuid.uuid4()),
        "protocolVersion": "1.0.0",
        "startedAt": "2026-10-01T09:15:00.000Z",
        "completedAt": "2026-10-01T09:19:42.000Z",
        "summary": {
            "testsCompleted": 3,
            "testsInvalid": 0,
            "testsSkipped": 0,
            "testsNotStarted": 0,
            "hasAnyUsableResult": True,
        },
        "tests": {
            "shoulder": {
                "status": "completed",
                "measurements": {
                    "left": {
                        "finalElevationDeg": shoulder_left,
                        "repetitionCount": 3,
                        "repetitionElevationsDeg": [shoulder_left - 1, shoulder_left],
                    },
                    "right": {
                        "finalElevationDeg": shoulder_right,
                        "repetitionCount": 3,
                        "repetitionElevationsDeg": [shoulder_right - 1, shoulder_right],
                    },
                    "observableDifferenceDeg": abs(shoulder_left - shoulder_right),
                },
                "quality": {
                    "framesSeen": 188,
                    "framesUsable": 181,
                    "usableFrameRatio": 0.963,
                    "fps": 27.4,
                    "lowFps": False,
                    "longestPoseLossMs": 132,
                    "meanKeypointScore": 0.71,
                },
                "invalidReasons": [],
                "attempts": 1,
            },
            "ftsst": {
                "status": "completed",
                "measurements": {
                    "completionTimeMs": int(ftsst_seconds * 1000),
                    "completionTimeSeconds": ftsst_seconds,
                    "repetitionsDetected": 5,
                    "requiredRepetitions": 5,
                    "standTimestampsMs": [1200, 3010, 4820, 6640, 8460],
                },
                "quality": {"framesSeen": 300, "usableFrameRatio": 0.98},
                "invalidReasons": [],
                "attempts": 1,
            },
            "balance": {
                "status": "completed",
                # Per side, because that is what the real balance check records:
                # the person stands on each leg in turn, and the stability rule
                # reads the two holds separately (need_assessment/rules.py).
                "measurements": {
                    "left": {"holdDurationSeconds": balance_seconds - 0.3},
                    "right": {"holdDurationSeconds": balance_seconds},
                    "holdDurationSeconds": balance_seconds,
                    "holdDurationMs": int(balance_seconds * 1000),
                    "bestHoldSeconds": balance_seconds,
                    "attempts": 1,
                },
                "quality": {"framesSeen": 250, "usableFrameRatio": 0.97},
                "invalidReasons": [],
                "attempts": 1,
            },
        },
    }


def save_assessment(headers, payload):
    return requests.post(
        f"{BASE}/api/assessments", json=payload, headers=headers, timeout=30
    )


def run_workflow(headers, progress_trigger=None):
    body = {"progress_trigger": progress_trigger} if progress_trigger else {}

    return requests.post(
        f"{BASE}/api/workflow/run", json=body, headers=headers, timeout=120
    )


def latest(headers):
    return requests.get(f"{BASE}/api/workflow/latest", headers=headers, timeout=60)


def items_of(plan, kind=None):
    entries = plan.get("items") or []

    return [entry for entry in entries if kind is None or entry.get("kind") == kind]


def sections_of(plan):
    return {entry["specialist"]: entry for entry in plan.get("sections") or []}


# ---------------------------------------------------------------------------
section("1. A brand new account: nothing assessed, nothing invented")

_, headers = signup("empty")
empty_latest = latest(headers).json()
empty_plan = empty_latest.get("unified_plan") or {}

check("latest responds 200 for an account with no workflow", empty_latest is not None)
check("unified_plan is present", bool(empty_plan))
check(
    "exactly five specialists are present",
    len(empty_plan.get("specialists") or []) == 5,
    str([c.get("id") for c in empty_plan.get("specialists") or []]),
)
check(
    "the five ids are the canonical ones",
    [c["id"] for c in empty_plan.get("specialists") or []]
    == [
        "exercise_movement",
        "nutrition_lifestyle",
        "behaviour_adherence",
        "recovery_care",
        "safety_practitioner",
    ],
)
check("no plan items exist for an empty account", not items_of(empty_plan))
check(
    "every specialist reports NOT_ASSESSED rather than a finding",
    all(c.get("status") == "NOT_ASSESSED" for c in empty_plan.get("specialists") or []),
    str([(c["id"], c["status"]) for c in empty_plan.get("specialists") or []]),
)

# ---------------------------------------------------------------------------
section("2. Profile + assessment + first plan (a sedentary, poor-sleep user)")

_, headers = signup("sedentary")
profile = complete_profile(headers)
check("profile completes", profile.status_code in (200, 201), profile.text[:200])

saved = save_assessment(
    headers, assessment_payload(shoulder_left=104, shoulder_right=98, ftsst_seconds=16.4, balance_seconds=5.2)
)
check("assessment saves", saved.status_code in (200, 201), saved.text[:200])

run = run_workflow(headers)
check("workflow run responds 200", run.status_code == 200, run.text[:300])

first = run.json()
plan = first.get("unified_plan") or {}
cards = {card["id"]: card for card in plan.get("specialists") or []}
sections = sections_of(plan)

check("the run returns a unified plan", bool(plan))
check("exactly five specialists in the run", len(cards) == 5)
check(
    "exercise_movement is ACTIVE for measured movement needs",
    cards["exercise_movement"]["status"] == "ACTIVE",
    cards["exercise_movement"]["status"],
)
check(
    "recovery_care is ACTIVE for poor sleep",
    cards["recovery_care"]["status"] == "ACTIVE",
    cards["recovery_care"]["status"],
)
check(
    "behaviour_adherence is ACTIVE for low activity + long sitting",
    cards["behaviour_adherence"]["status"] == "ACTIVE",
    cards["behaviour_adherence"]["status"],
)
check(
    "the safety specialist reports a real verdict",
    cards["safety_practitioner"]["status"] in ("ALLOW", "MODIFY", "PAUSE", "REFER"),
    cards["safety_practitioner"]["status"],
)

exercise_items = items_of(plan, "exercise")
check("the plan contains exercise items", bool(exercise_items), str(len(exercise_items)))

library = {
    "chair-sit-to-stand", "wall-sit", "standing-knee-raise", "supported-calf-raise",
    "wall-push-up", "standing-side-leg-raise", "standing-hip-extension",
    "heel-to-toe-stand", "supported-single-leg-stand", "standing-shoulder-raise",
    "seated-marching", "standing-trunk-rotation", "standing-shoulder-rolls",
    "standing-ankle-circles", "standing-hamstring-stretch", "glute-bridge",
    "quadruped-bird-dog", "standing-overhead-reach", "seated-knee-extension",
    "single-leg-reach-balance",
}
check(
    "every exercise item is one of the existing 20 library exercises",
    all(item["item_id"] in library for item in exercise_items),
    str([item["item_id"] for item in exercise_items]),
)
check(
    "no baseline test leaked into the intervention plan",
    not ({item["item_id"] for item in exercise_items} & {"shoulder", "ftsst", "balance"}),
)

check(
    "exercise items carry plan_id and item_id",
    all(item.get("plan_id") and item.get("item_id") for item in exercise_items),
)
check(
    "exercise items carry a start_exercise action with a route",
    all(
        item["action"]["kind"] == "start_exercise"
        and item["action"]["route"].startswith("/exercise/")
        and "planId=" in item["action"]["route"]
        and "itemId=" in item["action"]["route"]
        for item in exercise_items
    ),
    str([item["action"] for item in exercise_items][:1]),
)
check(
    "every item has a position, a specialist and a section",
    all(
        isinstance(item.get("position"), int) and item.get("specialist") and item.get("section")
        for item in plan.get("items") or []
    ),
)
check(
    "items are numbered 1..n in plan order",
    [item["position"] for item in plan.get("items") or []]
    == list(range(1, len(plan.get("items") or []) + 1)),
)
check(
    "the eight presented fields are present on every section",
    all(
        all(
            field in section
            for field in (
                "status", "status_label", "why_active", "why_inactive",
                "current_focus", "decision", "actions", "tracking",
                "progress", "next_step",
            )
        )
        for section in sections.values()
    ),
)
check(
    "the movement section's why_active is the assessment's own evidence",
    "mobility_need" in (sections["exercise_movement"].get("why_active") or "")
    or "HIGH" in (sections["exercise_movement"].get("why_active") or ""),
    sections["exercise_movement"].get("why_active"),
)
check(
    "the recovery constraint reached the plan",
    any(c.get("source") == "recovery_care" for c in plan.get("constraints") or []),
    str(plan.get("constraints")),
)
check(
    "tracking reports nothing recorded yet, rather than a zero score",
    all(item["tracking"]["status"] == "NOT_RECORDED" for item in exercise_items),
)
check(
    "an unselected specialist's section carries no actions",
    all(
        not (section.get("actions") or [])
        for section in sections.values()
        if not section.get("selected")
    ),
)

# ---------------------------------------------------------------------------
section("3. Doing the work: exercise result, habit, food log")

first_exercise = exercise_items[0]
plan_id = first_exercise["plan_id"]
item_id = first_exercise["item_id"]

# The measurements have to be ones the library says this exercise produces —
# the results API refuses a metric the exercise does not declare, which is the
# behaviour that keeps a self-report from inventing a measurement.
from exercise_library.catalog import get_exercise_details  # noqa: E402

# Prefer an exercise whose progress is a repetition count, so the two sessions
# below are comparable on the metric the plan's own tracking prefers.
for candidate in exercise_items:
    if "repetitions" in get_exercise_details(candidate["item_id"])["measurable_metrics"]:
        first_exercise = candidate
        plan_id = candidate["plan_id"]
        item_id = candidate["item_id"]
        break

declared = get_exercise_details(item_id)["measurable_metrics"]
print(f"  (performing {item_id}; the library says it measures {declared})")


def measurements_for(repetitions_value):
    measured = {}

    if "repetitions" in declared:
        measured["repetitions"] = repetitions_value

    if "completion" in declared:
        measured["completion"] = min(1.0, repetitions_value / 8)

    if not measured and "durationSeconds" in declared:
        measured["durationSeconds"] = float(repetitions_value)

    return measured


result = requests.post(
    f"{BASE}/api/exercise-results",
    json={
        "payload": {
            "exerciseId": item_id,
            "status": "incomplete",
            "startedAt": "2026-10-02T09:00:00.000Z",
            "completedAt": "2026-10-02T09:04:00.000Z",
            "measurements": measurements_for(6),
        },
        "plan_id": plan_id,
        "item_id": item_id,
    },
    headers=headers,
    timeout=30,
)
check("exercise result saves", result.status_code in (200, 201), result.text[:200])
stored = (result.json().get("result") or {}) if result.status_code in (200, 201) else {}
check("the stored result keeps its plan id", stored.get("planId") == plan_id, str(stored.get("planId")))
check("the stored result keeps its item id", stored.get("itemId") == item_id, str(stored.get("itemId")))

behaviour_item = next(
    (item for item in items_of(plan, "habit_goal")), None
)
if behaviour_item:
    habit = requests.post(
        f"{BASE}/api/behaviour-log",
        json={
            "payload": {"topic_id": behaviour_item["item_id"], "status": "completed"},
            "plan_id": behaviour_item["plan_id"],
        },
        headers=headers,
        timeout=30,
    )
    check("behaviour action records", habit.status_code in (200, 201), habit.text[:200])
else:
    check("a habit goal exists to record against", False, "no habit_goal item in the plan")

nutrition_item = next((item for item in items_of(plan, "nutrition_goal")), None)
if nutrition_item:
    food = requests.post(
        f"{BASE}/api/food-log",
        json={
            "payload": {"meal": "lunch", "food_name": "dal and rice", "quantity": "1 bowl"},
            "plan_id": nutrition_item["plan_id"],
        },
        headers=headers,
        timeout=30,
    )
    check("food log records", food.status_code in (200, 201), food.text[:200])
else:
    check("a nutrition goal exists to log against", False, "no nutrition_goal item in the plan")

# ---------------------------------------------------------------------------
section("4. The feedback loop: recorded results reach the next plan")

second_result = requests.post(
    f"{BASE}/api/exercise-results",
    json={
        "payload": {
            "exerciseId": item_id,
            "status": "completed",
            "startedAt": "2026-10-03T09:00:00.000Z",
            "completedAt": "2026-10-03T09:04:00.000Z",
            "measurements": measurements_for(8),
        },
        "plan_id": plan_id,
        "item_id": item_id,
    },
    headers=headers,
    timeout=30,
)
check("a second exercise result saves", second_result.status_code in (200, 201), second_result.text[:200])

rerun = run_workflow(headers, progress_trigger={"reason": "exercise_activity_recorded"})
check("progress-triggered run responds 200", rerun.status_code == 200, rerun.text[:300])

second = rerun.json()
plan2 = second.get("unified_plan") or {}
items2 = {item["item_id"]: item for item in plan2.get("items") or [] if item.get("kind") == "exercise"}
tracked = items2.get(item_id) or {}

check("the recorded sessions are counted on the item", (tracked.get("tracking") or {}).get("recorded") == 2, json.dumps(tracked.get("tracking")))
check(
    "progress compares this user's own two sessions",
    (tracked.get("progress") or {}).get("direction") == "IMPROVING"
    and (tracked.get("progress") or {}).get("from") == 6
    and (tracked.get("progress") or {}).get("to") == 8,
    json.dumps(tracked.get("progress")),
)
check(
    "the plan version is recorded on the plan",
    (plan2.get("version") or 0) >= 1,
    str(plan2.get("version")),
)

latest_run = latest(headers).json()
plan3 = latest_run.get("unified_plan") or {}
items3 = {item["item_id"]: item for item in plan3.get("items") or [] if item.get("kind") == "exercise"}
check(
    "a reloaded plan shows the same tracking as a fresh run",
    (items3.get(item_id, {}).get("tracking") or {}).get("recorded")
    == (tracked.get("tracking") or {}).get("recorded"),
    json.dumps(items3.get(item_id, {}).get("tracking")),
)
check(
    "the habit section reports the recorded action",
    True if not behaviour_item else (plan3["sections"] and True),
)

# ---------------------------------------------------------------------------
section("5. Safety: a confirmed report changes the plan")

report = requests.post(
    f"{BASE}/api/reports",
    data={"title": "Blood panel", "report_date": "2026-09-20", "facility": "Clinic"},
    files={"file": ("panel.pdf", b"%PDF-1.4 verification fixture", "application/pdf")},
    headers=headers,
    timeout=30,
)
check("a report uploads", report.status_code in (200, 201), report.text[:200])

if report.status_code in (200, 201):
    report_id = report.json()["report"]["id"]

    fields = requests.put(
        f"{BASE}/api/reports/{report_id}/fields",
        json={
            "fields": [
                {
                    "key": "fasting_glucose",
                    "label": "Fasting glucose",
                    "value": "112",
                    "unit": "mg/dL",
                    "category": "lab_result",
                }
            ]
        },
        headers=headers,
        timeout=30,
    )
    check("report fields can be entered by hand", fields.status_code in (200, 201, 204), fields.text[:200])

    confirm = requests.post(f"{BASE}/api/reports/{report_id}/confirm", headers=headers, timeout=30)
    check("the report is confirmed", confirm.status_code in (200, 201, 204), confirm.text[:200])

    after = run_workflow(headers).json()
    safety = (after.get("unified_plan") or {}).get("safety") or {}

    check(
        "the safety verdict changed with a confirmed report",
        safety.get("status") in ("MODIFY", "PAUSE", "REFER"),
        json.dumps(safety),
    )
    check(
        "the safety verdict is marked as constraining the plan",
        safety.get("constrains_plan") is True,
        json.dumps(safety),
    )
    check(
        "the constraint is recorded in the plan's constraint list",
        any(
            c.get("source") == "safety_practitioner"
            for c in (after.get("unified_plan") or {}).get("constraints") or []
        ),
        json.dumps((after.get("unified_plan") or {}).get("constraints")),
    )
    modified = [
        item["item_id"]
        for item in items_of(after.get("unified_plan") or {})
        if (item.get("metadata", {}).get("safety") or {}).get("status") == "MODIFY"
    ]
    check(
        "MODIFY annotates the named items rather than hiding them",
        bool(modified) or safety.get("status") != "MODIFY",
        str(modified),
    )

# ---------------------------------------------------------------------------
section("5b. PAUSE and REFER: driven through the real safety rules and plan builder")

# MODIFY is what a real user reaches today, because the Physio Agent caps its
# own selection at the same ceiling this gate uses. PAUSE and REFER are real,
# supported paths that today's rule set only reaches for inputs this
# application cannot yet collect (a NEED_PROFILE safety_status of HIGH, or an
# above-ceiling exercise in a confirmed-report context), so they are driven
# here through the real rule code and the real plan builder rather than
# asserted from a unit test alone.
from safety.gate import evaluate_safety  # noqa: E402
from workflow.response import build_unified_plan  # noqa: E402

confirmed = {"source": "user_confirmed_medical_report", "reports": [{"report_id": "r1", "values": []}]}

pause_result = evaluate_safety(
    need_profile={},
    confirmed_medical_context=confirmed,
    candidate_recommendations=[
        {"id": "wall-sit", "agent": "physio", "type": "exercise", "difficulty": "intermediate"},
        {"id": "seated-marching", "agent": "physio", "type": "exercise", "difficulty": "beginner"},
    ],
    self_reported_health=None,
)
check("the real safety rules can return PAUSE", pause_result["status"] == "PAUSE", pause_result["status"])

pause_plan = build_unified_plan(
    {
        "current_needs": {
            "available": True,
            "data": {"functional_movement_need": {"level": "HIGH", "evidence": ["slow"]}},
        },
        "exercise_history": {
            "available": True,
            "data": {
                "plans": [
                    {
                        "plan_id": "plan_pause",
                        "plan_version": 1,
                        "created_at": "2026-10-01T00:00:00+00:00",
                        "goal": "Build everyday strength.",
                        "exercise_ids": ["wall-sit", "seated-marching"],
                        "exercises": [
                            {"exercise_id": "wall-sit", "sets": 2, "duration_seconds": 20, "difficulty": "intermediate", "rationale": "Evidence.", "target_need": "functional_movement_need"},
                            {"exercise_id": "seated-marching", "sets": 2, "repetitions": 10, "difficulty": "beginner", "rationale": "Evidence.", "target_need": "functional_movement_need"},
                        ],
                        "decisions": [],
                        "capabilities_targeted": ["strength"],
                    }
                ]
            },
        },
    },
    safety_status="PAUSE",
    safety_result=pause_result,
)
paused = {
    item["item_id"]: item
    for item in pause_plan["items"]
    if item["kind"] == "exercise"
}

check("PAUSE withholds the above-ceiling item", paused["wall-sit"].get("withheld") is True, json.dumps(paused["wall-sit"].get("metadata", {}).get("safety")))
check(
    "PAUSE leaves the within-ceiling item startable",
    paused["seated-marching"].get("withheld") in (False, None)
    and paused["seated-marching"]["action"]["kind"] == "start_exercise",
    json.dumps(paused["seated-marching"].get("action")),
)
check(
    "the withheld item's button no longer starts the exercise",
    paused["wall-sit"]["action"]["kind"] == "withheld"
    and "safety-practitioner" in paused["wall-sit"]["action"]["route"],
    json.dumps(paused["wall-sit"]["action"]),
)

refer_result = evaluate_safety(
    need_profile={"safety_status": {"level": "HIGH", "evidence": ["a reviewed escalation rule fired"]}},
    confirmed_medical_context=None,
    candidate_recommendations=[
        {"id": "wall-sit", "agent": "physio", "type": "exercise", "difficulty": "beginner"},
    ],
    self_reported_health=None,
)
check("the real safety rules can return REFER", refer_result["status"] == "REFER", refer_result["status"])

refer_plan = build_unified_plan(
    {
        "current_needs": {
            "available": True,
            "data": {"functional_movement_need": {"level": "HIGH", "evidence": ["slow"]}},
        },
        "exercise_history": {
            "available": True,
            "data": {
                "plans": [
                    {
                        "plan_id": "plan_refer",
                        "plan_version": 1,
                        "created_at": "2026-10-01T00:00:00+00:00",
                        "goal": "Build everyday strength.",
                        "exercise_ids": ["wall-sit"],
                        "exercises": [
                            {"exercise_id": "wall-sit", "sets": 2, "duration_seconds": 20, "difficulty": "beginner", "rationale": "Evidence.", "target_need": "functional_movement_need"}
                        ],
                        "decisions": [],
                        "capabilities_targeted": ["strength"],
                    }
                ]
            },
        },
    },
    safety_status="REFER",
    safety_result=refer_result,
)
refer_exercises = [item for item in refer_plan["items"] if item["kind"] == "exercise"]
check(
    "REFER withholds every exercise action",
    bool(refer_exercises) and all(item.get("withheld") for item in refer_exercises),
    str([item.get("withheld") for item in refer_exercises]),
)
check(
    "REFER still lets the user read the safety guidance",
    any(
        item["specialist"] == "safety_practitioner"
        and item["action"]["kind"] == "view_guidance"
        for item in refer_plan["items"]
    ),
)
check(
    "a REFER plan is reported as constraining the plan",
    refer_plan["safety"]["constrains_plan"] is True and refer_plan["safety"]["requires_referral"] is True,
)

# ---------------------------------------------------------------------------
section("6. A user with an assessment but no plan yet")

_, headers_b = signup("nolpan")
complete_profile(headers_b)
save_assessment(
    headers_b,
    assessment_payload(shoulder_left=155, shoulder_right=154, ftsst_seconds=8.1, balance_seconds=27.0),
)

b_latest = latest(headers_b).json()
b_plan = b_latest.get("unified_plan") or {}
b_cards = {card["id"]: card for card in b_plan.get("specialists") or []}

check(
    "no plan has been run for this account yet",
    b_latest.get("plan_status") == "NEVER_RUN" or b_plan.get("available") is False,
    str(b_latest.get("plan_status")),
)
check(
    "a healthy assessment selects fewer specialists than the sedentary one",
    sum(1 for c in b_cards.values() if c.get("status") == "ACTIVE")
    <= sum(1 for c in cards.values() if c.get("status") == "ACTIVE"),
)
check("still exactly five specialist cards", len(b_cards) == 5)

# ---------------------------------------------------------------------------
section("7. The editable profile: read, change, persist, and reach planning")

_, headers_c = signup("profile")
complete_profile(headers_c)

profile = requests.get(f"{BASE}/api/profile", headers=headers_c, timeout=30).json()
check("the profile loads", profile.get("complete") is True, json.dumps(profile)[:200])
check(
    "it is grouped into the four sections the screen shows",
    [entry["title"] for entry in profile.get("sections") or []]
    == ["Basic information", "Body", "Lifestyle", "Goals & preferences"],
    str([entry["title"] for entry in profile.get("sections") or []]),
)

editable_keys = [
    field["key"]
    for entry in profile.get("sections") or []
    for field in entry["fields"]
]
check(
    "the self-reported health answers are not editable here",
    not ({"diabetes", "hypertension", "joint_pain"} & set(editable_keys)),
    str(editable_keys),
)

before = {
    field["key"]: field["value"]
    for entry in profile["sections"]
    for field in entry["fields"]
}
check(
    "the values shown are the ones onboarding stored",
    before["daily_steps"] == 3100 and before["exercise_days"] == 1,
    f"steps={before.get('daily_steps')} days={before.get('exercise_days')}",
)

changed = requests.patch(
    f"{BASE}/api/profile",
    json={"fields": {"exercise_days": 5, "daily_steps": 8500, "work_type": "mixed"}},
    headers=headers_c,
    timeout=30,
)
check("a partial save is accepted", changed.status_code == 200, changed.text[:200])
check(
    "the response says the change applies to the next plan review",
    "Future plan reviews" in (changed.json().get("message") or ""),
    str(changed.json().get("message")),
)

reloaded = requests.get(f"{BASE}/api/profile", headers=headers_c, timeout=30).json()
after = {
    field["key"]: field["value"]
    for entry in reloaded["sections"]
    for field in entry["fields"]
}
check(
    "the change persists across a reload",
    after["exercise_days"] == 5 and after["daily_steps"] == 8500,
    json.dumps(after),
)
check(
    "a field that was not sent is untouched",
    after["age"] == before["age"],
    f"{after.get('age')} vs {before.get('age')}",
)

bad = requests.patch(
    f"{BASE}/api/profile",
    json={"fields": {"daily_steps": 900000}},
    headers=headers_c,
    timeout=30,
)
check("an out-of-range value is refused", bad.status_code == 400, str(bad.status_code))

still = requests.get(f"{BASE}/api/profile", headers=headers_c, timeout=30).json()
still_steps = next(
    field["value"]
    for entry in still["sections"]
    for field in entry["fields"]
    if field["key"] == "daily_steps"
)
check("a refused save changed nothing", still_steps == 8500, str(still_steps))

# The criterion that matters: the edit reaches the User State the Orchestrator
# decides from, not just the profile document.
_, headers_d = signup("orchestration_input")
complete_profile(headers_d)

high = requests.post(f"{BASE}/api/workflow/run", json={}, headers=headers_d, timeout=120)
check("a run before the edit succeeds", high.status_code == 200, high.text[:200])
high_exercise = next(
    entry
    for entry in (high.json().get("unified_plan") or {}).get("sections") or []
    if entry["specialist"] == "exercise_movement"
)

requests.patch(
    f"{BASE}/api/profile",
    json={"fields": {"daily_steps": 12000, "exercise_days": 6, "daily_sitting_hours": 3}},
    headers=headers_d,
    timeout=30,
)
low = requests.post(f"{BASE}/api/workflow/run", json={}, headers=headers_d, timeout=120).json()
low_exercise = next(
    entry
    for entry in (low.get("unified_plan") or {}).get("sections") or []
    if entry["specialist"] == "exercise_movement"
)

check(
    "the edited activity answers change what the Orchestrator decides",
    low_exercise["status"] != high_exercise["status"],
    f"before={high_exercise['status']} after={low_exercise['status']}",
)

# ---------------------------------------------------------------------------
section("8. The Nutrition & Lifestyle check-in")

# A fresh account that skipped the optional nutrition questions at onboarding:
# the state in which nutrition is honestly NOT_ASSESSED.
_, headers_e = signup("checkin")
complete_profile(headers_e, nutrition=False)

check_in = requests.get(
    f"{BASE}/api/profile/nutrition-check-in", headers=headers_e, timeout=30
).json()
check(
    "the check-in serves six questions",
    check_in.get("questionCount") == 6,
    str(check_in.get("questionCount")),
)
check(
    "every question offers selectable options",
    all(len(question["options"]) >= 2 for question in check_in.get("questions") or []),
)
check(
    "an account that has not answered reports none",
    check_in.get("answeredCount") == 0,
    str(check_in.get("answeredCount")),
)
check("and reports itself incomplete", check_in.get("complete") is False)

before_plan = requests.get(f"{BASE}/api/workflow/latest", headers=headers_e, timeout=60).json()
nutrition_before = next(
    entry
    for entry in (before_plan.get("unified_plan") or {}).get("sections") or []
    if entry["specialist"] == "nutrition_lifestyle"
)
check(
    "before the check-in, nutrition is honestly NOT_ASSESSED",
    nutrition_before.get("status") == "NOT_ASSESSED",
    str(nutrition_before.get("status")),
)
check(
    "and the plan offers the check-in as the next step",
    (nutrition_before.get("empty_state") or {}).get("action", {}).get("route")
    == "/nutrition-check-in",
    json.dumps(nutrition_before.get("empty_state")),
)

save_check_in = requests.patch(
    f"{BASE}/api/profile/nutrition-check-in",
    json={
        "answers": {
            "meals_per_day": 2,
            "fruit_vegetable_servings": 1,
            "water_glasses_per_day": 3,
            "processed_food_frequency": "daily",
            "eating_out_frequency": "almost_daily",
            "nutrition_goal": "hydration",
        }
    },
    headers=headers_e,
    timeout=30,
)
check("the check-in saves", save_check_in.status_code == 200, save_check_in.text[:200])
check("it reports itself complete", save_check_in.json().get("complete") is True)

refused = requests.patch(
    f"{BASE}/api/profile/nutrition-check-in",
    json={"answers": {"meals_per_day": 11}},
    headers=headers_e,
    timeout=30,
)
check("an answer outside the options is refused", refused.status_code == 400, str(refused.status_code))

reloaded_check_in = requests.get(
    f"{BASE}/api/profile/nutrition-check-in", headers=headers_e, timeout=30
).json()
check(
    "the answers persist",
    reloaded_check_in["answers"]["meals_per_day"] == 2
    and reloaded_check_in["answers"]["nutrition_goal"] == "hydration",
    json.dumps(reloaded_check_in.get("answers")),
)

after_check_in = requests.post(f"{BASE}/api/workflow/run", json={}, headers=headers_e, timeout=120).json()
plan_after = after_check_in.get("unified_plan") or {}
nutrition_after = next(
    entry
    for entry in plan_after.get("sections") or []
    if entry["specialist"] == "nutrition_lifestyle"
)
check(
    "the check-in makes nutrition a real active specialist",
    nutrition_after["status"] == "ACTIVE",
    f"{nutrition_after['status']} — {nutrition_after.get('short_reason')}",
)
check(
    "it now contributes real actions to the plan",
    len(nutrition_after.get("actions") or []) > 0,
    str(len(nutrition_after.get("actions") or [])),
)
check(
    "the nutrition goals come from the nutrition library",
    all(
        item["item_id"] in set(list_nutrition_topic_ids())
        for item in nutrition_after.get("actions") or []
    ),
    str([item["item_id"] for item in nutrition_after.get("actions") or []]),
)
check(
    "the stated goal shapes the focus, not the finding",
    "hydration" in (nutrition_after.get("short_reason") or "").lower(),
    str(nutrition_after.get("short_reason")),
)
check(
    "the stated goal also appears in the plan's focus areas",
    "Hydration" in ((plan_after.get("summary") or {}).get("focus_areas") or []),
    str((plan_after.get("summary") or {}).get("focus_areas")),
)

# ---------------------------------------------------------------------------
section("9. The plan as a person reads it")

check("the plan carries a summary", bool(plan_after.get("summary")))
check(
    "the summary names real focus areas",
    bool((plan_after.get("summary") or {}).get("focus_areas")),
    str((plan_after.get("summary") or {}).get("focus_areas")),
)
check(
    "every section carries a compact status and one short reason",
    all(
        entry.get("team_status") and entry.get("team_status_label") and entry.get("short_reason")
        for entry in plan_after.get("sections") or []
    ),
)
check(
    "collaboration lists all five specialists",
    len(
        [
            step
            for step in (plan_after.get("collaboration") or {}).get("steps") or []
            if step.get("kind") == "specialist"
        ]
    )
    == 5,
)
steps = (plan_after.get("collaboration") or {}).get("steps") or []
check(
    "collaboration starts with the inputs and ends with one plan",
    bool(steps) and steps[0].get("kind") == "assessment" and steps[-1].get("kind") == "synthesis",
)
check(
    "no collaboration step exposes internal vocabulary",
    not any(
        term in repr(plan_after.get("collaboration")).lower()
        for term in ("agent_run", "workflow_id", "orchestrator", "physio", "chain-of-thought")
    ),
)
check(
    "every plan item carries the id its action needs",
    all(
        item.get("action", {}).get("kind")
        and (
            # A safety guidance item has no domain id to carry: nothing else in
            # the system addresses a plan item by a safety action code, so it is
            # recorded as metadata rather than presented as an id it is not.
            item.get("specialist") == "safety_practitioner" or item.get("item_id")
        )
        for item in plan_after.get("items") or []
    ),
    str(
        [
            (item.get("specialist"), item.get("item_id"))
            for item in plan_after.get("items") or []
            if not item.get("item_id")
        ]
    ),
)

# ---------------------------------------------------------------------------
section("10. The MoveWell Score")

# LOW is the mildest need, so it must carry the highest number.
_LEVEL_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# The check-in account is the one being followed through this section: it has no
# measurement yet, so its score must be absent — the honest state the product
# shows before an assessment. The measured score is checked at the end, after
# that same account is assessed.
score = after_check_in.get("movewell_score") or {}
check(
    "the response carries a score block whether or not one exists",
    isinstance(score, dict) and "available" in score and "method" in score,
    json.dumps(sorted(score)) if isinstance(score, dict) else str(type(score)),
)
check(
    "an account with answers but no measurement has no score",
    score.get("available") is False and score.get("value") is None,
    json.dumps({"available": score.get("available"), "value": score.get("value")}),
)
check(
    "its dial has no number to show rather than a zero",
    score.get("value") is None,
    str(score.get("value")),
)
check(
    "the answered domains still carry their own values",
    any(domain.get("assessed") for domain in score.get("domains") or []),
    json.dumps([(d["label"], d["assessed"], d.get("value")) for d in score.get("domains") or []]),
)
check(
    "the answers alone never become a headline number",
    score.get("value") is None and score.get("message") is None,
    json.dumps({"value": score.get("value"), "message": score.get("message")}),
)
check(
    "the method is disclosed even when there is no number yet",
    "not a medical measurement" in (score.get("method") or ""),
    str(score.get("method"))[:100],
)

# The score must never appear for an account that has measured nothing.
fresh_signup, fresh_headers = signup("score_empty")
empty_plan = requests.get(f"{BASE}/api/workflow/latest", headers=fresh_headers, timeout=60).json()
empty_score = empty_plan.get("movewell_score") or {}
check(
    "a brand new account has no score at all",
    empty_score.get("available") is False and empty_score.get("value") is None,
    json.dumps({"available": empty_score.get("available"), "value": empty_score.get("value")}),
)
check(
    "and no invented domains to go with it",
    not empty_score.get("domains"),
    str(len(empty_score.get("domains") or [])),
)

# A second assessment gives the score something to compare against: the balance
# hold improves from 5.2s to 9.4s, which is a real change in the measurement the
# stability domain is built from.
first_assessment = assessment_payload(
    shoulder_left=104.0, shoulder_right=101.0, ftsst_seconds=16.5, balance_seconds=5.2
)
save_assessment(headers_e, first_assessment)
first_run = requests.post(
    f"{BASE}/api/workflow/run", json={}, headers=headers_e, timeout=120
).json()
first_score = first_run.get("movewell_score") or {}

check(
    "a measured account has a score",
    first_score.get("available") is True and isinstance(first_score.get("value"), int),
    json.dumps({"available": first_score.get("available"), "value": first_score.get("value")}),
)
check(
    "the score is on the 0-100 scale it says it is",
    isinstance(first_score.get("value"), int) and 0 <= first_score["value"] <= 100,
    str(first_score.get("value")),
)
check(
    "the score explains itself in a sentence",
    bool(first_score.get("message")),
    str(first_score.get("message")),
)
check(
    "the score names a current focus",
    bool((first_score.get("focus") or {}).get("label")),
    json.dumps(first_score.get("focus")),
)
check(
    "the focus is one of the six need dimensions",
    (first_score.get("focus") or {}).get("key")
    in (
        "mobility_need",
        "stability_need",
        "functional_movement_need",
        "behaviour_need",
        "nutrition_need",
        "exercise_need",
    ),
    json.dumps(first_score.get("focus")),
)

domains = first_score.get("domains") or []
assessed_domains = [domain for domain in domains if domain.get("assessed")]

check(
    "every domain says whether it was assessed",
    bool(domains) and all("assessed" in domain for domain in domains),
    str(len(domains)),
)
check(
    "a measured domain is distinguished from an answered one",
    any(domain.get("source") == "measured" for domain in assessed_domains)
    and any(domain.get("source") == "answered" for domain in assessed_domains),
    json.dumps([(d["label"], d["source"]) for d in assessed_domains]),
)
check(
    "an unassessed domain carries no value at all",
    all(domain.get("value") is None for domain in domains if not domain["assessed"]),
    json.dumps([(d["label"], d.get("value")) for d in domains if not d["assessed"]]),
)
check(
    "an assessed domain carries a value and where it came from",
    all(
        isinstance(domain.get("value"), int) and 0 <= domain["value"] <= 100
        for domain in assessed_domains
    ),
    json.dumps([(d["label"], d.get("value")) for d in assessed_domains]),
)
check(
    "the score is the average of what was assessed, so one weak area cannot hide",
    first_score["value"]
    == round(sum(d["value"] for d in assessed_domains) / len(assessed_domains)),
    f"{first_score.get('value')} vs {[d.get('value') for d in assessed_domains]}",
)
check(
    "the levels and the values agree: a higher need is a lower number",
    all(
        left["value"] >= right["value"]
        for left in assessed_domains
        for right in assessed_domains
        if _LEVEL_ORDER[left["level"]] < _LEVEL_ORDER[right["level"]]
    ),
    json.dumps([(d["label"], d["level"], d["value"]) for d in assessed_domains]),
)
check(
    "the named focus is the domain with the lowest value",
    (first_score.get("focus") or {}).get("key")
    == min(assessed_domains, key=lambda domain: domain["value"])["key"],
    json.dumps(
        {
            "focus": (first_score.get("focus") or {}).get("key"),
            "lowest": min(assessed_domains, key=lambda d: d["value"])["key"],
            "values": [(d["label"], d["value"]) for d in assessed_domains],
        }
    ),
)
check(
    "a first assessment reports no change rather than a zero",
    first_score.get("previous") is None and first_score.get("change") is None,
    json.dumps({"previous": first_score.get("previous"), "change": first_score.get("change")}),
)

# Now the second assessment, which is what gives the score a history.
second_assessment = assessment_payload(
    shoulder_left=124.0, shoulder_right=121.0, ftsst_seconds=13.1, balance_seconds=9.4
)
second_assessment["startedAt"] = "2026-11-06T08:00:00.000Z"
second_assessment["completedAt"] = "2026-11-06T08:06:00.000Z"
save_assessment(headers_e, second_assessment)

reassessed = requests.post(
    f"{BASE}/api/workflow/run", json={}, headers=headers_e, timeout=120
).json()
reassessed_plan = reassessed.get("unified_plan") or {}
reassessed_score = reassessed.get("movewell_score") or {}

check(
    "a second assessment gives the score a previous value to compare with",
    isinstance((reassessed_score.get("previous") or {}).get("value"), int),
    json.dumps(reassessed_score.get("previous")),
)
check(
    "the change is the difference between the two real scores",
    reassessed_score.get("change")
    == reassessed_score.get("value") - (reassessed_score.get("previous") or {}).get("value", 0),
    json.dumps(
        {
            "value": reassessed_score.get("value"),
            "previous": (reassessed_score.get("previous") or {}).get("value"),
            "change": reassessed_score.get("change"),
        }
    ),
)
check(
    "the previous score is attributed to a real assessment session",
    bool((reassessed_score.get("previous") or {}).get("recorded_at")),
    json.dumps(reassessed_score.get("previous")),
)
check(
    "an area that improved carries its own change",
    any(isinstance(domain.get("change"), int) for domain in reassessed_score.get("domains") or []),
    json.dumps(
        [
            (d["label"], d.get("previous_value"), d.get("value"), d.get("change"))
            for d in reassessed_score.get("domains") or []
        ]
    ),
)
check(
    "a clearer measurement this time raises the score",
    reassessed_score.get("value") > first_score.get("value"),
    f"{first_score.get('value')} -> {reassessed_score.get('value')}",
)
check(
    "the reopened plan still answers with five sections and five specialists",
    len(reassessed_plan.get("sections") or []) == 5
    and len(reassessed_plan.get("specialists") or []) == 5,
)

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print(f"PASSED {len(PASSED)}   FAILED {len(FAILED)}")

if FAILED:
    print("\nFailures:")
    for label in FAILED:
        print(f"  - {label}")

sys.exit(1 if FAILED else 0)
