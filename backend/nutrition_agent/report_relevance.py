"""Whether a user's confirmed medical reports make nutrition relevant.

This is a RELEVANCE test, not a clinical one. It answers one question:
"does this user's confirmed record contain measurements a nutrition
specialist would ordinarily want to take into account?" It never answers
"is this value abnormal" or "does this user have a condition".

Three disciplines hold here, and each is load-bearing:

* Only CONFIRMED values are read. The report pipeline
  (reports/schema.py's `confirmed_values`) already drops anything the
  user has not attested to, so an AI extraction the user never reviewed
  cannot activate a specialist.

* The printed value is never compared against the printed reference
  range to decide relevance. Doing so would be inferring a condition
  from a single number, which is exactly what this project refuses to
  do. A confirmed glucose result is nutrition-relevant whether it is
  high, low, or unremarkable -- what it changes is that the Nutrition
  specialist should be *involved*, not what it should conclude.

* Matching is on the field's own key and printed label, by token. Keys
  come from the extractor as free-form `lowercase_with_underscores`
  (reports/extraction.py), so an exact-key allowlist would silently miss
  `fasting_glucose` while matching `glucose`. Tokens match either.

The output is evidence sentences that quote what the report contains and
nothing more, so anything built on top of this can explain itself
without making a claim the data does not support.
"""

from reports.schema import (
    CATEGORY_DIAGNOSIS_ON_REPORT,
    CATEGORY_LAB_RESULT,
    CATEGORY_VITAL_SIGN,
    CATEGORY_LABELS,
)

# Categories whose contents can bear on diet and lifestyle at all.
# Medication, free clinical note text and report metadata are excluded:
# acting on those would mean interpreting prose or prescriptions, which
# is a clinician's job and not this system's.
NUTRITION_RELEVANT_CATEGORIES = frozenset(
    {CATEGORY_LAB_RESULT, CATEGORY_VITAL_SIGN, CATEGORY_DIAGNOSIS_ON_REPORT}
)

# Substrings that make a measurement dietary-relevant. Deliberately
# about metabolism, lipids, and the common nutritional markers -- not an
# attempt to cover clinical medicine. Anything not listed here simply
# does not activate the specialist, which is the safe direction to fail.
NUTRITION_RELEVANT_TOKENS = (
    # Glycaemic
    "glucose",
    "hba1c",
    "glycated",
    "glycosylated",
    # Lipids
    "cholesterol",
    "triglyceride",
    "ldl",
    "hdl",
    "lipid",
    # Common nutritional markers
    "vitamin",
    "b12",
    "folate",
    "ferritin",
    "iron",
    "haemoglobin",
    "hemoglobin",
    # Electrolytes and renal/hepatic markers that ordinarily bear on diet
    "sodium",
    "potassium",
    "calcium",
    "uric acid",
    "uric_acid",
    "urea",
    "creatinine",
    # Body composition and pressure
    "bmi",
    "body mass",
    "body_mass",
    "waist",
    "blood pressure",
    "blood_pressure",
    # Conditions a report may itself list, read as printed and never derived
    "diabet",
    "obes",
    "anaem",
    "anem",
    "dyslipid",
    "hypertens",
    "thyroid",
)


def _matches(value: dict) -> bool:
    """True when this confirmed field is one a dietitian would want."""

    if (value.get("category") or "") not in NUTRITION_RELEVANT_CATEGORIES:
        return False

    haystack = f"{value.get('key') or ''} {value.get('label') or ''}".lower()

    return any(token in haystack for token in NUTRITION_RELEVANT_TOKENS)


def nutrition_relevant_values(confirmed_reports) -> list:
    """The confirmed fields that make nutrition relevant, in report order.

    `confirmed_reports` is the list under
    `medical_context.data.confirmed_reports.reports` -- the same shape
    reports/store.py's `serialise_confirmed_report` produces. Anything
    that is not a dict, or carries no `values`, contributes nothing
    rather than raising: a malformed record should not be able to
    activate or crash a specialist.
    """

    matched = []

    for report in confirmed_reports or []:
        if not isinstance(report, dict):
            continue

        for value in report.get("values") or []:
            if isinstance(value, dict) and _matches(value):
                matched.append(
                    {
                        "report_id": report.get("id") or report.get("report_id"),
                        "key": value.get("key"),
                        "label": value.get("label"),
                        "category": value.get("category"),
                    }
                )

    return matched


def report_nutrition_evidence(confirmed_reports) -> dict:
    """{"relevant": bool, "matched": [...], "evidence": [str, ...]}.

    The evidence sentences state what the confirmed report contains and
    stop there. They do not say a value is high, low, abnormal, or
    indicative of anything -- the specialist that reads them is
    responsible for general dietary support and for telling the user to
    discuss the figures with their clinician.
    """

    matched = nutrition_relevant_values(confirmed_reports)

    if not matched:
        return {"relevant": False, "matched": [], "evidence": []}

    evidence = []
    seen = set()

    for entry in matched:
        name = entry["label"] or entry["key"]
        category = CATEGORY_LABELS.get(entry["category"], entry["category"])
        sentence = (
            f"A medical report this user confirmed records "
            f"{name} ({category})."
        )

        if sentence not in seen:
            seen.add(sentence)
            evidence.append(sentence)

    return {"relevant": True, "matched": matched, "evidence": evidence}
