"""The Nutrition Agent: a specialist agent over the Nutrition Guidance Library.

Mirrors backend/physio_agent/ exactly in structure and discipline:

    input_contract.py   the minimized structured input this agent receives
                         (never the raw User State, never raw food-tracking
                         data — this application collects none)
    plan_schema.py       the Nutrition Plan shape it produces
    tool_client.py        the interface + test-only in-process double
    mcp_client.py         the real MCP client (McpNutritionToolClient)
    agent.py              the execution lifecycle (AGENT_ID = "nutrition")

This agent does not diagnose a nutritional deficiency, prescribe a
supplement or medication, provide a restrictive diet, claim to be a
dietitian or doctor, or invent a user's food preferences it was not told.
"""
