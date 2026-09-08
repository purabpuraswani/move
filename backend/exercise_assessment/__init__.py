"""Structured exercise performance results — the backend half of:

    RGB Webcam -> MoveNet -> Keypoints (browser)
        -> exercise-specific deterministic rules (browser, src/exerciseAssessment/)
        -> structured movement metrics (browser)
        -> Exercise Result (crosses to the backend, here)

This package never sees a webcam frame, a keypoint, or a pose sequence — by
the time anything reaches it, the browser has already reduced a recording to
a handful of numbers (repetitions, duration, a range-of-motion angle, and so
on). schema.py enforces that boundary the same way
backend/assessments/schema.py already does for the three baseline tests:
structural limits generous enough for what a real result looks like, and a
name-based filter that rejects anything shaped like frame or pose data
outright, so a future bug elsewhere can't quietly start smuggling it through
here.

    schema.py    the Exercise Result shape, validated against the specific
                 exercise it claims to be for (its metrics must be a subset
                 of that exercise's declared measurable_metrics — a result
                 cannot claim a metric the library doesn't say this exercise
                 produces).
"""
