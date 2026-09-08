"""The shapes an agent response is allowed to have.

The tool schemas and the code that reads what comes back, kept together because
they describe the same contract from both ends, and kept free of any dependency
so both ends can be tested without a network, a database or an API key.

Validation here is strict about structure and quiet about content. A missing
list becomes an empty list, an over-long sentence is dropped rather than
truncated mid-word, and anything that is not the type it should be is discarded.
What it never does is invent a replacement: a response with nothing usable in it
raises, and the caller reports that honestly instead of showing an empty panel
that looks like a considered answer.

Two decisions are worth the words.

Truncation is refusal. A sentence cut off at 400 characters can change meaning,
and "your result is normal for someone" is a different claim from "your result is
normal". Anything over the limit is dropped whole.

The kind of professional is an enumeration. The model picks from a fixed list of
general roles and never writes the role itself, because naming a specialty is a
diagnosis by implication: "see a rheumatologist" tells the reader they have
arthritis without ever using the word. The displayed wording for each role is
written here, not by the model.
"""

# ---------------------------------------------------------------------------
# Limits
#
# Loose enough not to shape the content, tight enough that a runaway response
# cannot fill a screen or a database document.
# ---------------------------------------------------------------------------

MAX_SHORT = 160
MAX_SENTENCE = 400
MAX_PARAGRAPH = 700

MAX_OBSERVATIONS = 6
MAX_FOCUS_AREAS = 4
MAX_SUGGESTIONS = 4
MAX_HABITS = 6
MAX_GAPS = 6
MAX_CONSIDERATIONS = 5
MAX_QUESTIONS = 6


class AgentOutputError(RuntimeError):
    """Raised when a response has no usable content in it."""


# ---------------------------------------------------------------------------
# Who the person might talk to
#
# General roles only. Every entry is somebody a person can approach about
# wellbeing without a referral and without a suspected condition behind it.
# ---------------------------------------------------------------------------

PROFESSIONAL_TYPES = {
    "doctor_or_gp": {
        "label": "A doctor or GP",
        "note": "The person to take anything medical to first.",
    },
    "clinician_who_ordered_the_report": {
        "label": "The clinician who ordered your report",
        "note": "They have the full picture your report came from.",
    },
    "physiotherapist": {
        "label": "A physiotherapist",
        "note": "Trained to look properly at how a body moves.",
    },
    "qualified_exercise_professional": {
        "label": "A qualified exercise professional",
        "note": "For building activity up safely and at the right pace.",
    },
    "registered_dietitian": {
        "label": "A registered dietitian or nutrition professional",
        "note": "For anything about eating, without guesswork.",
    },
    "pharmacist": {
        "label": "A pharmacist",
        "note": "Easy to reach, and the right person for medication questions.",
    },
    "mental_wellbeing_professional": {
        "label": "A mental wellbeing professional",
        "note": "For stress, mood and sleep that habits alone are not shifting.",
    },
    "sleep_health_professional": {
        "label": "A sleep health professional",
        "note": "For sleep that stays poor after the obvious things are fixed.",
    },
}


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

WELLNESS_TOOL = {
    "name": "record_wellness_guidance",
    "description": (
        "Record general wellness guidance based only on the information "
        "provided about this person."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "opening": {
                "type": "string",
                "description": (
                    "One or two sentences saying what this guidance is based on, "
                    "naming the sources that were available. No conclusions."
                ),
            },
            "observations": {
                "type": "array",
                "description": (
                    "What was actually observed or confirmed, restated so the "
                    "person recognises it. Describe, do not evaluate."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "detail": {"type": "string"},
                    },
                    "required": ["heading", "detail"],
                },
            },
            "focusAreas": {
                "type": "array",
                "description": (
                    "At most four things worth attention, each tied to something "
                    "in the information provided."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "whyThisCameUp": {
                            "type": "string",
                            "description": (
                                "Which observation or answer led here, said "
                                "plainly. Not what it means medically."
                            ),
                        },
                        "suggestions": {
                            "type": "array",
                            "description": (
                                "General, widely accepted wellness actions. "
                                "Nothing medical, nothing about supplements."
                            ),
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["title", "whyThisCameUp", "suggestions"],
                },
            },
            "habits": {
                "type": "array",
                "description": (
                    "General habits that suit this person's situation. Plain, "
                    "practical, no medical content."
                ),
                "items": {"type": "string"},
            },
            "missingInformation": {
                "type": "array",
                "description": (
                    "What was not available, and what having it would allow. One "
                    "short sentence each."
                ),
                "items": {"type": "string"},
            },
            "closing": {
                "type": "string",
                "description": (
                    "One or two encouraging sentences. No promises and no "
                    "reassurance about health."
                ),
            },
        },
        "required": ["opening", "observations", "focusAreas", "missingInformation"],
    },
}


