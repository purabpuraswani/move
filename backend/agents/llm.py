"""The model call the guidance agents share.

The provider is OpenRouter, reached over its OpenAI-compatible
chat-completions API. Which model actually answers is an environment setting,
so this file is about the shape of the exchange rather than about any one
vendor.

Deliberately small. It sends a system prompt, one block of text about the user,
and a tool the model is forced to call, and it returns that tool's input. There
is no conversation state, no streaming and no free-form prose path, because
every one of those would be another way for a response to arrive in a shape
nothing validated.

Three properties are the reason this file exists rather than each agent calling
the API itself.

The transport is injectable. `AgentModel(key, transport=...)` replaces the
socket while leaving the request construction and the response parsing real, so
the agents can be exercised without a network or an API key.

Structured output is mandatory. `tool_choice` forces the model into the tool, and
a response that arrives as prose is treated as a failure rather than scraped. A
loosely parsed response is exactly where an unvalidated sentence gets in.

Unavailability is not failure. With no key configured the caller gets
AgentUnavailable, which means "this feature is not set up on this server" and
leads to a screen saying so. AgentFailed means something was tried and went
wrong. Collapsing the two would either alarm a user about a configuration
choice or hide a real outage.

The HTTP handling here overlaps with reports/extraction.py, which does the same
thing for document transcription. They are kept apart on purpose: that one sends
base64 documents and is covered by its own tests, and folding both into one
client would mean changing a verified path to serve a new one.
"""

import json
import re
import urllib.error
import urllib.request

from config import (
    AI_AGENT_MAX_OUTPUT_TOKENS,
    AI_AGENT_MODEL,
    AI_PROVIDER,
    AI_REQUEST_TIMEOUT_SECONDS,
    GEMINI_AGENT_MODEL,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    LEGACY_ANTHROPIC_KEY_PRESENT,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_TITLE,
    OPENROUTER_BASE_URL,
    OPENROUTER_SITE_URL,
    SUPPORTED_AI_PROVIDERS,
)

# Low, not zero. Guidance that reads like a form letter is ignored, and the
# structure is fixed by the tool schema either way, so the variation this allows
# is in wording rather than in what gets said.
TEMPERATURE = 0.2


class AgentUnavailable(RuntimeError):
    """No AI provider is configured, so no agent can run."""


class AgentFailed(RuntimeError):
    """A provider was configured but the attempt did not produce usable output."""


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
        return error.code, error.read().decode("utf-8", "replace")

    except urllib.error.URLError as error:
        raise AgentFailed(
            f"The AI provider could not be reached: {error.reason}"
        ) from error

    except TimeoutError:
        raise AgentFailed(
            f"The AI provider did not respond within "
            f"{AI_REQUEST_TIMEOUT_SECONDS} seconds."
        ) from None


def _headers(api_key: str) -> dict:
    """Authorization, plus OpenRouter's optional attribution headers.

    The attribution headers are what OpenRouter uses to label traffic in its own
    dashboard. They are omitted when unset rather than filled with a guess.
    """

    headers = {"Authorization": f"Bearer {api_key}"}

    if OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = OPENROUTER_SITE_URL

    if OPENROUTER_APP_TITLE:
        headers["X-Title"] = OPENROUTER_APP_TITLE

    return headers


def _openai_tool(tool: dict) -> dict:
    """A tool description in the shape the chat-completions API expects.

    The agents declare their tools once, in agents/outputs.py, with the schema
    under `input_schema`. Translating here at request time rather than there
    keeps the agent definitions free of any provider's wire format, which is the
    whole reason those definitions did not have to change when the provider did.
    """

    schema = tool.get("input_schema") or tool.get("parameters") or {}

    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description") or "",
            "parameters": schema,
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
# OpenRouter keys look like sk-or-...; Gemini keys look like AIza....
# Either shape could appear in an upstream error message quoting the
# offending credential back.
_KEY_SHAPED = re.compile(r"sk-[A-Za-z0-9_\-]{4,}|AIza[A-Za-z0-9_\-]{10,}")


def _redacted(text: str) -> str:
    return _KEY_SHAPED.sub("sk-***", text).strip()


