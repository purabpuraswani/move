"""Central environment configuration for the MoveWell AI backend.

Every value is resolved once, at import time, so a misconfigured environment
fails immediately on startup with an actionable message instead of failing
later on the first request that happens to need it.
"""

import os

from dotenv import load_dotenv


load_dotenv()


class ConfigError(RuntimeError):
    """Raised at startup when required configuration is missing or unusable."""


def _first_env(*names):
    """Return the first non-empty value among the given variable names."""

    for name in names:
        value = os.getenv(name)

        if value and value.strip():
            return value.strip()

    return None


# ---------------------------------------------------------------------------
# Database
#
# MONGODB_URI is the only value that has to change to move between a local
# MongoDB instance and MongoDB Atlas. MONGO_URL is the name this project used
# previously and is still accepted so existing local .env files keep working.
# ---------------------------------------------------------------------------

MONGODB_URI = _first_env("MONGODB_URI", "MONGO_URL")

if not MONGODB_URI:
    raise ConfigError(
        "MONGODB_URI is not set.\n"
        "\n"
        "Create backend/.env (copy backend/.env.example) and set one of:\n"
        "  local  ->  MONGODB_URI=mongodb://localhost:27017\n"
        "  atlas  ->  MONGODB_URI=mongodb+srv://<user>:<password>"
        "@<cluster>.mongodb.net/?retryWrites=true&w=majority\n"
        "\n"
        "Nothing else needs to change to switch between local and Atlas."
    )


MONGODB_DB_NAME = _first_env("MONGODB_DB_NAME", "MONGO_DB") or "movewell"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

JWT_MIN_SECRET_LENGTH = 32

JWT_SECRET = _first_env("JWT_SECRET")

if not JWT_SECRET:
    raise ConfigError(
        "JWT_SECRET is not set.\n"
        "\n"
        "Tokens cannot be signed without it, and it must never have a default\n"
        "value in source control. Generate one and add it to backend/.env:\n"
        "\n"
        '  python -c "import secrets; print(secrets.token_urlsafe(48))"\n'
        "\n"
        "  JWT_SECRET=<paste the generated value>"
    )