NAVIGATION_TOOL = {
    "name": "record_care_navigation",
    "description": (
        "Record suggestions about the kind of professional this person might "
        "choose to talk to, and what they could usefully ask."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "opening": {
                "type": "string",
                "description": (
                    "One or two sentences framing these as options the person "
                    "may consider, not instructions and not a referral."
                ),
            },
            "considerations": {
                "type": "array",
                "description": (
                    "At most five suggestions. Each names a kind of professional "
                    "from the fixed list and says what they could look at."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "professionalType": {
                            "type": "string",
                            "enum": list(PROFESSIONAL_TYPES),
                            "description": (
                                "Choose from this list only. Never name a "
                                "medical specialty."
                            ),
                        },
                        "whatTheyCouldLookAt": {
                            "type": "string",
                            "description": (
                                "Phrased as something the person may wish to "
                                "raise. Never a condition to be checked for."
                            ),
                        },
                        "whyItCameUp": {
                            "type": "string",
                            "description": (
                                "The observation or answer behind the "
                                "suggestion, stated without interpreting it."
                            ),
                        },
                    },
                    "required": ["professionalType", "whatTheyCouldLookAt"],
                },
            },
            "questionsToAsk": {
                "type": "array",
                "description": (
                    "Questions the person could take with them, in their own "
                    "voice. Questions only, never answers."
                ),
                "items": {"type": "string"},
            },
            "limitations": {
                "type": "array",
                "description": (
                    "What this tool could not tell, so the person knows what to "
                    "ask about rather than assume."
                ),
                "items": {"type": "string"},
            },
        },
        "required": ["opening", "considerations", "limitations"],
    },
}


# ---------------------------------------------------------------------------
# Reading what came back
# ---------------------------------------------------------------------------


def _text(value, limit: int):
    """A single clean line, or None if it is unusable or too long."""

    if not isinstance(value, str):
        return None

    cleaned = " ".join(value.split())

    if not cleaned:
        return None

    # Dropped rather than cut: a sentence that stops early can mean something
    # its author did not intend, and this is not text anybody proofreads.
    if len(cleaned) > limit:
        return None

    return cleaned


def _text_list(value, limit: int, maximum: int) -> list:
    if not isinstance(value, list):
        return []

    cleaned = []

    for item in value:
        text = _text(item, limit)

        if text and text not in cleaned:
            cleaned.append(text)

        if len(cleaned) >= maximum:
            break

    return cleaned


def _objects(value, maximum: int) -> list:
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, dict)][:maximum]


def parse_wellness(raw) -> dict:
    """Validate a wellness response into the shape the API returns."""

    if not isinstance(raw, dict):
        raise AgentOutputError("The guidance response was not a structured result.")

    observations = []

    for item in _objects(raw.get("observations"), MAX_OBSERVATIONS):
        heading = _text(item.get("heading"), MAX_SHORT)
        detail = _text(item.get("detail"), MAX_PARAGRAPH)

        if heading and detail:
            observations.append({"heading": heading, "detail": detail})

    focus_areas = []

    for item in _objects(raw.get("focusAreas"), MAX_FOCUS_AREAS):
        title = _text(item.get("title"), MAX_SHORT)
        why = _text(item.get("whyThisCameUp"), MAX_SENTENCE)
        suggestions = _text_list(item.get("suggestions"), MAX_SENTENCE,
                                 MAX_SUGGESTIONS)

        # A focus area with no suggestions is a heading with nothing under it,
        # which reads as an unfinished thought rather than as restraint.
        if title and suggestions:
            focus_areas.append({
                "title": title,
                "whyThisCameUp": why,
                "suggestions": suggestions,
            })

    parsed = {
        "opening": _text(raw.get("opening"), MAX_PARAGRAPH),
        "observations": observations,
        "focusAreas": focus_areas,
        "habits": _text_list(raw.get("habits"), MAX_SENTENCE, MAX_HABITS),
        "missingInformation": _text_list(
            raw.get("missingInformation"), MAX_SENTENCE, MAX_GAPS
        ),
        "closing": _text(raw.get("closing"), MAX_PARAGRAPH),
    }

    if not (parsed["observations"] or parsed["focusAreas"] or parsed["habits"]):
        raise AgentOutputError(
            "The guidance response contained nothing that could be shown."
        )

    return parsed


def parse_navigation(raw) -> dict:
    """Validate a care navigation response, including the fixed role list."""

    if not isinstance(raw, dict):
        raise AgentOutputError(
            "The care navigation response was not a structured result."
        )

    considerations = []
    seen_roles = []

    for item in _objects(raw.get("considerations"), MAX_CONSIDERATIONS):
        role = item.get("professionalType")

        # A role outside the list is dropped, not mapped to something near it.
        # Guessing what a model meant by "rheumatologist" would put back exactly
        # the implication the list exists to prevent.
        if role not in PROFESSIONAL_TYPES or role in seen_roles:
            continue

        what = _text(item.get("whatTheyCouldLookAt"), MAX_SENTENCE)

        if not what:
            continue

        seen_roles.append(role)

        considerations.append({
            "professionalType": role,
            "label": PROFESSIONAL_TYPES[role]["label"],
            "note": PROFESSIONAL_TYPES[role]["note"],
            "whatTheyCouldLookAt": what,
            "whyItCameUp": _text(item.get("whyItCameUp"), MAX_SENTENCE),
        })

    parsed = {
        "opening": _text(raw.get("opening"), MAX_PARAGRAPH),
        "considerations": considerations,
        "questionsToAsk": _text_list(
            raw.get("questionsToAsk"), MAX_SENTENCE, MAX_QUESTIONS
        ),
        "limitations": _text_list(raw.get("limitations"), MAX_SENTENCE, MAX_GAPS),
    }

    if not (parsed["considerations"] or parsed["questionsToAsk"]):
        raise AgentOutputError(
            "The care navigation response contained nothing that could be shown."
        )

    return parsed


def professional_type_options() -> list:
    """The role list, for a screen that wants to show what is on offer."""

    return [
        {"id": key, "label": value["label"], "note": value["note"]}
        for key, value in PROFESSIONAL_TYPES.items()
    ]
