"""Validation for incoming assessment results.

The browser produces these measurements, which makes the whole payload
untrusted input. Two kinds of rule are enforced here.

Structural rules keep the payload to the shape and size the assessment
protocol can actually produce: known test ids, known statuses, bounded arrays,
bounded strings, bounded nesting.

Privacy rules enforce the product invariant that pose data never leaves the
device. No frame, image, or keypoint sequence is ever stored, so anything that
looks like one is rejected outright rather than quietly saved.

What is deliberately NOT validated here is the clinical meaning of any
measurement. The backend does not know what a plausible arm elevation is, and
inventing bounds for one would be inventing a clinical norm. Measurement
content is stored as recorded; only structure and privacy are policed.
"""

from datetime import datetime

# The three tests defined by the assessment protocol. A payload naming anything
# else is rejected rather than stored for later interpretation.
TEST_IDS = ("shoulder", "ftsst", "balance")

# Must match TEST_STATUS in src/assessment/config/protocol.js.
TEST_STATUSES = ("completed", "invalid", "skipped", "not_started")

# A status that never carries measurements. Enforced, because a skipped test
# arriving with numbers attached would let a skip be read as a result.
STATUSES_WITHOUT_MEASUREMENTS = ("skipped", "not_started")

# Structural ceilings. These are generous compared with what the protocol
# produces (the longest legitimate array is a handful of per-repetition
# numbers) and far too small to hold a pose sequence.
MAX_ARRAY_LENGTH = 32
MAX_OBJECT_KEYS = 48
MAX_STRING_LENGTH = 200
MAX_DEPTH = 6
MAX_TOTAL_NODES = 800

# Privacy filtering on field names, in three parts.
#
# The primary defence is structural: MAX_ARRAY_LENGTH and MAX_TOTAL_NODES leave
# no room for a keypoint sequence whatever it is called. The name rules below
# are the second line, aimed at our own accidents - a future change that starts
# attaching frame or image data to a result fails loudly here instead of
# quietly writing it to the database.
#
# The distinction that matters is scalar versus sequence. A single number
# summarising pose quality, such as meanKeypointScore or longestPoseLossMs, is
# exactly the "minimal quality metadata" that is meant to be stored. A list or
# object of pose data is what must never be stored. So aggregate statistics are
# allowed through and containers under the same names are not.

# Names with no legitimate scalar counterpart: these are media or encoded
# payloads however they are shaped.
FORBIDDEN_KEY_SUBSTRINGS = (
    "video",
    "framedata",
    "rawframe",
    "image",
    "pixel",
    "dataurl",
    "base64",
    "blob",
    "thumbnail",
    "snapshot",
)

# Exact names that denote a collection of pose data rather than a summary of it.
FORBIDDEN_KEY_NAMES = (
    "keypoints",
    "keypointsequence",
    "keypointseries",
    "keypointhistory",
    "landmarks",
    "landmarksequence",
    "poses",
    "posesequence",
    "posehistory",
    "skeleton",
    "skeletons",
    "frames",
    "framesequence",
    "frameseries",
)

# A field whose name refers to pose data may hold a number or a string, never a
# list or an object. This is the rule that actually enforces "no sequences",
# independently of what the field is called.
POSE_RELATED_KEY_SUBSTRINGS = (
    "keypoint",
    "landmark",
    "pose",
    "skeleton",
    "frame",
)

MAX_PROTOCOL_VERSION_LENGTH = 32
MAX_SESSION_ID_LENGTH = 64
MAX_REASONS = 12


class AssessmentValidationError(ValueError):
    """Raised when a submitted assessment cannot be accepted.

    The message is written to be shown to a developer, not a user; routes wrap
    it in a 400 with a short explanation.
    """


def _fail(message: str):
    raise AssessmentValidationError(message)


def _require_mapping(value, label: str) -> dict:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")

    return value


def _clean_key(key) -> str:
    """Validate one field name and return it, or raise."""

    if not isinstance(key, str):
        _fail("object keys must be strings")

    if not key or len(key) > 64:
        _fail("object keys must be between 1 and 64 characters")

    lowered = key.lower()

    for forbidden in FORBIDDEN_KEY_SUBSTRINGS:
        if forbidden in lowered:
            _fail(
                f"the field {key!r} is not accepted: video, images, and encoded "
                "media are never stored"
            )

    if lowered in FORBIDDEN_KEY_NAMES:
        _fail(
            f"the field {key!r} is not accepted: sequences of pose data are "
            "never stored, only the measurements derived from them"
        )

    return key


