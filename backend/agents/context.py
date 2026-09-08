"""Assembling what an agent is allowed to know.

Every agent in this application reads its input from here, and from nowhere
else. That single entry point is what makes the promises in this project
checkable rather than aspirational.

Three rules are enforced by construction.

Only confirmed report values enter. The report pipeline hands over
`confirmed_values_for_user`, which refuses to serialise anything the user has
not confirmed, so a candidate value has no route into this module at all. If a
user has reports sitting unreviewed, that fact is reported as a gap rather than
quietly filled in.

Nothing is interpreted on the way through. A number arrives with the same
meaning it left the store with, plus a label saying where it came from and what
it is not. No score is computed, no value is compared against a range, and no
missing value is estimated. `context_digest` renders the context as prose for a
model, and that rendering is the only thing a model ever sees — a database
document is never serialised into a prompt.

Gaps are stated. Absent profile answers, a skipped movement test, an invalid
one and a user with no reports are four different situations, and each is named.
An agent that is told "no balance measurement exists" can say so; an agent
handed a silent zero cannot.

This module deliberately imports nothing outside the standard library. What data
crosses the boundary into an AI prompt is the part of this system that most
needs to be testable, so it is kept free of FastAPI, pymongo and the database.
The reads that feed it live in agents/sources.py.
"""

import hashlib
import json
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Source labels
#
# Attached to every group of values and repeated in the digest. Three kinds of
# information with three very different standings are being combined here, and
# an agent that cannot tell them apart will write "your sitting time is 8 hours"
# about a number the user estimated once during signup.
# ---------------------------------------------------------------------------

SOURCE_SELF_REPORTED = "self_reported_onboarding"
SOURCE_WEBCAM_OBSERVATION = "webcam_movement_observation"
SOURCE_USER_CONFIRMED_REPORT = "user_confirmed_medical_report"

SOURCE_DESCRIPTIONS = {
    SOURCE_SELF_REPORTED: (
        "answers the user typed in during setup. Self-reported estimates, not "
        "measurements, and possibly out of date"
    ),
    SOURCE_WEBCAM_OBSERVATION: (
        "movement observed through an ordinary webcam by a pose-estimation "
        "model. Observations of what the movement looked like on camera, not "
        "clinical measurements and not taken by a clinician"
    ),
    SOURCE_USER_CONFIRMED_REPORT: (
        "values transcribed from the user's own medical report and then checked "
        "and confirmed by the user themselves"
    ),
}


# ---------------------------------------------------------------------------
# Profile
#
# The fields named here are the ones the guidance layer consumes. The list is
# written out rather than derived from whatever the profile document happens to
# contain, because forwarding a whole document is how a birth date or a free
# text note ends up in a prompt that had no use for it. A new profile field is
# simply not sent to an agent until it is added here on purpose.
# ---------------------------------------------------------------------------

PROFILE_FIELDS = (
    ("age", "Age", "years"),
    ("sex", "Sex", None),
    ("bmi", "Body mass index", None),
    ("work_type", "Type of work", None),
    ("daily_sitting_hours", "Time spent sitting on a typical day", "hours"),
    ("daily_screen_hours", "Time spent looking at a screen on a typical day", "hours"),
    ("daily_steps", "Steps on a typical day", "steps"),
    ("sleep_hours", "Sleep on a typical night", "hours"),
    ("sleep_quality", "How the user rates their sleep", None),
    ("exercise_days", "Days a week with deliberate exercise", "days"),
    ("exercise_minutes", "Minutes of exercise on those days", "minutes"),
)

# camelCase spellings are accepted too, so the builder works whether it is
# handed the stored document or the API's serialised version of it.
PROFILE_ALIASES = {
    "daily_sitting_hours": "dailySittingHours",
    "daily_screen_hours": "dailyScreenHours",
    "daily_steps": "dailySteps",
    "sleep_hours": "sleepHours",
    "sleep_quality": "sleepQuality",
    "exercise_days": "exerciseDays",
    "exercise_minutes": "exerciseMinutes",
    "work_type": "workType",
}


