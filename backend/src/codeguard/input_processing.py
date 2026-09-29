"""Extract AST-valid Python code while preserving the answer's prose."""

from dataclasses import dataclass
import ast
import re
import textwrap


_FENCED_BLOCK = re.compile(
    r"(?P<fence>`{3,}|~{3,})(?P<language>[^\r\n]*)\r?\n(?P<body>.*?)(?:\r?\n)?(?P=fence)",
    flags=re.DOTALL,
)
_PYTHON_START = re.compile(
    r"^(?:async\s+(?:def|for|with)\b|def\b|class\b|if\b|elif\b|else\s*:|for\b|while\b|try\s*:|"
    r"except\b|finally\s*:|with\b|match\b|case\b|import\b|from\b|return\b|yield\b|"
    r"raise\b|assert\b|del\b|pass\b|break\b|continue\b|global\b|nonlocal\b|@|"
    r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*(?:\[[^]]+\]\s*)?(?:[:=+*/%&|^<>!-]=?|\+=|-=)|"
    r"[([{])"
)
NO_CODE_MESSAGE = (
    "No Python code could be detected in this response. Try placing the Python solution "
    "inside a code block or paste the Python code directly."
)


@dataclass(frozen=True)
class ExtractionResult:
    """AST-valid Python blocks and non-code response text."""

    code_blocks: list[str]
    explanation: str


def _valid_python(source: str) -> bool:
    candidate = textwrap.dedent(source).strip()
    if not candidate:
        return False
    try:
        ast.parse(candidate)
    except (SyntaxError, ValueError, TypeError):
        return False
    return True


def _looks_like_python_start(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "```", "~~~")):
        return False
    if _PYTHON_START.match(stripped):
        return True
    try:
        ast.parse(stripped)
    except (SyntaxError, ValueError, TypeError):
        return False
    # Bare prose words are legal Python names; do not mistake them for code.
    return bool(re.search(r"[()\[\]{}=.+*/%<>!,:'\"]", stripped))


def _extract_unfenced(text: str) -> tuple[list[str], str]:
    """Find code-shaped line groups that parse, retaining every other line."""
    lines = text.splitlines(keepends=True)
    code_blocks: list[str] = []
    explanation: list[str] = []
    index = 0
    while index < len(lines):
        if not _looks_like_python_start(lines[index]):
            explanation.append(lines[index])
            index += 1
            continue

        end = index + 1
        while end < len(lines):
            line = lines[end]
            if not line.strip() or line[:1].isspace() or line.lstrip().startswith("#"):
                end += 1
                continue
            if _looks_like_python_start(line):
                end += 1
                continue
            break

        candidate = "".join(lines[index:end]).strip()
        if _valid_python(candidate):
            code_blocks.append(textwrap.dedent(candidate))
        else:
            explanation.extend(lines[index:end])
        index = end
    return code_blocks, "".join(explanation)


def extract_response(response: str) -> ExtractionResult:
    """Extract Python-labelled or generic fences and AST-valid unfenced code.

    Other language fences and invalid Python candidates are preserved as prose.
    Multiple independently valid code blocks retain their original order.
    """
    if not isinstance(response, str) or not response.strip():
        return ExtractionResult(code_blocks=[], explanation="")

    code_blocks: list[str] = []
    explanation_parts: list[str] = []
    last_end = 0
    for match in _FENCED_BLOCK.finditer(response):
        before = response[last_end : match.start()]
        unfenced_blocks, prose = _extract_unfenced(before)
        code_blocks.extend(unfenced_blocks)
        if prose:
            explanation_parts.append(prose)

        language = match.group("language").strip().lower()
        candidate = match.group("body").strip("\r\n")
        language_name = language.split(maxsplit=1)[0] if language else ""
        if (language_name in {"python", "py", ""}) and _valid_python(candidate):
            code_blocks.append(textwrap.dedent(candidate).strip("\r\n"))
        else:
            explanation_parts.append(match.group(0))
        last_end = match.end()

    trailing_blocks, trailing_prose = _extract_unfenced(response[last_end:])
    code_blocks.extend(trailing_blocks)
    if trailing_prose:
        explanation_parts.append(trailing_prose)

    explanation = "".join(explanation_parts)
    explanation = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", explanation).strip()
    return ExtractionResult(code_blocks=code_blocks, explanation=explanation)
