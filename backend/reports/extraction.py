"""Reading candidate values off a report document.

This is the only part of the system that puts a document in front of a language
model, and it is deliberately narrow: it transcribes, and it says where each
transcription came from. It does not interpret, compare, score, or conclude
anything, and nothing it returns is treated as true until the user has said so.

Three properties matter more than the extraction quality itself.

It never invents. The instruction to the model is to transcribe printed text and
to return nothing for anything it cannot read. Whatever comes back is validated
against reports/schema.py, and a field that does not survive validation is
dropped and counted, not guessed at.

It fails visibly. With no provider configured, or with a provider that errors,
the caller gets an exception that says so. There is no fallback that produces
plausible-looking values, because a fabricated haemoglobin reading is worse than
no reading at all.

It carries no dependencies. The HTTP call is made with the standard library, so
this module works with the packages the project already installs, and the
transport can be replaced in tests without a network.
"""

import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

from config import (
    AI_MAX_OUTPUT_TOKENS,
    AI_PROVIDER,
    AI_REQUEST_TIMEOUT_SECONDS,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    LEGACY_ANTHROPIC_KEY_PRESENT,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_TITLE,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    OPENROUTER_PDF_ENGINE,
    OPENROUTER_SITE_URL,
    SUPPORTED_AI_PROVIDERS,
)
from reports.schema import (
    FIELD_CATEGORIES,
    SOURCE_AI_EXTRACTION,
    build_candidate_fields,
)


class ExtractionUnavailable(RuntimeError):
    """No AI provider is configured, so extraction cannot be attempted.

    Distinct from a failure on purpose: nothing was tried, the uploaded file is
    fine, and the user should be offered the manual path rather than told their
    report is broken.
    """


class ExtractionFailed(RuntimeError):
    """A provider was configured but the attempt did not produce usable output."""


MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


# ---------------------------------------------------------------------------
# The instruction
#
# Written as a transcription task, not an analysis task. Every "do not" here
# corresponds to something the rest of the application promises not to do, so
# the prompt is part of that promise rather than a hint.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You transcribe values from a medical report image or PDF into structured data.

You are a transcriber, not a clinician and not an analyst. Your entire job is to
copy what is printed on the document.

Rules you must follow:

1. Only record text that is actually printed on the document. If you cannot read
   something, leave it out. Never estimate, never complete a partially visible
   number, and never fill a gap with a typical or expected value.
2. Never interpret. Do not say whether a value is high, low, normal, abnormal,
   concerning or healthy. Do not add a diagnosis, an impression, a risk, or a
   recommendation of your own.
3. Never calculate. If a ratio or an index is not printed, it does not exist for
   your purposes.
4. Copy units exactly as printed. If no unit is printed, leave the unit empty.
5. If the document prints a reference range next to a value, copy it verbatim
   into printed_reference_range. This is the issuing laboratory's own printed
   range. Never write a range that is not printed on the document.
6. Do not record personal identifiers. Skip the patient's name, address, phone
   number, email, hospital or insurance ID, and any national ID number. Record
   the medical values only.
7. If the document is unreadable, is not a medical report, or contains no
   values, return an empty list of fields. An empty result is a correct answer.

For each field set confidence to how certain you are that you transcribed that
value correctly from the page: 1.0 for text that is perfectly legible, lower
when print is faint, skewed, handwritten or ambiguous. Confidence is about
legibility, not about the value's medical meaning.

Put the exact printed text you read into quoted_text so a human can check your
transcription against the page.

Choose category from:
- lab_result: a measured laboratory value
- vital_sign: blood pressure, pulse, temperature, weight, height and similar
- medication: a drug named on the report
- diagnosis_listed_on_report: a condition the document itself states
- clinical_note_text: a sentence or note printed on the report, copied verbatim
- report_metadata: the report's own date, type, or issuing facility
"""

USER_PROMPT = """\
Transcribe the medical values printed in this document.

