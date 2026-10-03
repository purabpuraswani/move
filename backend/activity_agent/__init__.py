"""Exercise & Physical Activity specialist.

Owns one question and no other: how much the user actually moves in a
day, and what a realistic next step in that volume is. It never selects
an exercise (physio_agent), never reads a medical report, never decides
an escalation (safety), and never reasons about sleep (recovery_agent).
"""

from activity_agent.agent import AGENT_ID, run_activity_agent
from activity_agent.evidence import build_activity_view
from activity_agent.reasoning import assess_activity

__all__ = ["AGENT_ID", "run_activity_agent", "build_activity_view", "assess_activity"]
