"""Conservative, rule-based extraction and triage of explanation claims."""

from __future__ import annotations

from dataclasses import dataclass
import re


_FACTUAL_PREDICATE = re.compile(
    r"\b(?:is|are|was|were|has|have|returns?|produces?|creates?|uses?|supports?|"
    r"requires?|means?|causes?|contains?|includes?|allows?|preserves?|raises?|"
    r"evaluates?|converts?|stores?|runs?|calls?|implements?|checks?|generates?|"
    r"mutable|immutable|modified|changed|altered|ordered|unordered|stable|unstable)\b",
    flags=re.IGNORECASE,
)
_MUTABILITY_CLAIM = re.compile(
    r"^\s*(?P<subject>[\w`.' -]+?)\s+(?:is|are)\s+"
    r"(?P<negation>not\s+)?(?P<property>mutable|immutable)\b",
    flags=re.IGNORECASE,
)
_NON_ASSERTION_PREFIXES = (
    "here is ",
    "below is ",
    "for example",
    "for instance",
    "use ",
    "try ",
    "you can ",
    "you should ",
    "let's ",
)


@dataclass(frozen=True)
class ClaimResult:
    claim_text: str
    status: str
    reason: str
    evidence_text: str = ""


def _sentences(text: str) -> list[str]:
    pieces: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        cleaned = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line).strip()
        if not cleaned:
            continue
        pieces.extend(
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9`])", cleaned)
            if part.strip()
        )
    return pieces


def _mutability_key(sentence: str) -> tuple[str, bool] | None:
    match = _MUTABILITY_CLAIM.match(sentence)
    if not match:
        return None
    subject = re.sub(r"\s+", " ", match.group("subject").lower()).strip(" .`'")
    subject = re.sub(r"^(?:the|a|an)\s+", "", subject)
    mutable = match.group("property").lower() == "mutable"
    if match.group("negation"):
        mutable = not mutable
    return subject, mutable


def analyze_explanation(explanation: str) -> list[ClaimResult]:
    """Extract sentence-level claims and assign cautious Phase 8 statuses.

    This version has no trusted documentation corpus. It therefore never marks
    external factual claims as Supported. Contradicted means only that two
    supplied sentences use a recognized, directly opposing mutability claim.
    """
    sentences = _sentences(explanation or "")
    claims: list[ClaimResult] = []
    for sentence in sentences:
        lowered = sentence.lower().strip()
        if lowered.startswith(_NON_ASSERTION_PREFIXES) or not _FACTUAL_PREDICATE.search(sentence):
            claims.append(
                ClaimResult(
                    sentence,
                    "Not evaluated",
                    "The Phase 8 heuristic did not recognize a factual assertion pattern in this sentence.",
                )
            )
        else:
            claims.append(
                ClaimResult(
                    sentence,
                    "Insufficient evidence",
                    "This appears to be a factual assertion, but no trusted documentation evidence is connected yet.",
                )
            )

    groups: dict[str, list[tuple[int, bool]]] = {}
    for index, claim in enumerate(claims):
        key = _mutability_key(claim.claim_text)
        if key:
            groups.setdefault(key[0], []).append((index, key[1]))

    for indexed_states in groups.values():
        has_positive = any(state for _, state in indexed_states)
        has_negative = any(not state for _, state in indexed_states)
        if not (has_positive and has_negative):
            continue
        for index, _ in indexed_states:
            current_state = next(
                state for other_index, state in indexed_states if other_index == index
            )
            conflicts = [
                claims[other_index].claim_text
                for other_index, other_state in indexed_states
                if other_index != index and other_state != current_state
            ]
            claims[index] = ClaimResult(
                claims[index].claim_text,
                "Contradicted",
                "This sentence conflicts with another mutability assertion in the supplied explanation: "
                + "; ".join(conflicts)
                + ". This is an internal inconsistency check, not an external fact check.",
            )
    return claims
