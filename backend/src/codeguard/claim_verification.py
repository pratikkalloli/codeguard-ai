"""Transparent evidence-backed verification for a conservative set of claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import time
from typing import Any

from codeguard.claims import analyze_explanation
from codeguard.retrieval import retrieve_evidence


@dataclass(frozen=True)
class VerifiedClaim:
    claim_text: str
    status: str
    reason: str
    evidence_text: str = ""
    source: str = ""
    title: str = ""
    source_url: str = ""
    retrieval_score: float | None = None
    evidence_chunk_id: str = ""
    retrieval_seconds: float | None = None
    rule_result: str = ""
    ml_result: str | None = None
    ml_confidence: float | None = None
    verification_method: str = "rule"
    ml_review_required: bool = False


def _claim_polarity(claim: str) -> tuple[str, bool] | None:
    text = claim.lower()
    negative = bool(
        re.search(r"\b(?:not|never|cannot|can't|unable to|immutable|unordered|unstable)\b", text)
    )
    positive = bool(
        re.search(r"\b(?:mutable|modified|changed|altered|preserve(?:s)?|preserved|ordered|stable)\b", text)
    )
    if re.search(r"\b(?:lists?|list objects?)\b", text) and re.search(
        r"\b(?:mutable|immutable|modified|changed|altered)\b", text
    ):
        return "list_mutability", not negative
    if re.search(r"\btuples?\b", text) and re.search(
        r"\b(?:mutable|immutable|modified|changed|altered)\b", text
    ):
        return "tuple_mutability", not negative
    if re.search(r"\b(?:dictionaries|dictionary|dicts?|mappings?)\b", text) and re.search(
        r"\b(?:insertion order|ordered|order)\b", text
    ):
        return "dict_insertion_order", positive and not negative
    if re.search(r"\bsets?\b", text) and re.search(r"\b(?:insertion order|ordered|unordered|order)\b", text):
        return "set_insertion_order", positive and not negative
    if re.search(r"\bsorted\b", text) and re.search(r"\b(?:stable|unstable)\b", text):
        return "sorted_stability", positive and not negative
    return None


def verify_claim(claim: str, *, index: dict[str, Any] | None = None) -> VerifiedClaim:
    """Retrieve evidence and compare only explicit, curated proposition keys."""
    started = time.perf_counter()
    if not claim or not claim.strip():
        return VerifiedClaim(
            claim or "", "Not evaluated", "The claim is empty and cannot be evaluated.",
            retrieval_seconds=0.0,
        )
    proposition = _claim_polarity(claim)
    evidence = retrieve_evidence(claim, index=index)
    best = evidence[0] if evidence else None
    elapsed = best["retrieval_seconds"] if best else time.perf_counter() - started
    if proposition is None:
        reason = (
            "Documentation was retrieved, but this MVP has no explicit proposition rule for the claim."
            if best
            else "No relevant documentation was retrieved, and this MVP has no explicit proposition rule for the claim."
        )
        return VerifiedClaim(
            claim,
            "Insufficient evidence",
            reason,
            evidence_text=best["text"] if best else "",
            source=best["source"] if best else "",
            title=best["title"] if best else "",
            source_url=best["url"] if best else "",
            retrieval_score=best["retrieval_score"] if best else None,
            evidence_chunk_id=best["chunk_id"] if best else "",
            retrieval_seconds=elapsed,
        )
    fact_key, claimed_polarity = proposition
    comparable = next(
        (
            chunk for chunk in evidence
            if chunk.get("fact_key") == fact_key and isinstance(chunk.get("polarity"), bool)
        ),
        None,
    )
    if comparable is None:
        return VerifiedClaim(
            claim,
            "Insufficient evidence",
            "The current trusted corpus did not retrieve a documentation chunk that directly addresses this proposition.",
            evidence_text=best["text"] if best else "",
            source=best["source"] if best else "",
            title=best["title"] if best else "",
            source_url=best["url"] if best else "",
            retrieval_score=best["retrieval_score"] if best else None,
            evidence_chunk_id=best["chunk_id"] if best else "",
            retrieval_seconds=elapsed,
        )
    evidence_polarity = comparable["polarity"]
    status = "Supported" if claimed_polarity == evidence_polarity else "Contradicted"
    reason = (
        "The retrieved documentation directly agrees with the recognized claim rule."
        if status == "Supported"
        else "The retrieved documentation directly conflicts with the recognized claim rule."
    )
    return VerifiedClaim(
        claim_text=claim,
        status=status,
        reason=reason,
        evidence_text=comparable["text"],
        source=comparable["source"],
        title=comparable["title"],
        source_url=comparable["url"],
        retrieval_score=comparable["retrieval_score"],
        evidence_chunk_id=comparable["chunk_id"],
        retrieval_seconds=elapsed,
    )


def verify_explanation(explanation: str) -> list[VerifiedClaim]:
    """Analyze explanation sentences, retaining heuristic non-claims as Not evaluated."""
    results = []
    for claim in analyze_explanation(explanation):
        if claim.status == "Not evaluated":
            results.append(
                VerifiedClaim(
                    claim.claim_text,
                    "Not evaluated",
                    "The sentence is not recognized as a factual assertion by the claim extractor.",
                    retrieval_seconds=0.0,
                )
            )
        else:
            results.append(verify_claim(claim.claim_text))
    return results


def claim_result_dict(claim: VerifiedClaim) -> dict[str, Any]:
    """Serialize the full verification and provenance record for SQLite."""
    result = asdict(claim)
    result["rule_result"] = result["rule_result"] or claim.status
    return result