Return every value you can read clearly. Leave out anything you cannot read, and
leave out all personal identifying information.
"""

# Structured output is requested as a tool call so the response comes back as
# validated JSON rather than prose that has to be scraped.
EXTRACTION_TOOL = {
    "name": "record_transcribed_fields",
    "description": (
        "Record values transcribed verbatim from the report document. "
        "Only include values that are printed on the document."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "document_readable": {
                "type": "boolean",
                "description": (
                    "False if the document could not be read at all, or is not "
                    "a medical report."
                ),
            },
            "document_note": {
                "type": "string",
                "description": (
                    "One short factual sentence about the document's legibility, "
                    "if anything is worth telling the user. No medical comment."
                ),
            },
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": (
                                "lowercase_with_underscores identifier, e.g. "
                                "haemoglobin, fasting_glucose, blood_pressure"
                            ),
                        },
                        "label": {
                            "type": "string",
                            "description": "The name as printed on the document",
                        },
                        "category": {
                            "type": "string",
                            "enum": list(FIELD_CATEGORIES),
                        },
                        "value": {
                            "type": "string",
                            "description": "The value exactly as printed",
                        },
                        "unit": {
                            "type": "string",
                            "description": "The unit exactly as printed, or empty",
                        },
                        "printed_reference_range": {
                            "type": "string",
                            "description": (
                                "The reference range printed on this document "
                                "beside the value, verbatim. Empty if none is "
                                "printed."
                            ),
                        },
                        "quoted_text": {
                            "type": "string",
                            "description": "The line of text you read this from",
                        },
                        "page": {
                            "type": "integer",
                            "description": "1-based page number",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "0 to 1, how legible the text was",
                        },
                    },
                    "required": ["key", "label", "value"],
                },
            },
        },
        "required": ["document_readable", "fields"],
    },
}


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def _urllib_post(url: str, headers: dict, payload: dict, timeout: int) -> tuple:
    """POST JSON with the standard library. Returns (status, decoded body)."""

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "content-type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")

    except urllib.error.HTTPError as error:
        # The body of an error response usually says what was wrong, and it is
        # far more useful than the status code alone.
        return error.code, error.read().decode("utf-8", "replace")

    except urllib.error.URLError as error:
        raise ExtractionFailed(
            f"The AI provider could not be reached: {error.reason}"
        ) from error

    except TimeoutError:
        raise ExtractionFailed(
            f"The AI provider did not respond within "
            f"{AI_REQUEST_TIMEOUT_SECONDS} seconds."
        ) from None


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class ExtractionProvider:
    """What the pipeline needs from any provider."""

    name = "abstract"
    model = None
    available = False

    def extract(self, file_bytes: bytes, extension: str) -> dict:
        raise NotImplementedError


def _gemini_headers(api_key: str) -> dict:
    """Gemini authenticates with a header, not a bearer token."""

    return {"x-goog-api-key": api_key}


def _gemini_content_block(file_bytes: bytes, extension: str) -> dict:
    """The document as inline base64 data, in Gemini's request shape."""

    media_type = MEDIA_TYPES.get(extension)

    if media_type is None:
        raise ExtractionFailed(
            f"{extension} is not a file type this extractor can read."
        )

    encoded = base64.b64encode(file_bytes).decode("ascii")

    return {"inlineData": {"mimeType": media_type, "data": encoded}}


def _gemini_function_declaration(tool: dict) -> dict:
    return {
        "name": tool["name"],
        "description": tool.get("description") or "",
        "parameters": tool.get("input_schema") or tool.get("parameters") or {},
    }


