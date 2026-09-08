"""Real behaviour tests for the Gemini provider added alongside OpenRouter.

Both agents/llm.py's GeminiAgentModel and reports/extraction.py's
GeminiProvider are exercised through their transport= injection point, the
same discipline the existing OpenRouter tests use (see
test_report_pipeline_integration.py): a fake transport stands in for the
socket, but the request construction and response parsing are the real
production code, and no network call is made or claimed. Neither class
depends on pymongo or fastapi, so this file needs no self-skip guard.
"""

import json
import unittest
from unittest import mock

from agents import llm
from reports import extraction


# ---------------------------------------------------------------------------
# agents/llm.py: GeminiAgentModel
# ---------------------------------------------------------------------------


def fake_gemini_function_call(args, *, name="record_guidance"):
    """A generateContent response carrying one function call, Gemini's own
    response shape -- distinct from OpenRouter's chat-completions shape."""

    body = {
        "candidates": [
            {
                "content": {
                    "parts": [{"functionCall": {"name": name, "args": args}}]
                },
                "finishReason": "STOP",
            }
        ]
    }

    return 200, json.dumps(body)


TOOL = {
    "name": "record_guidance",
    "description": "Record structured guidance.",
    "input_schema": {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
    },
}


class GeminiAgentModelTests(unittest.TestCase):
    def test_call_returns_the_function_arguments(self):
        def transport(url, headers, payload, timeout):
            self.assertIn("generateContent", url)
            self.assertEqual(headers["x-goog-api-key"], "AIzaTestKey1234567890")
            self.assertEqual(
                payload["toolConfig"]["functionCallingConfig"]["allowedFunctionNames"],
                ["record_guidance"],
            )
            return fake_gemini_function_call({"summary": "Move gently today."})

        model = llm.GeminiAgentModel(
            api_key="AIzaTestKey1234567890", model="gemini-2.0-flash", transport=transport
        )

        result = model.call("system prompt", "user text", TOOL)

        self.assertEqual(result, {"summary": "Move gently today."})

    def test_prose_instead_of_a_function_call_is_a_failure_not_a_guess(self):
        def transport(_url, _headers, _payload, _timeout):
            body = {
                "candidates": [
                    {"content": {"parts": [{"text": "Sure, here is guidance..."}]}}
                ]
            }
            return 200, json.dumps(body)

        model = llm.GeminiAgentModel(api_key="AIzaTestKey", transport=transport)

        with self.assertRaises(llm.AgentFailed):
            model.call("system", "user", TOOL)

    def test_blocked_prompt_is_reported_as_a_failure_with_the_real_reason(self):
        def transport(_url, _headers, _payload, _timeout):
            body = {"promptFeedback": {"blockReason": "SAFETY"}, "candidates": []}
            return 200, json.dumps(body)

        model = llm.GeminiAgentModel(api_key="AIzaTestKey", transport=transport)

        with self.assertRaises(llm.AgentFailed) as caught:
            model.call("system", "user", TOOL)

        self.assertIn("SAFETY", str(caught.exception))

    def test_401_names_the_gemini_key_variable_not_openrouters(self):
        def transport(_url, _headers, _payload, _timeout):
            return 401, json.dumps({"error": {"message": "API key not valid"}})

        model = llm.GeminiAgentModel(api_key="bad-key", transport=transport)

        with self.assertRaises(llm.AgentFailed) as caught:
            model.call("system", "user", TOOL)

        self.assertIn("GEMINI_API_KEY", str(caught.exception))

    def test_a_key_shaped_like_geminis_is_redacted_from_error_text(self):
        leaking_key = "AIzaSyDaGeLeakedKeyValueLooksLikeThis123"

        def transport(_url, _headers, _payload, _timeout):
            return 403, json.dumps({"error": {"message": f"rejected key {leaking_key}"}})

        model = llm.GeminiAgentModel(api_key="whatever", transport=transport)

        # The 401/403 branch returns a fixed message that never echoes the
        # provider's own text, so the key cannot appear in it regardless.
        with self.assertRaises(llm.AgentFailed) as caught:
            model.call("system", "user", TOOL)

        self.assertNotIn(leaking_key, str(caught.exception))


