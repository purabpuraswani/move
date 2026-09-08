"""The Behaviour/Habit Agent: a specialist agent over the Behaviour Guidance Library.

Mirrors backend/physio_agent/ and backend/nutrition_agent/ exactly in
structure and discipline. Responsibility: sedentary behaviour, movement
breaks, exercise frequency, and habit-formation guidance — built from the
same real questionnaire signals need_assessment.rules.assess_behaviour_need()
already reads (daily_sitting_hours, daily_screen_hours, exercise_days,
exercise_minutes). This agent does not diagnose a mental health condition,
claim to treat one, or make an unsupported psychological claim, and it
does not fabricate adherence history — this application tracks none yet.
"""