def _gemini_describe_http_error(status: int, body: str, model: str) -> str:
    """A message that helps whoever has to fix the configuration, read
    against Gemini's own error shape rather than OpenRouter's."""

    detail = ""

    try:
        detail = _error_detail(json.loads(body).get("error"))

    except (json.JSONDecodeError, AttributeError):
        detail = ""

    if status in (400, 401, 403):
        return (
            "The AI provider rejected the API key. Check GEMINI_API_KEY in "
            "backend/.env. A Gemini key starts with 'AIza'."
        )

    if status == 404:
        return (
            f"The AI provider does not recognise the model {model!r}. Check "
            "GEMINI_MODEL in backend/.env against the model list at "
            "ai.google.dev/gemini-api/docs/models."
        )

    if status == 429:
        return (
            "The AI provider is rate limiting requests. Gemini's free tier "
            "has a low per-minute and per-day limit; try again shortly, or "
            "add billing at aistudio.google.com, or switch back to "
            "OPENROUTER_API_KEY in backend/.env."
        )

    if status >= 500:
        return "The AI provider is having a problem. Try again shortly."

    return f"The AI provider refused the request ({status}). {detail}".strip()


def _gemini_function_call_args(response: dict) -> dict:
    """The structured transcription out of a generateContent response, or a
    failure. Gemini's function-call arguments arrive as an object already,
    under candidates[0].content.parts[].functionCall.args -- a different
    shape from the chat-completions response _tool_input() reads, so it is
    not reused here."""

    if not isinstance(response, dict):
        raise ExtractionFailed("The AI provider returned an unusable result.")

    if response.get("error"):
        detail = _error_detail(response["error"]) or "no detail given"

        raise ExtractionFailed(f"The AI provider reported a problem: {detail}")

    prompt_feedback = response.get("promptFeedback") or {}
    block_reason = prompt_feedback.get("blockReason")

    candidates = response.get("candidates") or []
    candidate = (
        candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    )
    content = candidate.get("content") or {}
    parts = content.get("parts") or []

    for part in parts:
        if not isinstance(part, dict):
            continue

        function_call = part.get("functionCall")

        if not isinstance(function_call, dict):
            continue

        args = function_call.get("args")

        if isinstance(args, dict):
            return args

    if block_reason:
        raise ExtractionFailed(
            f"The AI provider blocked the document before reading it "
            f"({block_reason}). Nothing was transcribed."
        )

    if candidate.get("finishReason") == "MAX_TOKENS":
        raise ExtractionFailed(
            "The AI provider ran out of output space before it finished "
            "transcribing. Raise AI_MAX_OUTPUT_TOKENS in backend/.env."
        )

    raise ExtractionFailed(
        "The AI provider did not return the structured transcription that "
        "was requested. If this keeps happening, set GEMINI_MODEL in "
        "backend/.env to a model that supports function calling and image "
        "input."
    )


class GeminiProvider(ExtractionProvider):
    """Reads the document with a model reached directly against Google's
    Generative Language API, for a deployment that has a Gemini key but no
    OpenRouter credit. The document travels the same way an image does for
    OpenRouterProvider, only as inline base64 data in Gemini's own request
    shape rather than a data: URL.
    """

    name = "gemini"
    available = True

    def __init__(self, api_key: str, model: str = GEMINI_MODEL, transport=None):
        self.api_key = api_key
        self.model = model
        self._post = transport or _urllib_post

    def extract(self, file_bytes: bytes, extension: str) -> dict:
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        _gemini_content_block(file_bytes, extension),
                        {"text": USER_PROMPT},
                    ],
                }
            ],
            "tools": [
                {
                    "functionDeclarations": [
                        _gemini_function_declaration(EXTRACTION_TOOL)
                    ]
                }
            ],
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": [EXTRACTION_TOOL["name"]],
                },
            },
            "generationConfig": {"maxOutputTokens": AI_MAX_OUTPUT_TOKENS},
        }

        status, body = self._post(
            f"{GEMINI_BASE_URL}/models/{self.model}:generateContent",
            _gemini_headers(self.api_key),
            payload,
            AI_REQUEST_TIMEOUT_SECONDS,
        )

        if status != 200:
            raise ExtractionFailed(
                _gemini_describe_http_error(status, body, self.model)
            )

        try:
            parsed = json.loads(body)

        except json.JSONDecodeError:
            raise ExtractionFailed(
                "The AI provider returned a response that could not be read."
            ) from None

        return _gemini_function_call_args(parsed)