def _reject_pose_container(key: str, value):
    """A pose-related field may summarise pose data, never contain it.

    meanKeypointScore is a number and is kept. A list or object under a name
    like keypointSeries or poseHistory is a sequence, and storing one would
    break the promise that pose data stays on the device.
    """

    if not isinstance(value, (list, dict)):
        return

    lowered = key.lower()

    for term in POSE_RELATED_KEY_SUBSTRINGS:
        if term in lowered:
            _fail(
                f"the field {key!r} is not accepted: a field naming pose data may "
                "hold a single summary value, not a list or object of it"
            )


class _NodeBudget:
    """Counts nodes across a whole payload, not per branch.

    A per-branch limit can be defeated by breadth; a shared budget cannot.
    """

    def __init__(self, limit: int):
        self.remaining = limit

    def spend(self):
        self.remaining -= 1

        if self.remaining < 0:
            _fail("the payload contains more fields than an assessment can produce")


def sanitise_value(value, budget: _NodeBudget, depth: int = 0, label: str = "value"):
    """Return the value if it is storable, raising if it is not.

    Only JSON scalars, lists, and objects are allowed, so nothing that could
    carry binary data or an unbounded sequence gets through.
    """

    budget.spend()

    if depth > MAX_DEPTH:
        _fail(f"{label} is nested more deeply than an assessment result can be")

    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        # NaN and infinity are not representable in JSON and would make a
        # stored measurement unreadable by the client that has to display it.
        if value != value or value in (float("inf"), float("-inf")):
            _fail(f"{label} must be a finite number")

        return value

    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            _fail(f"{label} is longer than {MAX_STRING_LENGTH} characters")

        return value

    if isinstance(value, list):
        if len(value) > MAX_ARRAY_LENGTH:
            _fail(
                f"{label} has {len(value)} entries, above the limit of "
                f"{MAX_ARRAY_LENGTH}. Sequences of pose data are never stored."
            )

        return [
            sanitise_value(item, budget, depth + 1, f"{label}[{index}]")
            for index, item in enumerate(value)
        ]

    if isinstance(value, dict):
        if len(value) > MAX_OBJECT_KEYS:
            _fail(f"{label} has more than {MAX_OBJECT_KEYS} fields")

        cleaned = {}

        for key, item in value.items():
            name = _clean_key(key)

            _reject_pose_container(name, item)

            cleaned[name] = sanitise_value(item, budget, depth + 1, f"{label}.{key}")

        return cleaned

    _fail(f"{label} has a type that cannot be stored: {type(value).__name__}")


def _parse_timestamp(value, label: str, *, required: bool):
    """Accept an ISO 8601 string and return a datetime, or None."""

    if value is None:
        if required:
            _fail(f"{label} is required")

        return None

    if not isinstance(value, str) or len(value) > 64:
        _fail(f"{label} must be an ISO 8601 timestamp string")

    # The browser sends Date.prototype.toISOString(), which ends in "Z".
    # fromisoformat only accepts "Z" from Python 3.11 onward, so normalise it.
    text = value.strip()

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        return datetime.fromisoformat(text)

    except ValueError:
        _fail(f"{label} must be an ISO 8601 timestamp, got {value!r}")


def _validate_reasons(value, label: str) -> list:
    if value is None:
        return []

    if not isinstance(value, list):
        _fail(f"{label} must be a list of reason codes")

    if len(value) > MAX_REASONS:
        _fail(f"{label} has more than {MAX_REASONS} entries")

    reasons = []

    for index, reason in enumerate(value):
        if not isinstance(reason, str) or not reason or len(reason) > 64:
            _fail(f"{label}[{index}] must be a short reason code string")

        reasons.append(reason)

    return reasons


