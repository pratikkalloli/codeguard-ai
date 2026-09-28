"""Provider tests use mocked HTTP responses and never require an API key/network."""

import json
import os
import unittest
from urllib.error import HTTPError, URLError
import io
from unittest.mock import patch

from codeguard.providers import OpenAIResponsesProvider, ProviderError


class _FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class ProviderTests(unittest.TestCase):
    def test_missing_api_key_has_actionable_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ProviderError, "OPENAI_API_KEY"):
                OpenAIResponsesProvider().generate("write add")

    @patch("codeguard.providers.openai_responses.urlopen")
    def test_response_text_is_parsed_and_key_is_environment_only(self, urlopen):
        urlopen.return_value = _FakeResponse(
            {
                "id": "resp_test",
                "model": "test-model",
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": "answer"}]}
                ],
                "usage": {"input_tokens": 14, "output_tokens": 20, "total_tokens": 34},
            }
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret", "CODEGUARD_OPENAI_MODEL": "test-model"}):
            generated = OpenAIResponsesProvider().generate("Write add.")
        self.assertEqual(generated.text, "answer")
        self.assertEqual(generated.model_name, "test-model")
        self.assertEqual(generated.total_tokens, 34)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertEqual(json.loads(request.data)["store"], False)
        self.assertNotIn("test-secret", request.data.decode("utf-8"))

    @patch("codeguard.providers.openai_responses.urlopen")
    def test_empty_api_output_is_reported(self, urlopen):
        urlopen.return_value = _FakeResponse({"output": []})
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}):
            with self.assertRaisesRegex(ProviderError, "no text output"):
                OpenAIResponsesProvider().generate("Write add.")

    @patch("codeguard.providers.openai_responses.urlopen")
    def test_rate_limit_has_specific_recovery_message(self, urlopen):
        urlopen.side_effect = HTTPError(
            "https://api.openai.com/v1/responses", 429, "Too Many Requests", {}, io.BytesIO(b"{}")
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}):
            with self.assertRaisesRegex(ProviderError, "rate or usage limit"):
                OpenAIResponsesProvider().generate("Write add.")

    @patch("codeguard.providers.openai_responses.urlopen")
    def test_output_token_limit_is_reported(self, urlopen):
        urlopen.return_value = _FakeResponse(
            {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}):
            with self.assertRaisesRegex(ProviderError, "output-token limit"):
                OpenAIResponsesProvider().generate("Write add.")

    @patch("codeguard.providers.openai_responses.urlopen", side_effect=URLError("offline"))
    def test_network_failure_is_reported_without_exposing_request_secrets(self, _urlopen):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}):
            with self.assertRaisesRegex(ProviderError, "Could not reach") as caught:
                OpenAIResponsesProvider().generate("Write add.")
        self.assertNotIn("test-secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