class UnavailableProvider(ExtractionProvider):
    """Stands in when nothing is configured, and says so when used."""

    name = "none"
    available = False

    def __init__(self, reason: str):
        self.reason = reason

    def extract(self, file_bytes: bytes, extension: str) -> dict:
        raise ExtractionUnavailable(self.reason)


class OpenRouterProvider(ExtractionProvider):
    """Reads the document with a model reached through OpenRouter.

    The document is sent as-is, which avoids a PDF text-extraction dependency
    and works for photographs of printed reports as well as generated PDFs.
    """

    name = "openrouter"
    available = True

    def __init__(self, api_key: str, model: str = OPENROUTER_MODEL, transport=None):
        self.api_key = api_key
        self.model = model
        self._post = transport or _urllib_post

    def _content_block(self, file_bytes: bytes, extension: str) -> dict:
        media_type = MEDIA_TYPES.get(extension)

        if media_type is None:
            raise ExtractionFailed(
                f"{extension} is not a file type this extractor can read."
            )

        encoded = base64.b64encode(file_bytes).decode("ascii")
        data_url = f"data:{media_type};base64,{encoded}"

        if media_type == "application/pdf":
            # A PDF travels as a file part with a filename, which is what the
            # document handling keys off. A photograph or scan of a printed
            # report travels as an image.
            return {
                "type": "file",
                "file": {
                    "filename": f"report{extension}",
                    "file_data": data_url,
                },
            }

        return {"type": "image_url", "image_url": {"url": data_url}}

    def extract(self, file_bytes: bytes, extension: str) -> dict:
        payload = {
            "model": self.model,
            "max_tokens": AI_MAX_OUTPUT_TOKENS,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        self._content_block(file_bytes, extension),
                        {"type": "text", "text": USER_PROMPT},
                    ],
                },
            ],
            "tools": [_openai_tool(EXTRACTION_TOOL)],
            "tool_choice": {
                "type": "function",
                "function": {"name": EXTRACTION_TOOL["name"]},
            },
        }

        if extension == ".pdf" and OPENROUTER_PDF_ENGINE:
            # Only sent when a deployment has explicitly chosen an engine.
            # Omitted, the provider picks, which is the behaviour that keeps
            # working when engine names change.
            payload["plugins"] = [
                {"id": "file-parser", "pdf": {"engine": OPENROUTER_PDF_ENGINE}}
            ]

        status, body = self._post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            _headers(self.api_key),
            payload,
            AI_REQUEST_TIMEOUT_SECONDS,
        )

        if status != 200:
            raise ExtractionFailed(_describe_http_error(status, body))

        try:
            parsed = json.loads(body)

        except json.JSONDecodeError:
            raise ExtractionFailed(
                "The AI provider returned a response that could not be read."
            ) from None

        return _tool_input(parsed)


def _headers(api_key: str) -> dict:
    """Authorization, plus OpenRouter's optional attribution headers."""

    headers = {"Authorization": f"Bearer {api_key}"}

    if OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = OPENROUTER_SITE_URL

    if OPENROUTER_APP_TITLE:
        headers["X-Title"] = OPENROUTER_APP_TITLE

    return headers


def _openai_tool(tool: dict) -> dict:
    """The extraction tool in the shape the chat-completions API expects.

    EXTRACTION_TOOL above stays in the schema-first form it was written and
    tested in; the translation to a provider's wire format happens here, at
    request time, so the prompt and the schema are not entangled with it.
    """

    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description") or "",
            "parameters": tool.get("input_schema") or tool.get("parameters") or {},
        },
    }


