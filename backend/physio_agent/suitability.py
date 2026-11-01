"""Conservative, non-clinical exercise suitability checks.

The exercise catalog currently contains free-text cautions, not reviewed,
condition-specific contraindication metadata. This module therefore never
claims clinical suitability: it allows a candidate only when the structured
onboarding screen is complete and reports no concern, and defers candidates
when relevant context is affirmative, incomplete, or unavailable. It does
not interpret report values or free-text conditions.
"""

HEALTH_FIELDS = (
    "diabetes",
    "hypertension",
    "heart_condition",
    "previous_injury",
    "joint_pain",
    "back_neck_pain",
    "other_conditions",
)
YES_VALUES = frozenset({"yes", "y", "true", "sometimes", "often", "occasionally"})
NO_VALUES = frozenset({"no", "n", "false"})


def _assessment_evidence_for_need(movement_evidence, target_need):
    movement_evidence = movement_evidence or {}
    if target_need == "mobility_need":
        return {"shoulder": movement_evidence.get("shoulder")}
    if target_need == "stability_need":
        return {"balance": movement_evidence.get("balance")}
    if target_need == "functional_movement_need":
        return {
            "shoulder": movement_evidence.get("shoulder"),
            "balance": movement_evidence.get("balance"),
        }
    return {}