class SelectModelPrefersOpenRouterThenGeminiTests(unittest.TestCase):
    """auto tries OpenRouter first (unchanged behaviour for an existing
    single-provider deployment), then falls back to Gemini -- never both
    silently, and never invents a provider when neither key is set."""

    def test_gemini_is_used_when_only_a_gemini_key_is_configured(self):
        with mock.patch.object(llm, "OPENROUTER_API_KEY", None), \
             mock.patch.object(llm, "GEMINI_API_KEY", "AIzaTestKey"):
            model = llm.select_model()

        self.assertIsInstance(model, llm.GeminiAgentModel)
        self.assertEqual(model.name, "gemini")

    def test_openrouter_is_disabled_even_when_a_key_is_present(self):
        """OpenRouter was removed from this deployment on purpose.

        This test previously asserted the opposite -- that OpenRouter won
        when both keys were configured. That preference no longer exists:
        config.py forces OPENROUTER_API_KEY to None and rewrites
        AI_PROVIDER="openrouter" to "gemini", so a stale OpenRouter key left
        in the environment (or exported as a real OS environment variable,
        which a .env file does not override) cannot pull the application
        back onto an account with no credit.

        AI_PROVIDER is patched explicitly rather than read from the
        developer's own .env, so this asserts the code's contract instead of
        whatever happens to be configured on the machine running the suite.
        """

        with mock.patch.object(llm, "AI_PROVIDER", "auto"), \
             mock.patch.object(llm, "OPENROUTER_API_KEY", "sk-or-test"), \
             mock.patch.object(llm, "GEMINI_API_KEY", "AIzaTestKey"):
            model = llm.select_model()

        self.assertIsInstance(model, llm.GeminiAgentModel)

    def test_config_refuses_to_hand_out_an_openrouter_key_at_all(self):
        """The removal is enforced in config.py, not merely preferred in
        select_model() -- otherwise any other caller reading the key would
        still reach OpenRouter."""

        import config

        self.assertIsNone(config.OPENROUTER_API_KEY)
        self.assertNotEqual(config.AI_PROVIDER, "openrouter")

    def test_neither_key_is_honestly_unavailable(self):
        with mock.patch.object(llm, "OPENROUTER_API_KEY", None), \
             mock.patch.object(llm, "GEMINI_API_KEY", None):
            model = llm.select_model()

        self.assertFalse(model.available)
        self.assertIn("OPENROUTER_API_KEY", model.reason)
        self.assertIn("GEMINI_API_KEY", model.reason)

    def test_explicit_ai_provider_gemini_is_honoured(self):
        with mock.patch.object(llm, "AI_PROVIDER", "gemini"), \
             mock.patch.object(llm, "OPENROUTER_API_KEY", "sk-or-test"), \
             mock.patch.object(llm, "GEMINI_API_KEY", "AIzaTestKey"):
            model = llm.select_model()

        self.assertIsInstance(model, llm.GeminiAgentModel)


# ---------------------------------------------------------------------------
# reports/extraction.py: GeminiProvider
# ---------------------------------------------------------------------------


def fake_gemini_extraction_response(fields, *, document_readable=True):
    body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "record_transcribed_fields",
                                "args": {
                                    "document_readable": document_readable,
                                    "document_note": "",
                                    "fields": fields,
                                },
                            }
                        }
                    ]
                },
                "finishReason": "STOP",
            }
        ]
    }

    return 200, json.dumps(body)


class GeminiProviderExtractionTests(unittest.TestCase):
    def test_extract_reads_fields_through_the_real_pipeline(self):
        def transport(url, headers, payload, timeout):
            self.assertIn("generateContent", url)
            self.assertEqual(headers["x-goog-api-key"], "AIzaTestKey")
            # The document travels as Gemini's inlineData shape, not
            # OpenRouter's data: URL -- this is the one place that would
            # silently regress to the wrong wire format.
            first_part = payload["contents"][0]["parts"][0]
            self.assertIn("inlineData", first_part)
            self.assertEqual(first_part["inlineData"]["mimeType"], "application/pdf")
            return fake_gemini_extraction_response(
                [
                    {
                        "key": "diagnosis",
                        "label": "Diagnosis",
                        "category": "diagnosis_listed_on_report",
                        "value": "Type 2 Diabetes",
                        "quoted_text": "Diagnosis: Type 2 Diabetes",
                        "page": 1,
                        "confidence": 0.95,
                    }
                ]
            )

        provider = extraction.GeminiProvider(api_key="AIzaTestKey", transport=transport)

        result = extraction.extract_candidates(b"%PDF-fake-bytes", ".pdf", provider=provider)

        self.assertEqual(len(result["fields"]), 1)
        self.assertEqual(result["fields"][0]["candidate"]["value"], "Type 2 Diabetes")
        self.assertEqual(result["provider"], "gemini")

    def test_a_provider_http_failure_never_produces_fields_silently(self):
        def failing_transport(_url, _headers, _payload, _timeout):
            return 500, json.dumps({"error": {"message": "upstream is down"}})

        provider = extraction.GeminiProvider(api_key="AIzaTestKey", transport=failing_transport)

        with self.assertRaises(extraction.ExtractionFailed):
            extraction.extract_candidates(b"%PDF-fake-bytes", ".pdf", provider=provider)

    def test_select_provider_falls_back_to_gemini_when_no_openrouter_key(self):
        with mock.patch.object(extraction, "OPENROUTER_API_KEY", None), \
             mock.patch.object(extraction, "GEMINI_API_KEY", "AIzaTestKey"):
            provider = extraction.select_provider()

        self.assertIsInstance(provider, extraction.GeminiProvider)

    def test_select_provider_is_honestly_unavailable_with_neither_key(self):
        with mock.patch.object(extraction, "OPENROUTER_API_KEY", None), \
             mock.patch.object(extraction, "GEMINI_API_KEY", None):
            provider = extraction.select_provider()

        self.assertFalse(provider.available)

        with self.assertRaises(extraction.ExtractionUnavailable):
            extraction.extract_candidates(b"%PDF-fake-bytes", ".pdf", provider=provider)


if __name__ == "__main__":
    unittest.main()
