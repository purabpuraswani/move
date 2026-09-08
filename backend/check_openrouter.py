"""One real request to whichever AI provider is configured (OpenRouter or
Gemini), through the application's own code path.

A quick way to tell whether AI guidance and report reading are actually working,
separately from the rest of the app. It uses the same configuration, the same
model selection and the same forced-tool call the agents use, so a success here
means the pieces the agents depend on are in place, and a failure prints the
message a user would have been shown.

    cd backend
    .venv\\Scripts\\python.exe check_openrouter.py

Costs one short request, typically a fraction of a cent. Nothing is written to
the database and no report is touched.

The API key is never printed. Only whether it is present, and its length.
"""

import sys

import config
from agents.llm import AgentFailed, AgentUnavailable, model_status, select_model
from reports.extraction import extraction_status

PROBE_TOOL = {
    "name": "record_check",
    "description": "Report that the connection works.",
    "input_schema": {
        "type": "object",
        "properties": {
            "provider_reply": {
                "type": "string",
                "description": "A short sentence confirming you received this.",
            },
        },
        "required": ["provider_reply"],
    },
}


def main() -> int:
    print()
    print("Configuration")
    print("-" * 60)

    openrouter_key = config.OPENROUTER_API_KEY
    gemini_key = config.GEMINI_API_KEY

    print(f"  AI_PROVIDER            {config.AI_PROVIDER}")
    print(
        "  OPENROUTER_API_KEY     "
        + (f"present, {len(openrouter_key)} characters" if openrouter_key else "NOT SET")
    )
    print(f"  OPENROUTER_MODEL       {config.OPENROUTER_MODEL}")
    print(f"  AI_AGENT_MODEL         {config.AI_AGENT_MODEL}")
    print(f"  OPENROUTER_BASE_URL    {config.OPENROUTER_BASE_URL}")
    print(
        "  GEMINI_API_KEY         "
        + (f"present, {len(gemini_key)} characters" if gemini_key else "NOT SET")
    )
    print(f"  GEMINI_MODEL           {config.GEMINI_MODEL}")
    print(f"  GEMINI_AGENT_MODEL     {config.GEMINI_AGENT_MODEL}")

    if config.LEGACY_ANTHROPIC_KEY_PRESENT:
        print()
        print("  Note: ANTHROPIC_API_KEY is set and is no longer read.")
        print("  This build calls OpenRouter or Gemini. ANTHROPIC_API_KEY is unused.")

    print()
    print("What the app reports about itself")
    print("-" * 60)

    guidance = model_status()
    reading = extraction_status()

    print(f"  AI guidance            {'available' if guidance['available'] else 'unavailable'}")

    if not guidance["available"]:
        print(f"    reason: {guidance['reason']}")

    print(f"  Report reading         {'available' if reading['available'] else 'unavailable'}")

    if not reading["available"]:
        print(f"    reason: {reading['reason']}")

    model = select_model()

    if not model.available:
        print()
        print("No request was sent, because nothing is configured to send it to.")
        print("Set OPENROUTER_API_KEY or GEMINI_API_KEY in backend/.env and run this again.")

        return 1

    print()
    print(f"Sending one request to {model.model}")
    print("-" * 60)

    try:
        result = model.call(
            "You are checking a connection. Call the tool you are given.",
            "Reply through the tool to confirm you received this message.",
            PROBE_TOOL,
        )

    except AgentUnavailable as error:
        print(f"  Not configured: {error}")

        return 1

    except AgentFailed as error:
        print(f"  FAILED: {error}")
        print()
        print("The message above names what to change. Nothing else is wrong with")
        print("the app: this script exercises only the provider call.")

        return 1

    reply = (result or {}).get("provider_reply") or "(the tool returned no text)"

    print(f"  OK. The model answered through the tool: {reply}")
    print()
    print("Tool calling works, the model name is valid and the key is accepted,")
    print("so the wellness guide, care navigator and report reader can all run.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