def _error_detail(error) -> str:
    """The provider's own message out of an error object, if there is one."""

    if isinstance(error, dict):
        return _redacted(str(error.get("message") or ""))

    if isinstance(error, str):
        return _redacted(error)

    return ""


# Anything shaped like an API key. OpenRouter is a proxy, so an error it returns
# may be an upstream provider's, and several of those quote the offending key
# back — in full or partially masked. This text ends up in an HTTP response, so
# it is the one place a credential could escape by accident.
_KEY_SHAPED = re.compile(r"sk-[A-Za-z0-9_\-]{4,}|AIza[A-Za-z0-9_\-]{10,}")


def _redacted(text: str) -> str:
    return _KEY_SHAPED.sub("sk-***", text).strip()


def _describe_http_error(status: int, body: str) -> str:
    """A message that helps whoever has to fix the configuration.

    The provider's own message is included because it is specific, but the API
    key never appears in it and this text is safe to show.
    """

    detail = ""

    try:
        detail = _error_detail(json.loads(body).get("error"))

    except (json.JSONDecodeError, AttributeError):
        detail = ""

    if status in (401, 403):
        return (
            "The AI provider rejected the API key. Check OPENROUTER_API_KEY in "
            "backend/.env. An OpenRouter key starts with 'sk-or-'."
        )

    if status == 402:
        return (
            "The OpenRouter account has no credit left for this request. Add "
            "credit, or set OPENROUTER_MODEL in backend/.env to a cheaper model."
        )

    if status == 404:
        return (
            f"The AI provider does not recognise the model "
            f"{OPENROUTER_MODEL!r}. Check OPENROUTER_MODEL in backend/.env "
            "against the model list at openrouter.ai/models."
        )

    if status == 429:
        return "The AI provider is rate limiting requests. Try again shortly."

    if status >= 500:
        return "The AI provider is having a problem. Try again shortly."

    return f"The AI provider refused the request ({status}). {detail}".strip()


def _tool_input(response: dict) -> dict:
    """Pull the structured result out of a chat-completions response.

    The call arrives under choices[0].message.tool_calls, with its arguments as
    a JSON string. Some models send an object instead, so both are accepted.
    """

    if not isinstance(response, dict):
        raise ExtractionFailed("The AI provider returned an unusable result.")

    # A 200 response can still carry an error object in place of choices.
    if response.get("error"):
        detail = _error_detail(response["error"]) or "no detail given"

        raise ExtractionFailed(f"The AI provider reported a problem: {detail}")

    choices = response.get("choices") or []
    choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = choice.get("message")

    if not isinstance(message, dict):
        message = {}

    for call in message.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue

        function = call.get("function")

        if not isinstance(function, dict):
            continue

        # The name is deliberately not matched. One tool is offered and the
        # call is forced, so anything that comes back is that tool, and some
        # models normalise the name they echo. Rejecting on a mangled name
        # would throw away a good transcription.
        arguments = function.get("arguments")

        if isinstance(arguments, dict):
            return arguments

        if isinstance(arguments, str) and arguments.strip():
            try:
                decoded = json.loads(arguments)

            except json.JSONDecodeError:
                # A long report transcription cut off mid-JSON is the usual
                # cause, and the fix is a setting rather than a retry.
                raise ExtractionFailed(
                    "The AI provider's transcription was not valid JSON. If "
                    "this keeps happening the answer is being cut off: raise "
                    "AI_MAX_OUTPUT_TOKENS in backend/.env."
                ) from None

            if isinstance(decoded, dict):
                return decoded

    if choice.get("finish_reason") == "length":
        raise ExtractionFailed(
            "The AI provider ran out of output space before it finished "
            "transcribing. Raise AI_MAX_OUTPUT_TOKENS in backend/.env."
        )

    # A model that answered in prose instead of calling the tool has not given
    # us anything we can store. Treated as a failure rather than parsed
    # loosely, because loose parsing is where invented values creep in.
    raise ExtractionFailed(
        "The AI provider did not return the structured transcription that was "
        "requested. If this keeps happening, set OPENROUTER_MODEL in "
        "backend/.env to a model that supports tool calling and image input."
    )


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def _no_key_reason() -> str:
    """Why extraction is unavailable when no key is configured."""

    reason = (
        "Automatic reading of reports is not set up on this server: no AI "
        "provider key is configured. Set OPENROUTER_API_KEY or "
        "GEMINI_API_KEY in backend/.env. You can still enter the values "
        "from your report yourself."
    )

    if LEGACY_ANTHROPIC_KEY_PRESENT:
        # Somebody who set the variable this project used previously would
        # otherwise read "no key is configured" with a key sitting in their .env.
        reason += (
            " (ANTHROPIC_API_KEY is set, but this build does not call "
            "Anthropic directly. Set OPENROUTER_API_KEY or GEMINI_API_KEY "
            "instead.)"
        )

    return reason