def _describe_http_error(status: int, body: str) -> str:
    """A message for whoever has to fix the configuration.

    The provider's own text is included because it is specific. The API key is
    never part of it, so this is safe to return to a caller.
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
            "credit, or set AI_AGENT_MODEL in backend/.env to a cheaper model."
        )

    if status == 404:
        return (
            f"The AI provider does not recognise the model {AI_AGENT_MODEL!r}. "
            "Check AI_AGENT_MODEL or OPENROUTER_MODEL in backend/.env against "
            "the model list at openrouter.ai/models."
        )

    if status == 429:
        return "The AI provider is rate limiting requests. Try again shortly."

    if status >= 500:
        return "The AI provider is having a problem. Try again shortly."

    return f"The AI provider refused the request ({status}). {detail}".strip()


class BaseModel:
    """What an agent needs from a model."""

    name = "abstract"
    model = None
    available = False

    def call(self, system: str, user_text: str, tool: dict,
             extra_user_text=None) -> dict:
        raise NotImplementedError


class UnavailableModel(BaseModel):
    """Stands in when nothing is configured, and says so when used."""

    name = "none"
    available = False

    def __init__(self, reason: str):
        self.reason = reason

    def call(self, system: str, user_text: str, tool: dict,
             extra_user_text=None) -> dict:
        raise AgentUnavailable(self.reason)


class AgentModel(BaseModel):
    """An OpenRouter model, answering only through a forced tool call."""

    name = "openrouter"
    available = True

    def __init__(self, api_key: str, model: str = AI_AGENT_MODEL, transport=None):
        self.api_key = api_key
        self.model = model
        self._post = transport or _urllib_post

    def call(self, system: str, user_text: str, tool: dict,
             extra_user_text=None) -> dict:
        # One text block rather than several. The chat-completions API does
        # accept a list of content parts, but a plain string is handled
        # identically by every model behind OpenRouter, and the text that
        # reaches the model is the same either way.
        user_content = user_text

        if extra_user_text:
            user_content = f"{user_text}\n\n{extra_user_text}"

        payload = {
            "model": self.model,
            "max_tokens": AI_AGENT_MAX_OUTPUT_TOKENS,
            "temperature": TEMPERATURE,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            "tools": [_openai_tool(tool)],
            "tool_choice": {
                "type": "function",
                "function": {"name": tool["name"]},
            },
        }

        status, body = self._post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            _headers(self.api_key),
            payload,
            AI_REQUEST_TIMEOUT_SECONDS,
        )

        if status != 200:
            raise AgentFailed(_describe_http_error(status, body))

        try:
            parsed = json.loads(body)

        except json.JSONDecodeError:
            raise AgentFailed(
                "The AI provider returned a response that could not be read."
            ) from None

        return _tool_input(parsed, tool["name"])


def _gemini_headers(api_key: str) -> dict:
    """Gemini authenticates with a header, not a bearer token."""

    return {"x-goog-api-key": api_key}


def _gemini_function_declaration(tool: dict) -> dict:
    """A tool description in the shape Gemini's function calling expects.

    Same source shape agents/outputs.py already declares (input_schema); only
    the field names on the wire differ from _openai_tool()'s translation.
    """

    schema = tool.get("input_schema") or tool.get("parameters") or {}

    return {
        "name": tool["name"],
        "description": tool.get("description") or "",
        "parameters": schema,
    }


def _gemini_describe_http_error(status: int, body: str, model: str) -> str:
    """A message for whoever has to fix the configuration, read against
    Gemini's own error shape rather than OpenRouter's."""

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
            "GEMINI_AGENT_MODEL or GEMINI_MODEL in backend/.env against the "
            "model list at ai.google.dev/gemini-api/docs/models."
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


class GeminiAgentModel(BaseModel):
    """A Gemini model, answering only through a forced function call.

    Reached directly against the Generative Language API rather than through
    OpenRouter, for a deployment that has a Gemini key but no OpenRouter
    credit. The forced-tool-call discipline AgentModel follows is preserved
    here with Gemini's own request and response shapes.
    """

    name = "gemini"
    available = True

    def __init__(self, api_key: str, model: str = GEMINI_AGENT_MODEL,
                 transport=None):
        self.api_key = api_key
        self.model = model
        self._post = transport or _urllib_post

    def call(self, system: str, user_text: str, tool: dict,
             extra_user_text=None) -> dict:
        user_content = user_text

        if extra_user_text:
            user_content = f"{user_text}\n\n{extra_user_text}"

        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "tools": [
                {"functionDeclarations": [_gemini_function_declaration(tool)]}
            ],
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": [tool["name"]],
                },
            },
            "generationConfig": {
                "temperature": TEMPERATURE,
                "maxOutputTokens": AI_AGENT_MAX_OUTPUT_TOKENS,
            },
        }

        status, body = self._post(
            f"{GEMINI_BASE_URL}/models/{self.model}:generateContent",
            _gemini_headers(self.api_key),
            payload,
            AI_REQUEST_TIMEOUT_SECONDS,
        )

        if status != 200:
            raise AgentFailed(
                _gemini_describe_http_error(status, body, self.model)
            )

        try:
            parsed = json.loads(body)

        except json.JSONDecodeError:
            raise AgentFailed(
                "The AI provider returned a response that could not be read."
            ) from None

        return _gemini_function_call_args(parsed, tool["name"])


def _gemini_function_call_args(response: dict, tool_name: str) -> dict:
    """The structured result out of a generateContent response, or a failure.

    A Gemini response carries the call under
    candidates[0].content.parts[].functionCall, with args already as an
    object rather than a JSON string -- a different shape from the
    chat-completions response _tool_input() reads, so it is not reused here.
    """

    if not isinstance(response, dict):
        raise AgentFailed("The AI provider returned an unusable result.")

    if response.get("error"):
        detail = _error_detail(response["error"]) or "no detail given"

        raise AgentFailed(f"The AI provider reported a problem: {detail}")

    # A prompt blocked before generation carries only promptFeedback, no
    # candidates -- worth naming specifically rather than falling through to
    # the generic "answered in prose" message below, which would not be true.
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

        if function_call.get("name") not in (None, tool_name):
            continue

        args = function_call.get("args")

        if isinstance(args, dict):
            return args

    if block_reason:
        raise AgentFailed(
            f"The AI provider blocked the prompt before answering "
            f"({block_reason}). Nothing was generated."
        )

    if candidate.get("finishReason") == "MAX_TOKENS":
        raise AgentFailed(
            "The AI provider ran out of output space before it finished "
            "answering. Raise AI_AGENT_MAX_OUTPUT_TOKENS in backend/.env."
        )

    raise AgentFailed(
        "The AI provider answered in prose instead of the structured form "
        "that was requested, so nothing could be used. If this keeps "
        "happening, set GEMINI_AGENT_MODEL in backend/.env to a model that "
        "supports function calling."
    )


def _tool_input(response: dict, tool_name: str) -> dict:
    """The structured result, or a failure.

    A chat-completions response carries the call under
    choices[0].message.tool_calls, and the arguments arrive as a JSON string
    rather than as an object. Some models behind OpenRouter send an object
    anyway, so both are accepted.
    """

    if not isinstance(response, dict):
        raise AgentFailed("The AI provider returned an unusable result.")

    # A 200 response can still carry an error object in place of choices.
    if response.get("error"):
        detail = _error_detail(response["error"]) or "no detail given"

        raise AgentFailed(f"The AI provider reported a problem: {detail}")

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

        if function.get("name") not in (None, tool_name):
            continue

        arguments = function.get("arguments")

        if isinstance(arguments, dict):
            return arguments

        if isinstance(arguments, str) and arguments.strip():
            try:
                decoded = json.loads(arguments)

            except json.JSONDecodeError:
                # Almost always output that stopped mid-JSON, and the fix is a
                # setting rather than a retry, so name the setting.
                raise AgentFailed(
                    "The AI provider's structured answer was not valid JSON. "
                    "If this keeps happening the answer is being cut off: "
                    "raise AI_AGENT_MAX_OUTPUT_TOKENS in backend/.env."
                ) from None

            if isinstance(decoded, dict):
                return decoded

    if choice.get("finish_reason") == "length":
        raise AgentFailed(
            "The AI provider ran out of output space before it finished "
            "answering. Raise AI_AGENT_MAX_OUTPUT_TOKENS in backend/.env."
        )

    # Prose instead of the tool means there is nothing here that has been
    # through a schema. Reading it anyway is how an unchecked sentence reaches
    # a user.
    raise AgentFailed(
        "The AI provider answered in prose instead of the structured form that "
        "was requested, so nothing could be used. If this keeps happening, set "
        "AI_AGENT_MODEL in backend/.env to a model that supports tool calling."
    )


def _no_key_reason() -> str:
    """Why guidance is unavailable when no key is configured."""

    reason = (
        "AI guidance is not set up on this server: no AI provider key is "
        "configured. Set OPENROUTER_API_KEY or GEMINI_API_KEY in "
        "backend/.env. Your assessment results and confirmed report values "
        "are still available on their own screens."
    )

    if LEGACY_ANTHROPIC_KEY_PRESENT:
        # Worth saying explicitly. Somebody who set the variable this project
        # used previously would otherwise be looking at "no key is configured"
        # with a key sitting right there in their .env.
        reason += (
            " (ANTHROPIC_API_KEY is set, but this build does not call "
            "Anthropic directly. Set OPENROUTER_API_KEY or GEMINI_API_KEY "
            "instead.)"
        )

    return reason


def select_model(transport=None) -> BaseModel:
    """The model the current environment supports."""

    if AI_PROVIDER == "none":
        return UnavailableModel(
            "AI guidance is switched off in this environment (AI_PROVIDER=none)."
        )

    if AI_PROVIDER != "auto" and AI_PROVIDER not in SUPPORTED_AI_PROVIDERS:
        return UnavailableModel(
            f"AI_PROVIDER={AI_PROVIDER!r} is not a provider this build supports. "
            f"Set it to {' or '.join(SUPPORTED_AI_PROVIDERS)!r} or 'auto'."
        )

    # OpenRouter is removed from this deployment. config.py forces
    # OPENROUTER_API_KEY to None, but the removal is enforced here as well
    # rather than resting on that single value: this is the point where a
    # provider is actually chosen, so leaving a live OpenRouter branch would
    # mean any future path that set the key -- a refactor, a different import
    # order, an exported OS environment variable -- silently put the
    # application back on an account with no credit. AgentModel itself is
    # kept: it is still constructible with an explicit key, which is how the
    # tests exercise it, but it is never selected automatically.
    if AI_PROVIDER in ("auto", "gemini") and GEMINI_API_KEY:
        return GeminiAgentModel(GEMINI_API_KEY, transport=transport)

    return UnavailableModel(_no_key_reason())


def model_status() -> dict:
    """Whether guidance can run. No key material and no base URL."""

    model = select_model()

    return {
        "available": model.available,
        "provider": model.name if model.available else None,
        "model": model.model if model.available else None,
        "reason": None if model.available else model.reason,
    }
