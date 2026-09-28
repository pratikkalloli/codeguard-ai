"""Advisory ML predictions that never override deterministic evidence results."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from codeguard.claim_verification import VerifiedClaim
from codeguard.ml.models import DEFAULT_MODEL_PATH, load_model, predict_with_confidence


def apply_ml_advisories(claims: list[VerifiedClaim], model_path: str | Path = DEFAULT_MODEL_PATH) -> list[VerifiedClaim]:
    """Attach predictions only to insufficient-evidence claims; preserve rule status."""
    try:
        artifact = load_model(model_path)
    except FileNotFoundError:
        return [replace(claim, rule_result=claim.status, verification_method="rule") for claim in claims]
    except Exception:
        # An unreadable optional model must not disable the deterministic verifier.
        return [replace(claim, rule_result=claim.status, verification_method="rule") for claim in claims]

    output: list[VerifiedClaim] = []
    for claim in claims:
        if claim.status != "Insufficient evidence":
            output.append(replace(claim, rule_result=claim.status, verification_method="rule"))
            continue
        record: dict[str, Any] = {
            "claim": claim.claim_text,
            "evidence": claim.evidence_text,
            "tfidf_similarity": claim.retrieval_score,
        }
        try:
            prediction = predict_with_confidence(artifact, [record])[0]
        except Exception:
            output.append(replace(claim, rule_result=claim.status, verification_method="rule"))
            continue
        confidence = prediction["confidence"]
        threshold = artifact.get("confidence_threshold")
        review = confidence is None or threshold is None or confidence < threshold
        if confidence is None:
            confidence_text = "confidence unavailable"
            threshold_text = "confidence acceptance threshold unavailable"
        else:
            confidence_text = f"uncalibrated class probability {confidence:.3f}"
            threshold_text = f"validation-derived threshold {threshold:.3f}"
        if review:
            note = f" LOW CONFIDENCE / REVIEW REQUIRED ({confidence_text}; {threshold_text})."
        else:
            note = f" This is an ML advisory only ({confidence_text}; {threshold_text}); it is not evidence or proof of truth."
        output.append(replace(
            claim,
            reason=claim.reason + f" ML advisory prediction: {prediction['prediction']}." + note,
            rule_result=claim.status,
            ml_result=prediction["prediction"],
            ml_confidence=confidence,
            verification_method="hybrid",
            ml_review_required=review,
        ))
    return output