# ---------------------------------------------------------------------------
# Movement tests
#
# Each entry says what the test observed and, just as importantly, what the
# observation is not. The caveats travel with the numbers into the prompt, so an
# agent cannot receive "142 degrees" without also receiving "an angle measured
# in the camera's flat image, not a clinical range of motion".
# ---------------------------------------------------------------------------

TEST_DESCRIPTIONS = {
    "shoulder": {
        "name": "Both arms raised out to the side",
        "observes": (
            "how far each arm appeared to lift away from the body, as an angle "
            "in the flat image the camera produced"
        ),
        "is_not": (
            "a clinical range of motion measurement, a strength measurement, or "
            "anything about the shoulder joint itself"
        ),
    },
    "ftsst": {
        "name": "Standing up from a chair five times",
        "observes": (
            "how long the five repetitions took, timed automatically from the "
            "knee angle the camera could see"
        ),
        "is_not": (
            "a clinician-timed test, a leg strength measurement, or a fitness "
            "score. The timing was started and stopped by software watching the "
            "video, and the chair was whatever the user had"
        ),
    },
    "balance": {
        "name": "Standing on one leg with eyes open",
        "observes": (
            "how long the user held the position on each leg before the camera "
            "saw the position break, up to the time limit"
        ),
        "is_not": (
            "a balance disorder screen, a fall risk score, or a neurological "
            "assessment"
        ),
    },
}

TEST_ORDER = ("shoulder", "ftsst", "balance")

