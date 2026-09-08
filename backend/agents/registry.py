"""What each agent is, and what it is not allowed to do.

Written down in one place because the answer has to be the same everywhere. The
screen that introduces the agents, the endpoint that reports their state and the
code that runs them all read this, so a limit cannot be described one way to the
user and implemented another way in the pipeline.

The wording is aimed at the person using the application rather than at a
developer. "Cannot tell you what a result means" is a sentence somebody deciding
whether to trust this can act on; "no interpretation layer" is not.

Standard library only, so a screen can ask what the agents are without the model
transport or the database being involved.
"""

STAGE_EXTRACTION = 1
STAGE_GUIDANCE = 2
STAGE_NAVIGATION = 3

REPORT_EXTRACTION = {
    "id": "report_extraction",
    "stage": STAGE_EXTRACTION,
    "name": "Report reader",
    "role": "Copies the values printed on a medical report into a list you check.",
    "canDo": [
        "Read a PDF or a photo of your report and transcribe the values it can "
        "see",
        "Quote the line it read each value from, so you can check it against "
        "your document",
        "Copy a reference range if your report prints one beside the value",
        "Say when it could not read something, and leave it out",
    ],
    "cannotDo": [
        "Decide anything about what a value means",
        "Say whether a value is high, low, normal or abnormal",
        "Fill in a value it could not read",
        "Treat anything as true before you have checked and confirmed it",
    ],
    "note": (
        "Nothing this agent reads is used anywhere else until you have gone "
        "through the values and confirmed them yourself."
    ),
}

WELLNESS_GUIDANCE = {
    "id": "wellness_guidance",
    "stage": STAGE_GUIDANCE,
    "name": "Wellness guide",
    "role": "Reflects back what was observed and suggests general habits.",
    "canDo": [
        "Restate what your movement recording showed, in plain words",
        "Repeat the report values you confirmed, along with any range printed on "
        "your own document",
        "Suggest ordinary wellness habits around movement, activity and sleep",
        "Tell you what was missing and what having it would allow",
    ],
    "cannotDo": [
        "Diagnose anything, or suggest what you might have",
        "Tell you what a result means or whether it is a problem",
        "Invent a normal range, a threshold or a score",
        "Advise on medication, supplements or doses",
        "Treat a webcam observation as a clinical measurement",
    ],
    "note": (
        "It works from your setup answers, your movement observations and the "
        "report values you confirmed. Nothing else."
    ),
}

CARE_NAVIGATION = {
    "id": "care_navigation",
    "stage": STAGE_NAVIGATION,
    "name": "Care navigator",
    "role": "Suggests the kind of professional you might talk to, and what to ask.",
    "canDo": [
        "Suggest a general kind of professional you may wish to raise something "
        "with",
        "Give you questions to take with you, in your own words",
        "Say what this tool could not tell you, so you know what to ask about",
    ],
    "cannotDo": [
        "Refer you to anybody, or name a medical specialty",
        "Tell you that you need to be seen, or that you do not",
        "Decide whether anything is urgent",
        "Say what a professional will find",
    ],
    "note": (
        "Everything here is an option you can take or leave. Choosing a "
        "specialist would imply a diagnosis, so it only ever names general "
        "roles."
    ),
}

AGENTS = (REPORT_EXTRACTION, WELLNESS_GUIDANCE, CARE_NAVIGATION)

BY_ID = {agent["id"]: agent for agent in AGENTS}


def describe_agents() -> list:
    """The three agents in the order they run."""

    return [dict(agent) for agent in AGENTS]


def describe(agent_id: str) -> dict:
    return dict(BY_ID[agent_id])
