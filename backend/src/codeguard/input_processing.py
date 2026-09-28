"""Extract Python code fences and remaining prose from an AI response."""

from dataclasses import dataclass
import re


_FENCED_BLOCK = re.compile(
    r"(?P<fence>```|~~~)(?P<language>[^\r\n]*)\r?\n(?P<body>.*?)(?:\r?\n)?(?P=fence)",
    flags=re.DOTALL,
)


@dataclass(frozen=True)
class ExtractionResult:
    """Python code blocks and non-Python-fence text from a response."""

    code_blocks: list[str]
    explanation: str


def extract_response(response: str) -> ExtractionResult:
    """Extract fenced Python blocks and keep the rest as explanation text.

    Only fenced blocks labeled ``python`` or ``py`` are extracted. Other fenced
    blocks remain in the explanation so this operation does not discard content.
    """
    code_blocks: list[str] = []
    explanation_parts: list[str] = []
    last_end = 0

    for match in _FENCED_BLOCK.finditer(response):
        explanation_parts.append(response[last_end : match.start()])
        language = match.group("language").strip().lower()
        if language in {"python", "py"}:
            code_blocks.append(match.group("body").strip("\r\n"))
        else:
            explanation_parts.append(match.group(0))
        last_end = match.end()

    explanation_parts.append(response[last_end:])
    explanation = "".join(explanation_parts)
    explanation = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", explanation).strip()
    return ExtractionResult(code_blocks=code_blocks, explanation=explanation)
