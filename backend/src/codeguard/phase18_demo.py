"""Deterministic Phase 18 demonstrations using CodeGuard's existing pipeline."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import tempfile
from typing import Any

from codeguard.claim_verification import claim_result_dict, verify_explanation
from codeguard.claims import analyze_explanation
from codeguard.execution import run_function_tests, run_python
from codeguard.input_processing import extract_response
from codeguard.ml.inference import apply_ml_advisories
from codeguard.ml.public_reliability import predict_pass_rate
from codeguard.reports import build_reliability_report
from codeguard.retrieval import retrieve_evidence
from codeguard.storage import (
    get_claim_results,
    get_evaluation,
    get_evaluation_metrics,
    get_test_results,
    save_claim_results,
    save_evaluation,
    save_evaluation_metrics,
    save_test_results,
)
from codeguard.validation import validate_python


DEMO_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "correct",
        "title": "Correct solution and explanation",
        "question": "Return the sum of the integers in a list. State whether Python lists are mutable.",
        "code": "def solution(values):\n    return sum(values)\n",
        "explanation": "Lists are mutable.",
        "run_expression": "solution([1, 2, 3])",
        "test_case": {"inputs": [[1, 2, 3]], "expected": 6},
        "timeout_seconds": 3,
        "expected": {
            "ast_status": "valid",
            "execution_status": "Passed",
            "test_status": "passed",
            "claim_status": "Supported",
        },
    },
    {
        "case_id": "incorrect_code",
        "title": "Syntactically valid code with an incorrect result",
        "question": "Return the sum of the integers in a list.",
        "code": "def solution(values):\n    return max(values)\n",
        "explanation": "Lists are mutable.",
        "run_expression": "solution([1, 2, 3])",
        "test_case": {"inputs": [[1, 2, 3]], "expected": 6},
        "timeout_seconds": 3,
        "expected": {
            "ast_status": "valid",
            "execution_status": "Passed",
            "test_status": "failed",
            "claim_status": "Supported",
        },
    },
    {
        "case_id": "explanation_error",
        "title": "Correct code with a documentation-conflicting claim",
        "question": "Return the sum of the integers in a list and explain list mutability.",
        "code": "def solution(values):\n    return sum(values)\n",
        "explanation": "Lists are immutable.",
        "run_expression": "solution([1, 2, 3])",
        "test_case": {"inputs": [[1, 2, 3]], "expected": 6},
        "timeout_seconds": 3,
        "expected": {
            "ast_status": "valid",
            "execution_status": "Passed",
            "test_status": "passed",
            "claim_status": "Contradicted",
        },
    },
    {
        "case_id": "performance",
        "title": "Correct but deliberately quadratic solution",
        "question": "Return the sum of a non-empty list of integers.",
        "code": (
            "def solution(values):\n"
            "    total = 0\n"
            "    for value in values:\n"
            "        for _ in values:\n"
            "            total += value\n"
            "    return total // len(values)\n"
        ),
        "explanation": "Lists are mutable.",
        "run_expression": "solution([1] * 3500)",
        "test_case": {"inputs": [[1] * 3500], "expected": 3500},
        "timeout_seconds": 5,
        "expected": {
            "ast_status": "valid",
            "execution_status": "Passed",
            "test_status": "passed",
            "claim_status": "Supported",
        },
    },
    {
        "case_id": "risk",
        "title": "Risky file operation contained by the sandbox",
        "question": "Write a short marker to a temporary file and return the number of characters written.",
        "code": (
            "def solution():\n"
            "    return open('/tmp/codeguard-phase18-marker.txt', 'w', encoding='utf-8').write('contained')\n"
        ),
        "explanation": "Lists are mutable.",
        "run_expression": "solution()",
        "test_case": {"inputs": [], "expected": 9},
        "timeout_seconds": 3,
        "expected": {
            "ast_status": "valid_with_risks",
            "execution_status": "Passed",
            "test_status": "passed",
            "claim_status": "Supported",
        },
    },
)


def _metric_rows(execution: Any, test_results: list[Any]) -> list[dict[str, Any]]:
    """Persist measurements returned by the existing execution components."""
    measurements = (
        ("python_process_wall_time", execution.code_execution_seconds, "seconds", execution.code_time_measurement_type),
        ("docker_engine_check_time", execution.engine_check_seconds, "seconds", "Host-observed Docker engine check"),
        ("image_readiness_check_time", execution.image_readiness_seconds, "seconds", "Host-observed local image inspection"),
        ("container_startup_time", execution.container_startup_seconds, "seconds", execution.container_startup_measurement_type),
        ("docker_run_wall_time", execution.docker_run_seconds, "seconds", "Host-observed docker run lifetime"),
        ("docker_overhead_estimate", execution.docker_overhead_estimate_seconds, "seconds", execution.docker_overhead_measurement_type),
        ("container_memory_peak", execution.memory_peak_bytes, "bytes", execution.memory_measurement_type),
    )
    rows = [
        {"metric_name": name, "metric_value": value, "unit": unit, "measurement_type": kind}
        for name, value, unit, kind in measurements
    ]
    for index, result in enumerate(test_results, start=1):
        rows.extend(
            [
                {
                    "metric_name": f"function_test_{index}_python_process_wall_time",
                    "metric_value": result.code_execution_seconds,
                    "unit": "seconds",
                    "measurement_type": result.code_time_measurement_type,
                },
                {
                    "metric_name": f"function_test_{index}_container_memory_peak",
                    "metric_value": result.memory_peak_bytes,
                    "unit": "bytes",
                    "measurement_type": result.memory_measurement_type,
                },
            ]
        )
    return rows


def _response(case: dict[str, Any]) -> str:
    return f"{case['explanation']}\n\n```python\n{case['code'].rstrip()}\n```"


def run_phase18_demonstrations(output_dir: str | Path | None = None) -> dict[str, Any]:
    """Run all cases through extraction, storage, analysis, Docker, and reporting.

    The working SQLite database is temporary. Results are exported as JSON to
    ``output_dir`` when supplied, so the app's normal history is left untouched.
    """
    output_path = Path(output_dir) if output_dir is not None else None
    if output_path is not None:
        output_path.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="codeguard-phase18-") as temporary:
        database_path = Path(temporary) / "phase18.sqlite3"
        records = [
            _run_case(case, database_path)
            for case in DEMO_CASES
        ]

    summary = {
        "phase": "18",
        "title": "End-to-end demonstration validation",
        "case_count": len(records),
        "all_expected_signals_observed": all(item["expectations_met"] for item in records),
        "limitations": [
            "The Phase 17 pass-rate estimate is reported separately from correctness tests and evidence-backed claim verification.",
            "Execution timings include Python startup/sandbox overhead and are observations, not a benchmark score or cross-machine performance guarantee.",
            "Static risk findings are warnings. The risk example writes only to container /tmp, which is ephemeral and not host-mounted.",
            "The Phase 17 prediction estimates source-recorded competitive-programming pass rate; it is not a CodeGuard correctness verdict.",
        ],
        "cases": records,
    }
    if output_path is not None:
        for record in records:
            (output_path / f"{record['case_id']}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        (output_path / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return summary


def _run_case(case: dict[str, Any], database_path: Path) -> dict[str, Any]:
    raw_response = _response(case)
    extracted = extract_response(raw_response)
    if len(extracted.code_blocks) != 1:
        raise AssertionError(f"{case['case_id']}: expected one extracted Python block")

    session_id = save_evaluation(
        case["question"], raw_response, extracted.code_blocks, extracted.explanation,
        model_name="Phase 18 deterministic demonstration", database_path=database_path,
    )
    evaluation = get_evaluation(session_id, database_path=database_path)
    if evaluation is None:
        raise AssertionError(f"{case['case_id']}: evaluation did not persist")

    code = extracted.code_blocks[0]
    ast_result = validate_python(code)
    execution_source = f"{code.rstrip()}\n\nprint({case['run_expression']})\n"
    execution_result = run_python(execution_source, timeout_seconds=case["timeout_seconds"])
    function_results = run_function_tests(
        code, "solution", [case["test_case"]], timeout_seconds=case["timeout_seconds"]
    )

    extracted_claims = analyze_explanation(extracted.explanation)
    evidence_results = [
        {"claim_text": claim.claim_text, "chunks": retrieve_evidence(claim.claim_text, top_k=3)}
        for claim in extracted_claims
        if claim.status != "Not evaluated"
    ]
    verified_claims = apply_ml_advisories(verify_explanation(extracted.explanation))
    serialized_claims = [claim_result_dict(claim) for claim in verified_claims]
    save_claim_results(evaluation["response_id"], serialized_claims, database_path=database_path)

    serialized_tests = [asdict(result) for result in function_results]
    save_test_results(evaluation["response_id"], serialized_tests, database_path=database_path)
    metrics = _metric_rows(execution_result, function_results)
    save_evaluation_metrics(evaluation["response_id"], metrics, database_path=database_path)

    persisted_evaluation = get_evaluation(session_id, database_path=database_path)
    persisted_tests = get_test_results(evaluation["response_id"], database_path=database_path)
    persisted_metrics = get_evaluation_metrics(evaluation["response_id"], database_path=database_path)
    persisted_claims = get_claim_results(evaluation["response_id"], database_path=database_path)
    ml_prediction = predict_pass_rate(
        code,
        explanation=extracted.explanation,
        metadata={"source": "phase18_demo", "dataset": "local deterministic cases", "difficulty": "unknown"},
    )
    report = build_reliability_report(
        persisted_evaluation,
        persisted_tests,
        persisted_metrics,
        persisted_claims,
        ml_reliability=ml_prediction,
        docker_execution=asdict(execution_result),
    )

    claim_statuses = [claim.status for claim in verified_claims]
    test_status = function_results[0].status if function_results else "missing"
    observed = {
        "ast_status": ast_result.status,
        "execution_status": execution_result.status,
        "test_status": test_status,
        "claim_status": claim_statuses[0] if claim_statuses else "missing",
    }
    expected = case["expected"]
    return {
        "case_id": case["case_id"],
        "title": case["title"],
        "input": {
            "question": case["question"],
            "raw_response": raw_response,
            "extracted_python": code,
            "extracted_explanation": extracted.explanation,
        },
        "expected_behavior": expected,
        "observed_behavior": observed,
        "expectations_met": observed == expected and execution_result.status == "Passed" and ml_prediction.get("status") == "predicted",
        "ast_result": asdict(ast_result),
        "docker_execution_result": asdict(execution_result),
        "test_results": serialized_tests,
        "performance_result": {
            "measurements": metrics,
            "interpretation": "Measured by the existing Docker supervisor and runner; includes interpreter and container overhead.",
        },
        "extracted_claims": [asdict(claim) for claim in extracted_claims],
        "evidence_results": evidence_results,
        "claim_verification_results": serialized_claims,
        "ml_reliability_prediction": ml_prediction,
        "final_output": report,
    }