STATUS_EXPLANATIONS = {
    "completed": "completed, and produced measurements",
    "invalid": (
        "attempted, but the recording did not meet the conditions the test "
        "needs, so it produced no usable measurement"
    ),
    "skipped": "deliberately skipped by the user, so no measurement exists",
    "not_started": "never reached, so no measurement exists",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(source, key: str):
    """Read a field by its stored name or its camelCase spelling."""

    if not isinstance(source, dict):
        return None

    if source.get(key) is not None:
        return source[key]

    alias = PROFILE_ALIASES.get(key)

    if alias and source.get(alias) is not None:
        return source[alias]

    return None


def _number(value):
    """Round for display without changing what the value is.

    Long floating point tails in a prompt invite a model to treat a number as
    more precise than it is, and 8.199999999999999 hours of sitting is not a
    more truthful figure than 8.2.
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value

    if isinstance(value, int):
        return value

    rounded = round(value, 2)

    return int(rounded) if rounded == int(rounded) else rounded


# ---------------------------------------------------------------------------
# Building each part
# ---------------------------------------------------------------------------


def build_profile_context(profile_summary) -> dict:
    """The lifestyle answers, or an honest account of their absence."""

    profile = None

    if isinstance(profile_summary, dict):
        profile = profile_summary.get("profile")

        if profile is None and profile_summary.get("complete") is None:
            # Handed the profile document itself rather than the API's wrapper.
            profile = profile_summary or None

    if not isinstance(profile, dict) or not profile:
        return {
            "available": False,
            "source": SOURCE_SELF_REPORTED,
            "reason": (
                "This user has not filled in the setup questions, so nothing is "
                "known about their day-to-day habits."
            ),
            "values": [],
            "missingFields": [label for _, label, _ in PROFILE_FIELDS],
        }

    values = []
    missing = []

    for key, label, unit in PROFILE_FIELDS:
        value = _read(profile, key)

        if value is None or value == "":
            missing.append(label)
            continue

        values.append({"key": key, "label": label,
                       "value": _number(value), "unit": unit})

    updated_at = _read(profile_summary, "updatedAt") \
        or _read(profile_summary, "updated_at")

    return {
        "available": bool(values),
        "source": SOURCE_SELF_REPORTED,
        "reason": None if values else (
            "The setup questions were started but no answers were kept."
        ),
        "values": values,
        "missingFields": missing,
        # Text either way. This is handed straight to a JSON response, and the
        # stored document holds a datetime while the API's version holds a
        # string.
        "updatedAt": updated_at.isoformat()
        if isinstance(updated_at, datetime) else updated_at,
    }


def _describe_shoulder(measurements: dict) -> list:
    left = measurements.get("left") or {}
    right = measurements.get("right") or {}

    lines = []

    for side, label in ((left, "Left arm"), (right, "Right arm")):
        elevation = side.get("finalElevationDeg")

        if elevation is None:
            lines.append(f"{label}: no usable angle was obtained.")
            continue

        lines.append(
            f"{label}: appeared to reach about {_number(elevation)} degrees away "
            "from the body in the camera's image."
        )

    difference = measurements.get("observableDifferenceDeg")

    if difference is not None:
        lines.append(
            f"Difference between the two sides as seen on camera: about "
            f"{_number(difference)} degrees. Some difference between sides is "
            "ordinary, and camera angle alone can produce it."
        )

    else:
        lines.append(
            "The two sides cannot be compared, because at least one of them "
            "produced no usable angle."
        )

    return lines


def _describe_ftsst(measurements: dict, setup) -> list:
    lines = []

    seconds = measurements.get("completionTimeSeconds")
    detected = measurements.get("repetitionsDetected")
    required = measurements.get("requiredRepetitions")

    if seconds is None:
        lines.append("No completion time was obtained.")

    else:
        lines.append(
            f"The five repetitions took about {_number(seconds)} seconds in "
            "total, timed by software watching the video."
        )

    if detected is not None and required is not None:
        lines.append(
            f"Repetitions the software recognised: {detected} of {required}."
        )

    if isinstance(setup, dict):
        height = setup.get("chairSeatHeightCm")

        if height is not None and setup.get("chairSeatHeightPlausible") is False:
            lines.append(
                "The seat height the user entered looked implausible, so this "
                "time should not be compared against another session."
            )

        elif height is not None:
            lines.append(
                f"Chair seat height as entered by the user: {_number(height)} cm. "
                "Seat height changes how hard the movement is, so a time from a "
                "different chair is not comparable."
            )

        else:
            lines.append(
                "No seat height was recorded, so this time cannot be compared "
                "against another session."
            )

    return lines


def _describe_balance(measurements: dict) -> list:
    lines = []

    for key, label in (("left", "Standing on the left leg"),
                       ("right", "Standing on the right leg")):
        side = measurements.get(key) or {}

        if not side.get("attempted"):
            lines.append(f"{label}: not attempted, so no duration exists.")
            continue

        if not side.get("valid"):
            lines.append(
                f"{label}: attempted, but the recording did not meet the "
                "test's conditions, so the duration is not usable."
            )
            continue

        seconds = side.get("holdDurationSeconds")

        if seconds is None:
            lines.append(f"{label}: no duration was obtained.")
            continue

        limit = " which was the time limit, so the hold was not tested further" \
            if side.get("reachedMaxDuration") else ""

        lines.append(f"{label}: held for about {_number(seconds)} seconds{limit}.")

    difference = measurements.get("observableDifferenceMs")

    if difference is not None:
        lines.append(
            f"Difference between the two legs: about "
            f"{_number(difference / 1000)} seconds."
        )

    return lines


_DESCRIBERS = {
    "shoulder": lambda measurements, setup: _describe_shoulder(measurements),
    "ftsst": _describe_ftsst,
    "balance": lambda measurements, setup: _describe_balance(measurements),
}


def build_assessment_context(assessment) -> dict:
    """The movement session, test by test, with its gaps named."""

    if not isinstance(assessment, dict) or not assessment:
        return {
            "available": False,
            "source": SOURCE_WEBCAM_OBSERVATION,
            "reason": (
                "This user has not completed a movement assessment, so there "
                "are no movement observations at all."
            ),
            "tests": [],
        }

    summary = assessment.get("summary") or {}
    tests = assessment.get("tests") or {}

    described = []

    for test_id in TEST_ORDER:
        test = tests.get(test_id)

        if not isinstance(test, dict):
            described.append({
                "id": test_id,
                "name": TEST_DESCRIPTIONS[test_id]["name"],
                "status": "not_started",
                "statusExplanation": STATUS_EXPLANATIONS["not_started"],
                "observes": TEST_DESCRIPTIONS[test_id]["observes"],
                "isNot": TEST_DESCRIPTIONS[test_id]["is_not"],
                "observations": [],
                "reliabilityNotes": [],
            })
            continue

        status = test.get("status") or "not_started"

        observations = []

        # Only a completed test has anything to describe. An invalid or skipped
        # one keeps its status and contributes no numbers, which is the whole
        # point of holding on to the distinction.
        if status == "completed":
            describer = _DESCRIBERS.get(test_id)

            if describer is not None:
                observations = describer(test.get("measurements") or {},
                                         test.get("setup"))

        described.append({
            "id": test_id,
            "name": TEST_DESCRIPTIONS[test_id]["name"],
            "status": status,
            "statusExplanation": STATUS_EXPLANATIONS.get(
                status, "in an unrecognised state, so it produced nothing usable"
            ),
            "observes": TEST_DESCRIPTIONS[test_id]["observes"],
            "isNot": TEST_DESCRIPTIONS[test_id]["is_not"],
            "observations": observations,
            "reliabilityNotes": _reliability_notes(test),
        })

    usable = [test for test in described if test["status"] == "completed"]

    return {
        "available": bool(usable),
        "source": SOURCE_WEBCAM_OBSERVATION,
        "reason": None if usable else (
            "A session exists but no test in it produced a usable measurement."
        ),
        "completedAt": assessment.get("completedAt") or assessment.get("createdAt"),
        "protocolVersion": assessment.get("protocolVersion"),
        "counts": {
            "completed": summary.get("testsCompleted"),
            "invalid": summary.get("testsInvalid"),
            "skipped": summary.get("testsSkipped"),
            "notStarted": summary.get("testsNotStarted"),
        },
        "tests": described,
    }


def _reliability_notes(test: dict) -> list:
    """What was wrong with the recording, in plain words.

    Kept separate from the observations so a model cannot mistake a recording
    problem for something about the person.
    """

    notes = []

    quality = test.get("quality")

    if isinstance(quality, dict):
        for label, value in (("frame rate", quality.get("meanFps")),
                             ("detection confidence",
                              quality.get("meanKeypointScore"))):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                notes.append(f"Recording {label}: {_number(value)}.")

    reasons = test.get("invalidReasons")

    if isinstance(reasons, list) and reasons:
        readable = ", ".join(
            str(reason).replace("_", " ").replace(":", " on the ").rstrip(".")
            for reason in reasons[:6]
        )

        notes.append(f"Conditions the recording did not meet: {readable}.")

    attempts = test.get("attempts")

    if isinstance(attempts, int) and attempts > 1:
        notes.append(f"The user attempted this test {attempts} times.")

    return notes


def build_report_context(confirmed, totals=None) -> dict:
    """Confirmed report values, with any unconfirmed ones counted but excluded."""

    total_reports = None
    confirmed_count = 0

    if isinstance(totals, dict):
        total_reports = totals.get("total")

    reports = []

    if isinstance(confirmed, dict):
        confirmed_count = confirmed.get("reportCount") or 0

        for report in confirmed.get("reports") or []:
            if not isinstance(report, dict):
                continue

            values = [
                {
                    "label": value.get("label") or value.get("key"),
                    "value": value.get("value"),
                    "unit": value.get("unit"),
                    "printedReferenceRange": value.get("printedReferenceRange"),
                    "category": value.get("category"),
                    "wasCorrectedByUser": bool(value.get("wasCorrectedByUser")),
                }
                for value in report.get("values") or []
                if isinstance(value, dict)
            ]

            reports.append({
                "title": report.get("title") or "Untitled report",
                "reportDate": report.get("reportDate"),
                "facility": report.get("facility"),
                "confirmedAt": report.get("confirmedAt"),
                "values": values,
            })

    unconfirmed = None

    if isinstance(total_reports, int):
        unconfirmed = max(0, total_reports - (confirmed_count or 0))

    return {
        "available": bool(reports),
        "source": SOURCE_USER_CONFIRMED_REPORT,
        "reason": None if reports else (
            "This user has reports that have not been confirmed yet, so none of "
            "their values may be used."
            if unconfirmed else
            "This user has not confirmed any medical report, so no report "
            "values exist to work from."
        ),
        "confirmedReportCount": confirmed_count,
        "unconfirmedReportCount": unconfirmed,
        "reports": reports,
    }


# ---------------------------------------------------------------------------
# The context
# ---------------------------------------------------------------------------


def build_context(*, profile_summary=None, assessment=None, confirmed_reports=None,
                  report_totals=None, generated_at=None) -> dict:
    """Everything an agent may read about one user, and nothing else."""

    profile = build_profile_context(profile_summary)
    movement = build_assessment_context(assessment)
    reports = build_report_context(confirmed_reports, report_totals)

    present = [
        name
        for name, part in (("profile", profile), ("movement", movement),
                           ("reports", reports))
        if part["available"]
    ]

    missing = [
        name
        for name, part in (("profile", profile), ("movement", movement),
                           ("reports", reports))
        if not part["available"]
    ]

    context = {
        "generatedAt": generated_at or _now_iso(),
        "profile": profile,
        "movement": movement,
        "reports": reports,
        "availability": {
            "present": present,
            "missing": missing,
            "hasAnything": bool(present),
            # Two sources is the point at which guidance can say something the
            # user could not read off a single screen themselves. Below that it
            # still runs, and it says what it is working from.
            "isThin": len(present) < 2,
        },
    }

    context["signature"] = context_signature(context)

    return context


def context_signature(context: dict) -> str:
    """A short fingerprint of the inputs.

    Lets a stored guidance run be compared against the user's data as it is now,
    so a screen can say the guidance was written before the newest assessment
    rather than presenting it as current. The timestamp is excluded, otherwise
    every rebuild of an unchanged context would look like a change.
    """

    subject = {
        "profile": context.get("profile", {}).get("values"),
        "movement": [
            {"id": test["id"], "status": test["status"],
             "observations": test["observations"]}
            for test in context.get("movement", {}).get("tests", [])
        ],
        "reports": context.get("reports", {}).get("reports"),
    }

    encoded = json.dumps(subject, sort_keys=True, default=str).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Rendering for a model
#
# The only text a model ever receives about the user. Written out field by field
# on purpose: dumping the context as JSON would be shorter, but it would also
# mean any key that ever gets added to a stored document silently becomes part
# of a prompt.
# ---------------------------------------------------------------------------


def _profile_section(profile: dict) -> list:
    lines = ["ABOUT THIS PERSON",
             f"Where this comes from: {SOURCE_DESCRIPTIONS[SOURCE_SELF_REPORTED]}."]

    if not profile["available"]:
        lines.append(profile["reason"])

        return lines

    for entry in profile["values"]:
        unit = f" {entry['unit']}" if entry["unit"] else ""

        lines.append(f"- {entry['label']}: {entry['value']}{unit}")

    if profile["missingFields"]:
        lines.append(
            "Not answered: " + ", ".join(profile["missingFields"]) +
            ". Do not guess at these."
        )

    return lines


def _movement_section(movement: dict) -> list:
    lines = [
        "MOVEMENT OBSERVATIONS",
        f"Where this comes from: {SOURCE_DESCRIPTIONS[SOURCE_WEBCAM_OBSERVATION]}.",
    ]

    if not movement["tests"]:
        lines.append(movement["reason"])

        return lines

    if movement.get("completedAt"):
        lines.append(f"Session recorded: {movement['completedAt']}.")

    for test in movement["tests"]:
        lines.append("")
        lines.append(f"{test['name']} — {test['statusExplanation']}")
        lines.append(f"  What it observed: {test['observes']}.")
        lines.append(f"  What it is not: {test['isNot']}.")

        for observation in test["observations"]:
            lines.append(f"  - {observation}")

        for note in test["reliabilityNotes"]:
            lines.append(f"  ~ {note}")

    return lines


def _reports_section(reports: dict) -> list:
    lines = [
        "CONFIRMED MEDICAL REPORT VALUES",
        f"Where this comes from: "
        f"{SOURCE_DESCRIPTIONS[SOURCE_USER_CONFIRMED_REPORT]}.",
    ]

    if not reports["available"]:
        lines.append(reports["reason"])

        return lines

    if reports.get("unconfirmedReportCount"):
        lines.append(
            f"{reports['unconfirmedReportCount']} further report(s) exist that "
            "the user has not confirmed. Their values are deliberately withheld "
            "from you and you must not speculate about them."
        )

    for report in reports["reports"]:
        lines.append("")
        date = f" dated {report['reportDate']}" if report.get("reportDate") else ""
        lines.append(f"{report['title']}{date}:")

        for value in report["values"]:
            unit = f" {value['unit']}" if value.get("unit") else ""

            printed = value.get("printedReferenceRange")

            range_text = (
                f" (the laboratory printed this range beside it: {printed})"
                if printed else
                " (no reference range was printed beside this value on the "
                "report, and you must not supply one)"
            )

            corrected = (
                " [the user corrected this value themselves]"
                if value.get("wasCorrectedByUser") else ""
            )

            lines.append(
                f"- {value['label']}: {value['value']}{unit}{range_text}{corrected}"
            )

    return lines


def context_digest(context: dict) -> str:
    """The context as prose, ready to put in a prompt."""

    sections = [
        _profile_section(context["profile"]),
        _movement_section(context["movement"]),
        _reports_section(context["reports"]),
    ]

    blocks = ["\n".join(section) for section in sections]

    availability = context["availability"]

    if availability["missing"]:
        blocks.append(
            "MISSING INFORMATION\nNothing is available from: "
            + ", ".join(availability["missing"])
            + ". Say plainly that this is missing where it matters. Do not fill "
            "the gap with what is typical."
        )

    return "\n\n".join(blocks)


def context_summary(context: dict) -> dict:
    """What the interface shows about the basis for a piece of guidance.

    Counts and dates only. The values themselves are already on the screens they
    belong to, and repeating report readings inside a guidance response would put
    health information in a second place for no reason.
    """

    movement = context["movement"]
    reports = context["reports"]

    return {
        "generatedAt": context["generatedAt"],
        "signature": context.get("signature"),
        "profileAvailable": context["profile"]["available"],
        "profileFieldCount": len(context["profile"]["values"]),
        "movementAvailable": movement["available"],
        "movementCompletedAt": movement.get("completedAt"),
        "movementTests": [
            {"id": test["id"], "name": test["name"], "status": test["status"]}
            for test in movement["tests"]
        ],
        "confirmedReportCount": reports["confirmedReportCount"],
        "unconfirmedReportCount": reports["unconfirmedReportCount"],
        "present": context["availability"]["present"],
        "missing": context["availability"]["missing"],
        "hasAnything": context["availability"]["hasAnything"],
        "isThin": context["availability"]["isThin"],
    }
