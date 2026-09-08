"""Prints Google's raw response for a forced function call, the exact
request shape the app actually uses (unlike check_gemini_raw.py, which
sends plain text). check_openrouter.py's "having a problem" message hides
the real status and body behind a generic sentence for any 5xx -- this
shows the real one.

    cd backend
    .venv\\Scripts\\python.exe check_gemini_tool_call.py

The key is sent as a header, never printed.
"""

import json
import sys
import urllib.error
import urllib.request

import config

PROBE_TOOL = {
    "name": "record_check",
    "description": "Report that the connection works.",
    "parameters": {
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
    if not config.GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set.")
        return 1

    model = config.GEMINI_AGENT_MODEL
    url = f"{config.GEMINI_BASE_URL}/models/{model}:generateContent"

    payload = {
        "systemInstruction": {
            "parts": [{"text": "You are checking a connection. Call the tool you are given."}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Reply through the tool to confirm you received this."}],
            }
        ],
        "tools": [{"functionDeclarations": [PROBE_TOOL]}],
        "toolConfig": {
            "functionCallingConfig": {
                "mode": "ANY",
                "allowedFunctionNames": ["record_check"],
            },
        },
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3000},
    }

    print(f"POST {url}")
    print()
    print("Payload:")
    print(json.dumps(payload, indent=2))
    print()

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": config.GEMINI_API_KEY,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            print(f"Status: {response.status}")
            print(response.read().decode("utf-8"))
            return 0

    except urllib.error.HTTPError as error:
        print(f"Status: {error.code}")
        print(error.read().decode("utf-8", "replace"))
        return 1

    except urllib.error.URLError as error:
        print(f"Could not reach Google: {error.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
