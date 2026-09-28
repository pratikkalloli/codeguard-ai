"""Optional OpenAI Responses API provider using the official HTTP endpoint."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from codeguard.providers.base import GeneratedResponse, ProviderError


API_URL = "https://api.openai.com/v1/responses"
MAX_OUTPUT_TOKENS = 1200


@dataclass
class OpenAIResponsesProvider:
    """Call the OpenAI Responses API; read the secret only from the environment."""

    model_name: str | None = None
    timeout_seconds: float = 60.0
    provider_name: str = "OpenAI"

    def _api_key(self) -> str:
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key.strip():
            raise ProviderError(
                "OPENAI_API_KEY is not configured. Use Manual paste, or set the key in your environment and restart the app."
            )
        return key.strip()

    def generate(self, question: str) -> GeneratedResponse:
        if not question or not question.strip():
            raise ProviderError("Enter a coding question before requesting a model response.")
        key = self._api_key()
        model = self.model_name or os.environ.get("CODEGUARD_OPENAI_MODEL", "gpt-6-astra")
        payload = {
            "model": model,
            "store": False,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "input": (
                "Answer the coding question. Include a complete Python solution in a fenced "
                "```python code block and explain the key behavior in plain language.\n\n"
                f"Coding question:\n{question.strip()}"
            ),
        }
        request = Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 429:
                raise ProviderError(
                    "OpenAI rate or usage limit reached (HTTP 429). Wait and retry, or check your API account limits."
                ) from None
            if error.code in {401, 403}:
                raise ProviderError(
                    f"OpenAI rejected the API credentials or access (HTTP {error.code}); verify the configured key and account access."
                ) from None
            if error.code == 400:
                raise ProviderError(
                    "OpenAI rejected the request (HTTP 400). Check the model name and input size; the request may exceed an input or usage limit."
                ) from None
            if error.code >= 500:
                raise ProviderError(
                    f"OpenAI reported a service error (HTTP {error.code}). Retry later."
                ) from None
            raise ProviderError(f"OpenAI request failed with HTTP {error.code}.") from None
        except (URLError, TimeoutError, OSError) as error:
            raise ProviderError(f"Could not reach the OpenAI API: {type(error).__name__}.") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError("OpenAI returned an unreadable response.") from None

        if not isinstance(body, dict):
            raise ProviderError("OpenAI returned a response with an invalid structure.")
        if body.get("status") == "incomplete":
            details = body.get("incomplete_details")
            reason = details.get("reason", "") if isinstance(details, dict) else ""
            if reason == "max_output_tokens":
                raise ProviderError(
                    f"The response reached the app's {MAX_OUTPUT_TOKENS} output-token limit. "
                    "Shorten the question or change MAX_OUTPUT_TOKENS in the provider module."
                )
            raise ProviderError("OpenAI returned an incomplete response; retry with a shorter question.")
        if body.get("error"):
            raise ProviderError("OpenAI returned an API error instead of a generated response.")
        output_parts = []
        output_items = body.get("output", [])
        for item in output_items if isinstance(output_items, list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            content_items = item.get("content", [])
            for content in content_items if isinstance(content_items, list) else []:
                if not isinstance(content, dict):
                    continue
                if content.get("type") == "output_text" and isinstance(content.get("text"), str) and content.get("text"):
                    output_parts.append(content["text"])
        text = "\n".join(output_parts).strip()
        if not text:
            raise ProviderError("The API response contained no text output.")
        usage = body.get("usage", {})
        usage = usage if isinstance(usage, dict) else {}
        return GeneratedResponse(
            text=text,
            provider_name=self.provider_name,
            model_name=str(body.get("model", model)),
            duration_seconds=time.perf_counter() - started,
            request_id=str(body.get("id", "")),
            input_tokens=usage.get("input_tokens") if type(usage.get("input_tokens")) is int else None,
            output_tokens=usage.get("output_tokens") if type(usage.get("output_tokens")) is int else None,
            total_tokens=usage.get("total_tokens") if type(usage.get("total_tokens")) is int else None,
        )
