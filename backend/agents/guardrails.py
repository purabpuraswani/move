"""The limits every agent works inside, written once.

Two halves. The first is the text put in front of the model: the rules it has to
follow, phrased as rules rather than hints. The second is the check applied to
whatever comes back, because a prompt is a request and not a guarantee.

The check is deliberately blunt. It looks for the shapes of sentence this
application has promised never to produce — a diagnosis, a prescription, an
invented normal range, a score, a verdict on urgency — and when it finds one the
response is withheld rather than cleaned up. Editing a diagnosis out of a
paragraph leaves the reasoning that produced it in place, and a response that
was rewritten to look acceptable is worse than a panel that says it could not be
produced.

Blunt checks catch innocent sentences too. Two things keep that cost down. Most
rules are negation-aware, so "this cannot tell you whether you have a condition"
passes while "you have a condition" does not. And a first failure is retried
once with the broken rules named, so an unlucky phrasing usually resolves itself
without the user ever seeing a gap.

Standard library only, for the same reason as agents/context.py: this is the
part that most needs to be testable.
"""

import re

# ---------------------------------------------------------------------------
# What the user is told, in our words rather than a model's
#
# Text that has to be right every single time is written here and shown as
# written. A model asked to produce its own disclaimer will eventually produce a
# softer one, and the softest version is the one that matters.
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "MoveWell AI is a wellness tool. It does not diagnose, treat, or rule out "
    "any medical condition, and nothing here is medical advice. The movement "
    "observations come from an ordinary webcam and are not clinical "
    "measurements. Report values are whatever you confirmed from your own "
    "document. Anything that concerns you belongs with a qualified healthcare "
    "professional who can examine you."
)

SAFETY_NOTE = (
    "This tool cannot tell whether something is urgent. If you develop chest "
    "pain, breathlessness at rest, sudden weakness or numbness, fainting, a "
    "sudden severe headache, or any symptom that frightens you, contact "
    "emergency services or urgent care rather than an app."
)


# ---------------------------------------------------------------------------
# The rules given to the model
# ---------------------------------------------------------------------------

SHARED_RULES = """\
You are part of MoveWell AI, a functional wellness tool. You are not a
clinician, you are not a diagnostic system, and the person reading you has no
way to check your reasoning. Every rule below is a hard limit, not a preference.

WHAT YOU MUST NEVER DO

1. Never diagnose, and never suggest a diagnosis. Do not name a disease,
   condition, disorder, syndrome or deficiency as something this person has,
   might have, probably has, or should be checked for because you suspect it.
2. Never prescribe or advise on medication, supplements or doses. Not brand
   names, not generic names, not amounts, not timing, not starting something and
   not stopping something.
3. Never invent a threshold, a normal range, a healthy range or a cut-off. If a
   reference range was printed on the person's own report it is given to you and
   you may repeat it as theirs; if none was printed, none exists for your
   purposes. Never say a value is high, low, normal or abnormal.
4. Never produce a score, a rating, a grade, a percentage, a body age or a risk
   figure. This application deliberately has none, and inventing one would give
   a number the weight of a measurement.
5. Never say whether something is urgent, whether treatment is needed, or
   whether the person is fine. You cannot see them and you cannot know.
6. Never treat the webcam observations as clinical measurements. They are what a
   pose-estimation model saw through a normal camera. Do not call them range of
   motion, strength, balance ability, fall risk or bone health.
7. Never invent information. If something you would need is missing from what
   you were given, say it is missing. Do not substitute what is typical, average
   or likely for this kind of person.
8. Never repeat a number that was not given to you, and never recalculate one.

WHAT YOU ARE FOR

Restating what was actually observed in plain language, in a way the person can
recognise. Suggesting general, widely accepted wellness habits — movement,
activity, sleep routine, sitting less, hydration, gradual progression. Naming
what is missing so the person knows what would make this more useful. Pointing
at the kind of professional who could look properly at something, in the wording
of a suggestion rather than an instruction.

HOW TO WRITE

Address the person directly as "you". Plain words, short sentences, no clinical
vocabulary and no jargon. Warm and calm, never alarming and never falsely
reassuring. Specific about what was observed, honest about what it does not
mean. Where you use an observation, say what it was: "in the recording your
right arm looked like it lifted a little further than your left" rather than
"your right shoulder is more mobile".
"""


