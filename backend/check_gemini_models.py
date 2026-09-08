"""Lists the Gemini models this API key can actually use.

check_openrouter.py already told you the key is accepted but the model
name is not recognised. Model names on the free API change over time, so
rather than guess again, this asks Google directly which models exist for
this key and which of those support both generateContent (function
calling and text) and the free tier is likely to include.

    cd backend
    .venv\\Scripts\\python.exe check_gemini_models.py

Nothing is written anywhere. The key is never printed.
"""

import json
import sys
import urllib.error
import urllib.request

import config


def main() -> int:
    if not config.GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set in backend/.env.")
        return 1

    url = f"{config.GEMINI_BASE_URL}/models"
    request = urllib.request.Request(
        url, headers={"x-goog-api-key": config.GEMINI_API_KEY}
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")

    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        print(f"Request failed ({error.code}): {detail}")
        return 1

    except urllib.error.URLError as error:
        print(f"Could not reach Google: {error.reason}")
        return 1

    data = json.loads(body)
    models = data.get("models", [])

    print(f"{len(models)} models visible to this key.\n")
    print("Models that support generateContent (usable by this app):")
    print("-" * 60)

    usable = []

    for model in models:
        methods = model.get("supportedGenerationMethods", [])
        name = model.get("name", "").removeprefix("models/")

        if "generateContent" in methods:
            usable.append(name)
            print(f"  {name}")

    print()
    print("Pick one of the names above (without the 'models/' prefix) and")
    print("set it in backend/.env as both:")
    print()
    print("  GEMINI_MODEL=<name>")
    print("  GEMINI_AGENT_MODEL=<name>")
    print()
    print("Prefer a 'flash' model over a 'pro' one for the free tier -- it")
    print("has a much higher free-tier rate limit.")

    return 0 if usable else 1


if __name__ == "__main__":
    sys.exit(main())
