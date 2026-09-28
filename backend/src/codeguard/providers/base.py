"""Provider-neutral model response types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeneratedResponse:
    text: str
    provider_name: str
    model_name: str
    duration_seconds: float
    request_id: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ProviderError(RuntimeError):
    """A safe, user-displayable provider failure without credential data."""


class ModelProvider(Protocol):
    provider_name: str

    def generate(self, question: str) -> GeneratedResponse:
        """Generate a response for a coding question."""