# ---------------------------------------------------------------------------
# Checking what came back
# ---------------------------------------------------------------------------


class GuardrailViolation(RuntimeError):
    """Raised when a response broke a rule that cannot be softened."""

    def __init__(self, rules):
        self.rules = list(rules)

        super().__init__(
            "The generated response broke these rules and was withheld: "
            + ", ".join(self.rules)
        )


# Looked for behind a match, within a short window. "this is not a diagnosis"
# and "you have a condition" contain the same word and mean opposite things.
NEGATORS = re.compile(
    r"\b(not|never|cannot|can'?t|won'?t|isn'?t|aren'?t|doesn'?t|don'?t|no|"
    r"nothing|neither|nor|without|unable|avoid)\b",
    re.IGNORECASE,
)

NEGATION_WINDOW = 70

_CONDITION_WORDS = (
    r"condition|disease|disorder|syndrome|deficiency|an?a?emia|diabetes|"
    r"hypertension|arthritis|osteoporosis|osteopenia|depression|anxiety|cancer|"
    r"infection|dysfunction|impairment|insufficiency|imbalance|sarcopenia|"
    r"frailty|thyroid problem|kidney problem|liver problem|heart problem"
)

# Each rule is (name, description, pattern, negation_may_excuse_it).
#
# The description is what the user is shown, so it says what was wrong without
# repeating the sentence that was wrong.
RULES = (
    (
        "diagnosis",
        "named or implied a diagnosis",
        re.compile(r"\bdiagnos(?:e|ed|es|is|ing|tic|tics)\b", re.IGNORECASE),
        True,
    ),
    (
        "condition_claim",
        "told the reader they have a medical condition",
        re.compile(
            r"\byou\s+(?:have|had|likely have|probably have|may have|might have|"
            r"appear to have|seem to have|are showing signs of|are developing)\s+"
            r"(?:\w+\s+){0,3}?(?:" + _CONDITION_WORDS + r")\b",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "suspected_condition",
        "raised a suspected condition",
        re.compile(
            r"\b(?:suggestive of|consistent with|indicative of|points? to|"
            r"could be a sign of|may be a sign of|signs? of)\s+"
            r"(?:\w+\s+){0,3}?(?:" + _CONDITION_WORDS + r")\b",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "prescription",
        "gave medication or supplement advice",
        re.compile(
            r"\b(?:prescrib\w+|start taking|stop taking|come off|switch to|"
            r"supplement with|you should take|take a supplement)\b",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "dosage",
        "referred to a dose or an amount of a substance",
        re.compile(
            r"\b(?:\d+(?:\.\d+)?\s?(?:mg|mcg|µg|ml|iu)\b|dosage|dose of|"
            r"twice a day|three times a day)\b",
            re.IGNORECASE,
        ),
        False,
    ),
    (
        "treatment_verdict",
        "said whether treatment is needed",
        re.compile(
            r"\byou\s+(?:need|will need|must|require|should get)\s+"
            r"(?:\w+\s+){0,2}?(?:treatment|therapy|surgery|medication|"
            r"antibiotics|an operation|a referral)\b",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "cure_claim",
        "claimed something cures or treats a condition",
        re.compile(r"\b(?:cure|cures|cured|curing|will treat|treats your)\b",
                   re.IGNORECASE),
        True,
    ),
    (
        "invented_norm",
        "used a normal or healthy range that was not printed on the report",
        re.compile(
            r"\b(?:normal range|healthy range|optimal range|ideal range|"
            r"normal limits|abnormal|below normal|above normal|"
            r"outside (?:the )?normal|should be (?:above|below|between)|"
            r"target range|healthy level)\b",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "value_judgement",
        "called one of the person's values high or low",
        re.compile(
            r"\byour\s+(?:\w+\s+){0,3}?(?:level|result|reading|value|count|"
            r"time|score)\s+(?:is|was|looks|appears|seems)\s+"
            r"(?:a bit |slightly |somewhat |quite |very )?"
            r"(?:high|low|elevated|raised|reduced|poor|bad|concerning|"
            r"borderline)\b",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "invented_score",
        "produced a score, grade or age figure this application does not have",
        re.compile(
            r"\b(?:your (?:overall )?score|health score|wellness score|"
            r"mobility score|balance score|fitness score|risk score|"
            r"body age|fitness age|metabolic age|grade of|you scored)\b",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "capability_claim",
        "described a webcam observation as a clinical measurement",
        re.compile(
            r"\byour\s+(?:range of motion|muscle strength|bone density|"
            r"bone health|fall risk|balance ability|joint health|"
            r"cardiovascular fitness|vo2)\b",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "urgency_verdict",
        "decided how urgent something is",
        re.compile(
            r"\b(?:seek (?:urgent|immediate|emergency)|urgently see|"
            r"see (?:a doctor|your doctor) (?:immediately|urgently|today|"
            r"right away)|go to (?:the )?(?:a&e|er|emergency)|"
            r"call an ambulance|this is an emergency|not an emergency|"
            r"nothing to worry about|nothing is wrong|you are fine|"
            r"you're fine|perfectly healthy)\b",
            re.IGNORECASE,
        ),
        False,
    ),
    (
        "risk_claim",
        "stated a personal risk this application cannot calculate",
        re.compile(
            r"\b(?:your risk of|puts you at risk of|at high risk|at low risk|"
            r"increases your risk of|likelihood of developing)\b",
            re.IGNORECASE,
        ),
        True,
    ),
)


def _excused_by_negation(text: str, start: int) -> bool:
    """Whether a negation shortly before the match reverses its meaning."""

    window = text[max(0, start - NEGATION_WINDOW):start]

    # A sentence boundary ends the window: a negation in the previous sentence
    # says nothing about this one.
    for boundary in (". ", "! ", "? ", "\n"):
        cut = window.rfind(boundary)

        if cut != -1:
            window = window[cut + len(boundary):]

    return bool(NEGATORS.search(window))


def check_text(text) -> list:
    """Rule descriptions broken by one piece of text. Empty means it passed."""

    if not isinstance(text, str) or not text.strip():
        return []

    broken = []

    for name, description, pattern, negatable in RULES:
        for match in pattern.finditer(text):
            if negatable and _excused_by_negation(text, match.start()):
                continue

            broken.append(description)

            break

    return broken


def _strings(payload):
    """Every string anywhere in a nested structure."""

    if isinstance(payload, str):
        yield payload

    elif isinstance(payload, dict):
        for value in payload.values():
            yield from _strings(value)

    elif isinstance(payload, (list, tuple)):
        for value in payload:
            yield from _strings(value)


def check_payload(payload) -> list:
    """Rule descriptions broken anywhere in a structured response."""

    broken = []

    for text in _strings(payload):
        for description in check_text(text):
            if description not in broken:
                broken.append(description)

    return broken


def enforce(payload):
    """Return the payload, or refuse it. The only way a response is accepted."""

    broken = check_payload(payload)

    if broken:
        raise GuardrailViolation(broken)

    return payload


def correction_instruction(broken) -> str:
    """What to tell the model on a second attempt.

    Names what was wrong and asks for the same content within the rules, rather
    than asking for something shorter or vaguer. A response that has been made
    vague to get past a check is not a safer response.
    """

    return (
        "Your previous response was rejected because it "
        + "; ".join(broken)
        + ". Write it again. Keep the same helpful content and the same level of "
        "detail, but stay inside the rules: describe only what was observed, "
        "name what is missing, and suggest general wellness habits and the kind "
        "of professional who could look at something properly. Do not diagnose, "
        "do not judge any value as high or low, do not invent a range, do not "
        "produce a score, and do not decide anything about urgency."
    )