def evaluate_exercise_suitability(
    exercise,
    constraints_result,
    *,
    reported_health_context,
    confirmed_medical_context,
    confirmed_medical_context_status,
    target_need,
    movement_evidence,
):
    """Return an auditable decision using only explicit metadata and answers.

    The catalog's caution text is surfaced verbatim; it is not parsed into
    invented clinical rules. A positive or unresolved medical answer defers
    the exercise for clarification/professional review because this catalog
    cannot establish whether that context conflicts with a particular move.
    """
    exercise_id = exercise.get("exercise_id")
    exercise_body_areas = list(exercise.get("target_body_area") or [])
    reported_health_context = reported_health_context or {}
    values = reported_health_context.get("values") or {}
    status = reported_health_context.get("status", "UNKNOWN")
    missing = list(reported_health_context.get("missing_fields") or [])
    evidence = []
    conflicts = []
    additional = []
    metadata_constraints = []

    if not isinstance(constraints_result, dict) or "error" in constraints_result:
        metadata_constraints_status = "UNAVAILABLE"
        exclusion_reason = (
            "Exercise safety metadata could not be retrieved; the exercise was deferred."
        )
        additional.append("Exercise-library safety metadata")
        evaluation_status = "DEFERRED_METADATA_UNAVAILABLE"
        metadata_constraints = []
    elif (
        constraints_result.get("exerciseId") != exercise_id
        or constraints_result.get("difficulty") != exercise.get("difficulty")
        or not isinstance(constraints_result.get("safetyConstraints"), list)
        or not constraints_result.get("safetyConstraints")
        or any(not isinstance(note, str) or not note.strip()
               for note in constraints_result.get("safetyConstraints", []))
    ):
        metadata_constraints_status = "INCOMPLETE"
        exclusion_reason = (
            "Exercise safety metadata was incomplete; the exercise was deferred."
        )
        additional.append("Complete exercise-library safety metadata")
        evaluation_status = "DEFERRED_METADATA_UNAVAILABLE"
    else:
        metadata_constraints_status = "AVAILABLE"
        metadata_constraints = list(constraints_result["safetyConstraints"])
        exclusion_reason = None
        evaluation_status = "NO_REPORTED_CONFLICT"

    affirmative = []
    unresolved = []
    for field in HEALTH_FIELDS:
        value = values.get(field)
        if field == "other_conditions":
            if isinstance(value, str) and value.strip():
                affirmative.append(field)
                evidence.append("An additional condition was self-reported; its text is not interpreted by this system.")
            elif field in missing:
                unresolved.append(field)
            continue
        normalized = value.strip().lower() if isinstance(value, str) else ""
        if normalized in YES_VALUES:
            affirmative.append(field)
            evidence.append(f"Self-reported {field.replace('_', ' ')}.")
        elif normalized not in NO_VALUES:
            unresolved.append(field)

    reports = (confirmed_medical_context or {}).get("reports") or []
    confirmed_status = confirmed_medical_context_status or "UNKNOWN"

    if reports:
        evidence.append("One or more user-confirmed medical reports are on file; report values were not clinically interpreted.")
    elif confirmed_status == "UNKNOWN":
        evidence.append("Confirmed-report status is unknown.")

    if missing or unresolved or status != "COMPLETE":
        evaluation_status = "DEFERRED_CONTEXT_REQUIRED"
        unresolved_names = sorted(set(missing + unresolved))
        additional.extend(
            f"Clarify self-reported {field.replace('_', ' ')}"
            for field in unresolved_names
        )
        if not unresolved_names:
            additional.append("Complete the self-reported health screen")
        conflicts.append("The available health screen is incomplete; absence of an answer is not treated as a negative answer.")
        exclusion_reason = "Required user-reported health context is incomplete or unknown."
    elif affirmative:
        evaluation_status = "DEFERRED_HEALTHCARE_REVIEW"
        if set(affirmative) & {"previous_injury", "joint_pain", "back_neck_pain"}:
            conflicts.append(
                "Reported injury/pain details do not identify affected body areas or current status; "
                f"the catalog lists this exercise for {', '.join(exercise_body_areas) or 'unspecified body areas'}, "
                "and has no structured rule to determine whether they overlap."
            )
        conflicts.append(
            "Reported health context is present, but the exercise catalog has no reviewed rule to establish exercise-specific suitability."
        )
        additional.append("Clarify the reported condition, injury, limitation, or pain and obtain healthcare-professional review of exercise suitability.")
        exclusion_reason = "Exercise-specific suitability cannot be established from the available catalog metadata and reported health context."
    elif reports:
        evaluation_status = "DEFERRED_HEALTHCARE_REVIEW"
        conflicts.append(
            "Confirmed medical information is present, but this system does not interpret report values or map them to exercise contraindications."
        )
        additional.append("Have a healthcare professional review the confirmed report in relation to this exercise.")
        exclusion_reason = "Exercise-specific suitability cannot be established from confirmed medical information using the implemented rules."
    elif confirmed_status == "AVAILABLE":
        evaluation_status = "DEFERRED_CONTEXT_REQUIRED"
        conflicts.append("Confirmed-report status says information is available, but no confirmed report records were supplied.")
        additional.append("Reload the user's confirmed medical reports before evaluating this exercise.")
        exclusion_reason = "Confirmed medical-context data is inconsistent or incomplete."
    elif confirmed_status == "UNKNOWN":
        evaluation_status = "DEFERRED_CONTEXT_REQUIRED"
        conflicts.append("The system cannot determine whether confirmed medical context exists.")
        additional.append("Confirm whether relevant medical reports exist and complete the self-reported health screen.")
        exclusion_reason = "Medical-context availability is unknown."

    if metadata_constraints_status != "AVAILABLE":
        evaluation_status = "DEFERRED_METADATA_UNAVAILABLE"
        exclusion_reason = (
            "Exercise safety metadata could not be fully verified; the exercise was deferred."
        )
        conflicts.append("The exercise metadata safety check could not be completed.")

    included = evaluation_status == "NO_REPORTED_CONFLICT"
    return {
        "exercise_id": exercise_id,
        "exercise_body_areas": exercise_body_areas,
        "target_need": target_need,
        "decision": "INCLUDE" if included else "EXCLUDE",
        "status": evaluation_status,
        "clinical_approval": False,
        "metadata_constraints_status": metadata_constraints_status,
        "metadata_constraints": metadata_constraints,
        "reported_context_status": status,
        "confirmed_medical_context_status": confirmed_status,
        "evidence_used": evidence,
        "assessment_evidence": _assessment_evidence_for_need(
            movement_evidence, target_need
        ),
        "potential_conflicts": conflicts,
        "additional_information_required": sorted(set(additional)),
        "exclusion_reason": None if included else exclusion_reason,
    }