def select_provider(transport=None) -> ExtractionProvider:
    """The provider the current environment supports."""

    if AI_PROVIDER == "none":
        return UnavailableProvider(
            "Automatic reading of reports is switched off in this environment "
            "(AI_PROVIDER=none). You can still enter your values yourself."
        )

    if AI_PROVIDER != "auto" and AI_PROVIDER not in SUPPORTED_AI_PROVIDERS:
        return UnavailableProvider(
            f"AI_PROVIDER={AI_PROVIDER!r} is not a provider this build "
            f"supports. Set it to {' or '.join(SUPPORTED_AI_PROVIDERS)!r} or "
            "'auto'."
        )

    # Removed here as well as in config.py, for the reason given in
    # agents/llm.py's select_model(): this is where the choice is actually
    # made, so the removal is enforced at the decision point rather than
    # depending solely on the key being None. OpenRouterProvider stays
    # constructible with an explicit key for the tests that inject it.
    if AI_PROVIDER in ("auto", "gemini") and GEMINI_API_KEY:
        return GeminiProvider(GEMINI_API_KEY, transport=transport)

    return UnavailableProvider(_no_key_reason())


def extraction_status() -> dict:
    """What the interface should tell the user about extraction.

    Only whether it works and which provider it is. No key material, and no
    base URL, which can itself be sensitive in a proxied deployment.
    """

    provider = select_provider()

    return {
        "available": provider.available,
        "provider": provider.name if provider.available else None,
        "reason": None if provider.available else provider.reason,
    }


# ---------------------------------------------------------------------------
# The step the pipeline calls
# ---------------------------------------------------------------------------


def extract_candidates(file_bytes: bytes, extension: str, *, provider=None) -> dict:
    """Transcribe a document into validated candidate fields.

    Returns the fields, the provenance recorded against them, anything that was
    dropped in validation, and whatever the provider said about legibility.
    Raises ExtractionUnavailable or ExtractionFailed; it never returns a
    partial success dressed up as a full one.
    """

    provider = provider or select_provider()

    if not provider.available:
        raise ExtractionUnavailable(getattr(provider, "reason", "not configured"))

    if not file_bytes:
        raise ExtractionFailed("There is no file to read.")

    raw = provider.extract(file_bytes, extension.lower())

    if not isinstance(raw, dict):
        raise ExtractionFailed("The AI provider returned an unusable result.")

    now = datetime.now(timezone.utc)

    provenance = {
        "source": SOURCE_AI_EXTRACTION,
        "provider": provider.name,
        "model": provider.model,
        "extracted_at": now,
    }

    fields, rejected = build_candidate_fields(
        raw.get("fields"), provenance=provenance
    )

    readable = raw.get("document_readable")

    return {
        "fields": fields,
        "rejected": rejected,
        "provider": provider.name,
        "model": provider.model,
        "document_readable": bool(readable) if readable is not None else None,
        "document_note": (raw.get("document_note") or "").strip()[:400] or None,
        "extracted_at": now,
    }


def read_extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()