def _validate_test(test_id: str, raw, budget: _NodeBudget) -> dict:
    """Validate one test result and return the document to store."""

    label = f"tests.{test_id}"
    payload = _require_mapping(raw, label)

    status = payload.get("status")

    if status not in TEST_STATUSES:
        _fail(f"{label}.status must be one of {', '.join(TEST_STATUSES)}")

    measurements = payload.get("measurements")

    # The rule that keeps a skip from becoming a result. The client already
    # enforces it; a second check here means a buggy or hostile client cannot
    # write a record that reads as "measured zero".
    if status in STATUSES_WITHOUT_MEASUREMENTS and measurements is not None:
        _fail(
            f"{label} is {status} but carries measurements. A test that was not "
            "performed has no measurements, and must never be stored as zero."
        )

    if status == "completed" and measurements is None:
        _fail(f"{label} is completed but carries no measurements")

    if measurements is not None:
        measurements = _require_mapping(measurements, f"{label}.measurements")

    document = {
        "status": status,
        "measurements": sanitise_value(
            measurements, budget, label=f"{label}.measurements"
        ),
        "quality": sanitise_value(
            payload.get("quality"), budget, label=f"{label}.quality"
        ),
        "invalid_reasons": _validate_reasons(
            payload.get("invalidReasons"), f"{label}.invalidReasons"
        ),
        "attempts": _validate_attempts(payload.get("attempts"), label),
    }

    # Setup metadata is optional and only some tests collect it. Chair seat
    # height lives here, and without it two sit-to-stand times are not
    # comparable, so it is stored with the result rather than dropped.
    if payload.get("setup") is not None:
        document["setup"] = sanitise_value(
            _require_mapping(payload["setup"], f"{label}.setup"),
            budget,
            label=f"{label}.setup",
        )

    return document


def _validate_attempts(value, label: str) -> int:
    if value is None:
        return 0

    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{label}.attempts must be a whole number")

    if value < 0 or value > 100:
        _fail(f"{label}.attempts must be between 0 and 100")

    return value


def _validate_summary(raw, tests: dict) -> dict:
    """Recount the summary from the stored statuses.

    The client sends a summary, but it is derived data, so it is recomputed
    rather than trusted. That way a stored summary can never disagree with the
    statuses stored beside it.
    """

    if raw is not None:
        _require_mapping(raw, "summary")

    statuses = [tests[test_id]["status"] for test_id in TEST_IDS]

    return {
        "tests_completed": statuses.count("completed"),
        "tests_invalid": statuses.count("invalid"),
        "tests_skipped": statuses.count("skipped"),
        "tests_not_started": statuses.count("not_started"),
        "has_any_usable_result": "completed" in statuses,
    }


def _validate_short_string(value, label: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{label} is required")

    text = value.strip()

    if len(text) > max_length:
        _fail(f"{label} must be at most {max_length} characters")

    return text


def validate_assessment_payload(raw) -> dict:
    """Turn an untrusted submission into a document ready to store.

    The returned dict has no user id and no server timestamps; the store layer
    adds those from the authenticated session so they cannot be spoofed.
    """

    payload = _require_mapping(raw, "the assessment payload")

    unknown = set(payload) - {
        "sessionId",
        "protocolVersion",
        "startedAt",
        "completedAt",
        "summary",
        "tests",
        "client",
    }

    if unknown:
        _fail(f"unexpected fields in the payload: {', '.join(sorted(unknown))}")

    raw_tests = _require_mapping(payload.get("tests"), "tests")

    missing = [test_id for test_id in TEST_IDS if test_id not in raw_tests]

    if missing:
        _fail(f"tests is missing: {', '.join(missing)}")

    extra = set(raw_tests) - set(TEST_IDS)

    if extra:
        _fail(f"tests contains unknown test ids: {', '.join(sorted(extra))}")

    budget = _NodeBudget(MAX_TOTAL_NODES)

    tests = {
        test_id: _validate_test(test_id, raw_tests[test_id], budget)
        for test_id in TEST_IDS
    }

    started_at = _parse_timestamp(payload.get("startedAt"), "startedAt", required=True)
    completed_at = _parse_timestamp(
        payload.get("completedAt"), "completedAt", required=False
    )

    if completed_at is not None and completed_at < started_at:
        _fail("completedAt is before startedAt")

    document = {
        "session_id": _validate_short_string(
            payload.get("sessionId"), "sessionId", MAX_SESSION_ID_LENGTH
        ),
        "protocol_version": _validate_short_string(
            payload.get("protocolVersion"),
            "protocolVersion",
            MAX_PROTOCOL_VERSION_LENGTH,
        ),
        "started_at": started_at,
        "completed_at": completed_at,
        "summary": _validate_summary(payload.get("summary"), tests),
        "tests": tests,
    }

    # Optional recording-environment notes. Useful when comparing two sessions,
    # and sanitised like everything else.
    if payload.get("client") is not None:
        document["client"] = sanitise_value(
            _require_mapping(payload["client"], "client"), budget, label="client"
        )

    return document
