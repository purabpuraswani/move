"""Prints Google's raw, unfiltered response for one generateContent call.

check_openrouter.py's 404 message is a fixed, generic sentence -- it does
not show what Google actually said. This script skips that translation
and prints the real HTTP status and body, so we can see the true reason
instead of guessing from a paraphrase.

    cd backend
    .venv\\Scripts\\python.exe check_gemini_raw.py

The key is sent as a header, never printed, and never appears in the
output below (Google's own error text does not echo request headers).
"""

import json
import sys
import urllib.error
import urllib.request

import config


def main() -> int:
    if not config.GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set.")
        return 1

    model = config.GEMINI_MODEL
    url = f"{config.GEMINI_BASE_URL}/models/{model}:generateContent"

    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Say hello in one word."}]}],
    }

    print(f"POST {url}")
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
        with urllib.request.urlopen(request, timeout=30) as response:
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
