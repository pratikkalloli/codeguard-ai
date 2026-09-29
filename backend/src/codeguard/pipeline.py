"""Authenticated orchestration for CodeGuard's existing evaluation components."""

from __future__ import annotations

from dataclasses import asdict
import time
from typing import Any, Callable

from codeguard.auth import DEVELOPER, USER, require_role
from codeguard.claim_verification import claim_result_dict, verify_explanation
from codeguard.claims import analyze_explanation
from codeguard.events import log_event
from codeguard.execution import run_function_tests, run_python
from codeguard.input_processing import NO_CODE_MESSAGE, extract_response
from codeguard.ml.inference import apply_ml_advisories
from codeguard.ml.public_reliability import predict_pass_rate
from codeguard.reports import build_reliability_report
from codeguard.storage import (
    DEFAULT_DATABASE_PATH,
    get_evaluation,
    save_claim_results,
    save_evaluation,
    save_evaluation_metrics,
    save_reliability_report,
    save_test_results,
)
from codeguard.validation import validate_python

StageCallback = Callable[[str, str], None]


def _notify(callback: StageCallback | None, stage: str, status: str) -> None:
    if callback:
        callback(stage, status)


def _metric_rows(executions: list[dict[str, Any]], tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, execution in enumerate(executions, start=1):
        rows.extend(
            [
                {"metric_name": f"code_{index}_python_process_wall_time", "metric_value": execution.get("code_execution_seconds"), "unit": "seconds", "measurement_type": execution.get("code_time_measurement_type", "Unavailable")},
                {"metric_name": f"code_{index}_docker_run_wall_time", "metric_value": execution.get("docker_run_seconds"), "unit": "seconds", "measurement_type": "Host-observed docker run lifetime; includes startup, execution, and teardown"},
                {"metric_name": f"code_{index}_container_memory_peak", "metric_value": execution.get("memory_peak_bytes"), "unit": "bytes", "measurement_type": execution.get("memory_measurement_type", "Unavailable")},
            ]
        )
    for index, result in enumerate(tests, start=1):
        rows.append(
            {"metric_name": f"function_test_{index}_python_process_wall_time", "metric_value": result.get("code_execution_seconds"), "unit": "seconds", "measurement_type": result.get("code_time_measurement_type", "Unavailable")}
        )
    return rows


def run_evaluation(
    actor_user_id: int,
    question: str,
    response: str,
    *,
    evaluation_name: str = "",
    model_name: str = "Manual input",
    test_function: str = "",
    test_cases: list[dict[str, Any]] | None = None,
    timeout_seconds: int = 3,
    api_metrics: list[dict[str, Any]] | None = None,
    database_path=DEFAULT_DATABASE_PATH,
    on_stage: StageCallback | None = None,
) -> dict[str, Any]:
    """Run real extract/AST/Docker/test/evidence/ML/report components and persist each result."""
    actor = require_role(actor_user_id, {USER, DEVELOPER}, database_path)
    if not question.strip():
        raise ValueError("Enter the coding question first.")
    if not response.strip():
        raise ValueError("Paste an AI response first.")

    started = time.perf_counter()
    log_event("EVALUATION_STARTED", user_id=actor["id"], component="pipeline", database_path=database_path)
    try:
        _notify(on_stage, "Extracting Python code", "running")
        extracted = extract_response(response)
        session_id = save_evaluation(
            question=question,
            raw_response=response,
            code_blocks=extracted.code_blocks,
            explanation=extracted.explanation,
            model_name=model_name,
            database_path=database_path,
            owner_user_id=actor["id"],
            evaluation_name=evaluation_name,
        )
        evaluation = get_evaluation(session_id, database_path, owner_user_id=actor["id"])
        assert evaluation is not None
        if api_metrics:
            save_evaluation_metrics(evaluation["response_id"], api_metrics, database_path)
        log_event("CODE_EXTRACTION_COMPLETED", user_id=actor["id"], evaluation_id=session_id, component="extraction", status="completed" if extracted.code_blocks else "no_code", details={"code_blocks": len(extracted.code_blocks)}, database_path=database_path)
        _notify(on_stage, "Extracting Python code", "complete" if extracted.code_blocks else "warning")
    except Exception as error:
        log_event("EVALUATION_FAILED", user_id=actor["id"], level="ERROR", component="extraction", error_type=type(error).__name__, database_path=database_path)
        _notify(on_stage, "Extracting Python code", "error")
        raise

    validations: list[dict[str, Any]] = []
    if extracted.code_blocks:
        _notify(on_stage, "Validating Python", "running")
        try:
            for code in extracted.code_blocks:
                validation = validate_python(code)
                validations.append({"status": validation.status, "message": validation.message, "findings": [asdict(item) for item in validation.findings]})
            log_event("STATIC_ANALYSIS_COMPLETED", user_id=actor["id"], evaluation_id=session_id, component="static_analysis", status="completed", details={"code_blocks": len(validations), "risk_findings": sum(len(item["findings"]) for item in validations)}, database_path=database_path)
            _notify(on_stage, "Validating Python", "complete")
        except Exception as error:
            log_event("EVALUATION_FAILED", user_id=actor["id"], evaluation_id=session_id, level="ERROR", component="static_analysis", error_type=type(error).__name__, database_path=database_path)
            validations.append({"status": "error", "message": "Static analysis failed.", "findings": []})
            _notify(on_stage, "Validating Python", "error")
    else:
        _notify(on_stage, "Validating Python", "not_run")

    executions: list[dict[str, Any]] = []
    if extracted.code_blocks:
        _notify(on_stage, "Running code in Docker", "running")
        for index, code in enumerate(extracted.code_blocks, start=1):
            log_event("DOCKER_EXECUTION_STARTED", user_id=actor["id"], evaluation_id=session_id, component="docker", status="started", details={"code_block": index}, database_path=database_path)
            started_docker = time.perf_counter()
            try:
                result = run_python(code, timeout_seconds=timeout_seconds)
                execution = asdict(result)
                executions.append(execution)
                log_event("DOCKER_EXECUTION_COMPLETED", user_id=actor["id"], evaluation_id=session_id, component="docker", duration_ms=(time.perf_counter() - started_docker) * 1000, status=result.status, error_type="" if result.status == "Passed" else result.status, details={"code_block": index}, level="INFO" if result.status == "Passed" else "WARNING", database_path=database_path)
            except Exception as error:
                executions.append({"status": "Execution error", "stderr": type(error).__name__, "stdout": "", "duration_seconds": 0.0})
                log_event("EVALUATION_FAILED", user_id=actor["id"], evaluation_id=session_id, level="ERROR", component="docker", error_type=type(error).__name__, database_path=database_path)
        executed_statuses = {"Passed", "Failed", "Timeout", "Security blocked"}
        _notify(on_stage, "Running code in Docker", "complete" if any(row.get("status") in executed_statuses for row in executions) else "warning")
    else:
        _notify(on_stage, "Running code in Docker", "not_run")

    test_results: list[dict[str, Any]] = []
    if extracted.code_blocks and test_function.strip() and test_cases:
        _notify(on_stage, "Running function tests", "running")
        try:
            test_results = [asdict(item) for item in run_function_tests(
                extracted.code_blocks[0], test_function.strip(), test_cases[:10], timeout_seconds=timeout_seconds
            )]
            save_test_results(evaluation["response_id"], test_results, database_path)
            log_event("FUNCTION_TESTS_COMPLETED", user_id=actor["id"], evaluation_id=session_id, component="function_tests", status="completed", details={"total": len(test_results), "passed": sum(item.get("status") == "passed" for item in test_results)}, database_path=database_path)
            _notify(on_stage, "Running function tests", "complete" if test_results and all(item.get("status") == "passed" for item in test_results) else "warning")
        except Exception as error:
            log_event("EVALUATION_FAILED", user_id=actor["id"], evaluation_id=session_id, level="ERROR", component="function_tests", error_type=type(error).__name__, database_path=database_path)
            _notify(on_stage, "Running function tests", "error")
    else:
        _notify(on_stage, "Running function tests", "not_run")

    _notify(on_stage, "Measuring performance", "running" if executions else "not_run")
    metrics = _metric_rows(executions, test_results)
    if metrics:
        save_evaluation_metrics(evaluation["response_id"], metrics, database_path)
    measured_count = sum(item.get("metric_value") is not None for item in metrics)
    log_event("PERFORMANCE_COMPLETED", user_id=actor["id"], evaluation_id=session_id, component="performance", status="completed" if measured_count else "unavailable", details={"measurements": measured_count}, database_path=database_path)
    _notify(on_stage, "Measuring performance", "complete" if measured_count else ("warning" if executions else "not_run"))

    stage_errors: list[dict[str, str]] = []
    try:
        _notify(on_stage, "Extracting explanation claims", "running")
        claim_candidates = analyze_explanation(extracted.explanation)
        log_event("CLAIMS_EXTRACTED", user_id=actor["id"], evaluation_id=session_id, component="claims", status="completed", details={"claims": len(claim_candidates)}, database_path=database_path)
        _notify(on_stage, "Extracting explanation claims", "complete")
        _notify(on_stage, "Retrieving evidence", "running")
        _notify(on_stage, "Verifying claims", "running")
        claims = [claim_result_dict(item) for item in apply_ml_advisories(verify_explanation(extracted.explanation))]
        # verify_explanation performs the corpus lookup for every factual claim.
        save_claim_results(evaluation["response_id"], claims, database_path)
        log_event("EVIDENCE_RETRIEVED", user_id=actor["id"], evaluation_id=session_id, component="evidence", status="completed", details={"claims_with_source": sum(bool(item.get("source_url")) for item in claims)}, database_path=database_path)
        _notify(on_stage, "Retrieving evidence", "complete")
        log_event("CLAIMS_VERIFIED", user_id=actor["id"], evaluation_id=session_id, component="verification", status="completed", details={"claims": len(claims)}, database_path=database_path)
        _notify(on_stage, "Verifying claims", "complete")
    except Exception as error:
        claims = []
        stage_errors.append({"component": "evidence_verification", "error_type": type(error).__name__})
        log_event("EVALUATION_FAILED", user_id=actor["id"], evaluation_id=session_id, level="ERROR", component="evidence_verification", error_type=type(error).__name__, database_path=database_path)
        _notify(on_stage, "Extracting explanation claims", "error")
        _notify(on_stage, "Retrieving evidence", "error")
        _notify(on_stage, "Verifying claims", "error")

    predictions: list[dict[str, Any]] = []
    if extracted.code_blocks:
        _notify(on_stage, "Running ML advisory analysis", "running")
        for index, code in enumerate(extracted.code_blocks, start=1):
            signal = predict_pass_rate(code, extracted.explanation)
            predictions.append({**signal, "code_block_index": index})
            log_event("ML_INFERENCE_COMPLETED", user_id=actor["id"], evaluation_id=session_id, component="ml", status=signal.get("status", "unknown"), details={"code_block": index, "model": signal.get("model", "")}, database_path=database_path)
        _notify(on_stage, "Running ML advisory analysis", "complete" if any(item.get("status") == "predicted" for item in predictions) else "warning")
    else:
        predictions.append({"status": "not_available", "reason": NO_CODE_MESSAGE, "prediction_range": [0.0, 1.0], "confidence": None})
        _notify(on_stage, "Running ML advisory analysis", "not_run")

    _notify(on_stage, "Building report", "running")
    report = build_reliability_report(
        evaluation,
        test_results,
        metrics,
        claims,
        ml_reliability=predictions[0] if predictions else None,
        docker_execution=executions[0] if executions else None,
    )
    report["ml_block_predictions"] = predictions
    report["extraction"] = {
        "code_blocks_found": len(extracted.code_blocks),
        "explanation": extracted.explanation,
        "no_code_message": NO_CODE_MESSAGE if not extracted.code_blocks else "",
    }
    report["static_analysis"] = validations
    report["docker_executions"] = executions
    report["stage_errors"] = stage_errors
    save_reliability_report(session_id, report, database_path)
    elapsed_ms = (time.perf_counter() - started) * 1000
    log_event("REPORT_CREATED", user_id=actor["id"], evaluation_id=session_id, component="report", duration_ms=elapsed_ms, status="completed", database_path=database_path)
    _notify(on_stage, "Building report", "complete")
    return {
        "evaluation_id": session_id,
        "code_blocks": extracted.code_blocks,
        "explanation": extracted.explanation,
        "validations": validations,
        "executions": executions,
        "test_results": test_results,
        "metrics": metrics,
        "claims": claims,
        "ml_predictions": predictions,
        "report": report,
    }