if len(JWT_SECRET) < JWT_MIN_SECRET_LENGTH:
    raise ConfigError(
        f"JWT_SECRET is too short ({len(JWT_SECRET)} characters). "
        f"Use at least {JWT_MIN_SECRET_LENGTH}.\n"
        "\n"
        "Generate a strong value with:\n"
        '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )


JWT_ALGORITHM = _first_env("JWT_ALGORITHM") or "HS256"


def _positive_int(name, default):
    raw = _first_env(name)

    if raw is None:
        return default

    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(
            f"{name} must be a whole number of minutes, got {raw!r}."
        ) from None

    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero, got {value}.")

    return value


JWT_EXPIRES_MINUTES = _positive_int("JWT_EXPIRES_MINUTES", 60 * 24 * 7)


# ---------------------------------------------------------------------------
# CORS
#
# Comma-separated list. The defaults cover the Vite dev server on both
# hostnames it is commonly reached on; deployment sets CORS_ORIGINS explicitly.
# ---------------------------------------------------------------------------

_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"

CORS_ORIGINS = [
    origin.strip()
    for origin in (_first_env("CORS_ORIGINS") or _DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]


# ---------------------------------------------------------------------------
# Medical report storage
#
# Uploaded files go through a storage interface (reports/storage.py) rather
# than being written to a hard-coded path. Local disk is the only backend in
# this build; the setting exists so a deployment can add durable object storage
# without the pipeline changing.
# ---------------------------------------------------------------------------

REPORT_STORAGE_BACKEND = (_first_env("REPORT_STORAGE_BACKEND") or "local").lower()

REPORT_STORAGE_DIR = _first_env("REPORT_STORAGE_DIR") or "uploads/reports"

REPORT_MAX_UPLOAD_MB = _positive_int("REPORT_MAX_UPLOAD_MB", 15)

REPORT_MAX_UPLOAD_BYTES = REPORT_MAX_UPLOAD_MB * 1024 * 1024

# Extensions the pipeline can actually do something with: a PDF or a photo of
# a printed report. Anything else would be stored and then sit there unread.
REPORT_ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")


# ---------------------------------------------------------------------------
# AI provider (optional)
#
# Nothing here is required, and none of it raises on startup. A missing API key
# is a legitimate configuration: report extraction then reports itself as
# unavailable and the manual-entry path is used instead. It must never cause
# invented values, and it must never stop the rest of the API from running.
#
# Keys are read here, server-side, and are never sent to the browser.
#
# The provider is OpenRouter, which exposes an OpenAI-compatible
# chat-completions API in front of many underlying models. That is the reason
# the model is a setting rather than a constant: changing which model reads
# reports or writes guidance is an environment change, not a code change.
# ---------------------------------------------------------------------------

# Providers this build knows how to talk to. The checks below are written
# against this tuple rather than against a hard-coded provider name so that
# adding one later is a change in one place.
SUPPORTED_AI_PROVIDERS = ("openrouter", "gemini")

# "auto" uses whichever supported provider has credentials, trying them in
# the order they are checked below (OpenRouter first, then Gemini, which
# keeps an existing single-provider deployment's behaviour unchanged);
# "none" disables AI even if a key is present, which is useful for testing
# the unavailable path.
AI_PROVIDER = (_first_env("AI_PROVIDER") or "auto").lower()

# OpenRouter is disabled for this deployment (user request: Gemini only).
# Normalising "openrouter" to "gemini" here, and forcing the key to None
# below, means this holds even if OPENROUTER_API_KEY or AI_PROVIDER=openrouter
# is still set as a real Windows environment variable somewhere -- an OS
# environment variable is not overridden by a value in backend/.env, so
# disabling it in .env alone would not have been enough.
if AI_PROVIDER == "openrouter":
    AI_PROVIDER = "gemini"

OPENROUTER_API_KEY = None

# Includes the /api/v1 prefix, so callers append the endpoint path only. A
# self-hosted gateway that speaks the same API can be pointed at here.
OPENROUTER_BASE_URL = (
    _first_env("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
).rstrip("/")

# Any OpenRouter model that supports both tool calling and image input works.
# Both are required: tool calling is how structured output is enforced, and
# image input is how a photographed report is read. The default is picked for
# that combination at low cost. See backend/.env.example for alternatives.
OPENROUTER_MODEL = _first_env("OPENROUTER_MODEL") or "google/gemini-2.5-flash"

# Optional attribution headers. OpenRouter uses them for its own dashboards and
# model rankings; neither is required and neither carries key material.
OPENROUTER_SITE_URL = _first_env("OPENROUTER_SITE_URL")

OPENROUTER_APP_TITLE = _first_env("OPENROUTER_APP_TITLE") or "MoveWell AI"

# How a PDF is turned into something the model can see. Left unset on purpose:
# OpenRouter then chooses, which is the behaviour that keeps working when it
# changes its engine names. Set to "native", "pdf-text" or "mistral-ocr" to
# force one.
OPENROUTER_PDF_ENGINE = _first_env("OPENROUTER_PDF_ENGINE")

AI_REQUEST_TIMEOUT_SECONDS = _positive_int("AI_REQUEST_TIMEOUT_SECONDS", 90)

AI_MAX_OUTPUT_TOKENS = _positive_int("AI_MAX_OUTPUT_TOKENS", 4096)


# The guidance agents get their own model setting, defaulting to the same model
# as report reading. Transcribing a scanned document and writing a few
# paragraphs are different jobs with different costs, and a deployment may well
# want a cheaper model for the second without changing the first.
AI_AGENT_MODEL = _first_env("AI_AGENT_MODEL") or OPENROUTER_MODEL

AI_AGENT_MAX_OUTPUT_TOKENS = _positive_int("AI_AGENT_MAX_OUTPUT_TOKENS", 3000)


# ---------------------------------------------------------------------------
# Gemini (Google), a second provider
#
# Reached directly against the Generative Language API rather than through
# OpenRouter's proxy, for a deployment that has a Gemini key but no OpenRouter
# credit. Auth is a request header, not a bearer token, and the response shape
# is Google's own rather than the OpenAI-compatible one OpenRouter exposes --
# both differences are handled where the HTTP call is made (agents/llm.py,
# reports/extraction.py), not translated into a shared shape here.
# ---------------------------------------------------------------------------

GEMINI_API_KEY = _first_env("GEMINI_API_KEY", "GOOGLE_API_KEY")

GEMINI_BASE_URL = (
    _first_env("GEMINI_BASE_URL")
    or "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")

# Any Gemini model that supports both function calling and image/PDF input
# works. "gemini-flash-latest" is an alias Google keeps pointed at its
# current flash model, so it stays valid as dated snapshot names (like
# gemini-2.0-flash, gemini-2.5-flash) are retired -- Google has been
# retiring those every few months. Pin a dated name only if a deployment
# needs a specific version's behaviour to stop changing under it.
GEMINI_MODEL = _first_env("GEMINI_MODEL") or "gemini-flash-latest"

GEMINI_AGENT_MODEL = _first_env("GEMINI_AGENT_MODEL") or GEMINI_MODEL


# Whether a key for the provider this build used previously is still in the
# environment. Only its presence is recorded, never its value, so that the
# "not set up" message can say something useful to somebody who set the old
# variable and is wondering why nothing happened.
LEGACY_ANTHROPIC_KEY_PRESENT = bool(_first_env("ANTHROPIC_API_KEY"))


def ai_provider_available() -> bool:
    """Whether any AI provider is usable with the current environment."""

    if AI_PROVIDER == "none":
        return False

    if AI_PROVIDER != "auto" and AI_PROVIDER not in SUPPORTED_AI_PROVIDERS:
        return False

    if AI_PROVIDER == "openrouter":
        return bool(OPENROUTER_API_KEY)

    if AI_PROVIDER == "gemini":
        return bool(GEMINI_API_KEY)

    return bool(OPENROUTER_API_KEY) or bool(GEMINI_API_KEY)

