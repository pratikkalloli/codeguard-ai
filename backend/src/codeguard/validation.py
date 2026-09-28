"""Static-only validation for submitted Python source code."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationFinding:
    rule: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class ValidationResult:
    status: str
    message: str
    findings: list[ValidationFinding]


_RISKY_IMPORT_ROOTS = {"subprocess", "socket", "ctypes", "importlib"}
_RISKY_CALLS = {"eval", "exec", "compile", "__import__", "open"}
_RISKY_QUALIFIED_CALLS = {
    "os.system",
    "os.popen",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "socket.socket",
    "socket.create_connection",
    "shutil.rmtree",
}


def _qualified_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def validate_python(code: str) -> ValidationResult:
    """Check presence, Python syntax, and a small set of risky constructs.

    This is a static heuristic. Passing validation does not establish that code
    is safe, correct, or suitable to execute.
    """
    if not code or not code.strip():
        return ValidationResult("missing", "No Python code was provided.", [])

    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        location = f"line {error.lineno}" if error.lineno else "unknown line"
        detail = error.msg or "invalid syntax"
        return ValidationResult(
            "syntax_error",
            f"Python syntax error at {location}: {detail}.",
            [ValidationFinding("syntax", detail, error.lineno)],
        )

    findings: list[ValidationFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in _RISKY_IMPORT_ROOTS:
                    findings.append(
                        ValidationFinding(
                            "risky_import",
                            f"Import of '{alias.name}' can enable system, network, or dynamic-loading behavior; review it carefully.",
                            node.lineno,
                        )
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root in _RISKY_IMPORT_ROOTS:
                findings.append(
                    ValidationFinding(
                        "risky_import",
                        f"Import from '{node.module}' can enable system, network, or dynamic-loading behavior; review it carefully.",
                        node.lineno,
                    )
                )
        elif isinstance(node, ast.Call):
            name = _qualified_name(node.func)
            if name in _RISKY_CALLS or name in _RISKY_QUALIFIED_CALLS:
                findings.append(
                    ValidationFinding(
                        "risky_call",
                        f"Call to '{name}' can evaluate dynamic code, access files, or interact with the system; review it carefully.",
                        node.lineno,
                    )
                )

    # Keep output predictable when the same syntax is encountered more than once.
    unique_findings = list(dict.fromkeys(findings))
    if unique_findings:
        return ValidationResult(
            "valid_with_risks",
            "Syntax is valid, but static checks found operations that need review. This is not a safety guarantee.",
            unique_findings,
        )
    return ValidationResult(
        "valid",
        "Python syntax is valid. Static checks found no flagged operations; this is not a safety guarantee.",
        [],
    )
