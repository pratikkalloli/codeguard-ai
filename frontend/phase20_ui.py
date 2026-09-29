"""Separate authenticated User and Developer experiences for CodeGuard AI."""

from __future__ import annotations

import ast
import csv
from datetime import date
import json
import os
from pathlib import Path
import sys
import sqlite3
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SOURCE = PROJECT_ROOT / "backend" / "src"
if str(BACKEND_SOURCE) not in sys.path:
    sys.path.insert(0, str(BACKEND_SOURCE))

import streamlit as st

from codeguard.access import get_accessible_evaluation, get_accessible_report, list_accessible_evaluations
from codeguard.auth import (
    DEVELOPER,
    USER,
    AuthenticationError,
    AuthorizationError,
    authenticate_user,
    get_user,
    list_users,
    register_user,
    require_role,
    update_profile,
)
from codeguard.comparison import group_evaluations_by_question
from codeguard.events import MAX_LOG_ROWS, list_events, log_event
from codeguard.health import (
    collect_health,
    developer_statistics,
    docker_configuration,
    docker_status,
    run_docker_runtime_probe,
)
from codeguard.input_processing import NO_CODE_MESSAGE
from codeguard.ml.phase16 import PHASE16_DIR, build_phase16_workspace
from codeguard.ml.review import (
    DECISIONS as REVIEW_DECISIONS,
    get_review_record,
    initialize_review_db,
    list_review_records,
    review_counts,
    save_adjudication,
    save_independent_review,
)
from codeguard.ml.public_reliability import predict_pass_rate
from codeguard.pipeline import run_evaluation
from codeguard.providers import OpenAIResponsesProvider, ProviderError
from codeguard.retrieval import retrieve_evidence
from codeguard.storage import (
    DEFAULT_DATABASE_PATH,
    get_claim_results,
    get_evaluation_metrics,
    get_test_results,
)

USER_NAVIGATION = ("HOME", "NEW EVALUATION", "MY EVALUATIONS", "COMPARE", "PROFILE")
DEVELOPER_NAVIGATION = (
    "OVERVIEW", "EVALUATIONS", "LOGS", "SYSTEM HEALTH", "DOCKER", "ML",
    "EVIDENCE", "DATASETS", "USERS", "SETTINGS",
)


def _theme() -> None:
    st.markdown(
        """<style>
        :root {color-scheme:dark;--cg-bg:#0b1018;--cg-surface:#111a26;--cg-surface2:#172231;
          --cg-border:#263448;--cg-text:#e8eef8;--cg-muted:#9aa9bc;--cg-accent:#92adff;}
        .stApp {background:radial-gradient(ellipse at 80% -10%,#1c2a47 0,transparent 43%),var(--cg-bg);color:var(--cg-text)}
        [data-testid="stHeader"] {background:transparent}
        [data-testid="stSidebar"] {background:var(--cg-surface);border-right:1px solid var(--cg-border)}
        .block-container {max-width:1420px;padding-top:1.4rem;padding-bottom:3rem}
        h1,h2,h3 {letter-spacing:-.035em}
        [data-testid="stMetric"] {background:var(--cg-surface);border:1px solid var(--cg-border);border-radius:14px;padding:16px;}
        [data-testid="stExpander"] {border-color:var(--cg-border);border-radius:12px;background:var(--cg-surface)}
        [data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input,
        [data-testid="stSelectbox"] [data-baseweb="select"]>div {background:var(--cg-surface2);border-color:var(--cg-border);border-radius:9px}
        .stButton button,[data-testid="stFormSubmitButton"] button {border-radius:9px;min-height:2.55rem;font-weight:650}
        .cg-hero {padding:28px;border:1px solid var(--cg-border);border-radius:18px;
          background:linear-gradient(120deg,#111a26,#182844);margin:8px 0 18px}
        .cg-kicker {font-size:.74rem;letter-spacing:.14em;text-transform:uppercase;color:#a4baff;font-weight:700}
        .cg-hero-title {font-size:2.1rem;font-weight:760;letter-spacing:-.045em;margin:.55rem 0}
        .cg-muted {color:#a8b5c7}
        .cg-banner {padding:13px 16px;border:1px solid var(--cg-border);border-radius:12px;background:var(--cg-surface);margin:8px 0 18px}
        [data-testid="stCode"] {border:1px solid var(--cg-border);border-radius:11px}
        @media(max-width:740px){.block-container{padding:1rem .8rem 2rem}.cg-hero-title{font-size:1.7rem}}
        @media(prefers-reduced-motion:reduce){*,*::before,*::after{transition:none!important;scroll-behavior:auto!important}}
        </style>""",
        unsafe_allow_html=True,
    )


def _clear_session() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _render_landing(database_path) -> None:
    st.markdown(
        '<div class="cg-hero"><div class="cg-kicker">CodeGuard AI · Reliability workspace</div>'
        '<div class="cg-hero-title">Evaluate the reliability of AI-generated code and explanations.</div>'
        '<div class="cg-muted">Inspect code, execution, tests, performance, selected risks, explanations, evidence, and ML advisory signals. '
        'Each signal stays separate; no check guarantees correctness or security.</div></div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.subheader("A clearer review of generated Python")
        st.write("Submit an AI answer, inspect the individual checks, and keep a private history of your evaluations.")
        st.markdown("**Code · execution · tests · performance · risks · explanations · evidence · ML advisory**")
        st.caption("CodeGuard currently evaluates Python. Docker restrictions reduce local execution risk but are not a production security boundary.")
        mode = st.radio("Continue", ("LOGIN", "GET STARTED", "DEVELOPER ACCESS"), horizontal=True, key="cg_entry_mode")
    with right:
        if mode == "GET STARTED":
            st.subheader("Create a user account")
            with st.form("cg_register_form"):
                username = st.text_input("Username or email")
                password = st.text_input("Password · at least 12 characters", type="password")
                confirmation = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submitted:
                if password != confirmation:
                    st.error("The passwords do not match.")
                else:
                    try:
                        user = register_user(username, password, database_path)
                        st.session_state["cg_user_id"] = user["id"]
                        st.rerun()
                    except AuthenticationError as error:
                        st.error(str(error))
        else:
            developer_mode = mode == "DEVELOPER ACCESS"
            st.subheader("Developer access" if developer_mode else "Welcome back")
            with st.form("cg_login_form"):
                username = st.text_input("Username or email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if submitted:
                try:
                    user = authenticate_user(username, password, database_path)
                    if developer_mode and user["role"] != DEVELOPER:
                        st.error("This account does not have developer access.")
                    else:
                        st.session_state["cg_user_id"] = user["id"]
                        st.rerun()
                except AuthenticationError as error:
                    st.error(str(error))
            if developer_mode:
                st.info("First developer setup is performed once from a local terminal with `python -m codeguard.auth_bootstrap <username>`. The password is entered in a hidden prompt and is never stored in plaintext.")


def _actor(database_path) -> dict[str, Any] | None:
    user_id = st.session_state.get("cg_user_id")
    if not user_id:
        return None
    try:
        user = get_user(int(user_id), database_path)
    except (ValueError, TypeError, sqlite3.Error):
        user = None
    if user is None:
        _clear_session()
    return user


def _status_message(status: str) -> None:
    if status in {"valid", "Passed", "passed", "Supported", "READY", "ONLINE"}:
        st.success(status.replace("_", " ").upper())
    elif status in {"valid_with_risks", "WARNING", "UNAVAILABLE", "Insufficient evidence", "Not evaluated"}:
        st.warning(status.replace("_", " ").upper())
    else:
        st.error(status.replace("_", " ").upper())


def _render_code(code: str, findings: list[dict[str, Any]] | None = None) -> None:
    with st.expander("Python source", expanded=True):
        st.code(code, language="python", line_numbers=True)
        try:
            tree = ast.parse(code)
            functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            col_a, col_b = st.columns(2)
            col_a.caption("Functions: " + (", ".join(functions) if functions else "none detected"))
            col_b.caption("Classes: " + (", ".join(classes) if classes else "none detected"))
        except SyntaxError:
            st.caption("The extracted source did not parse as Python.")
        for finding in findings or []:
            line = f" · line {finding.get('line')}" if finding.get("line") else ""
            st.warning(f"{finding.get('rule', 'Finding')}{line}: {finding.get('message', '')}")


def _render_report(actor_id: int, evaluation_id: int, database_path) -> None:
    evaluation = get_accessible_evaluation(actor_id, evaluation_id, database_path=database_path)
    if evaluation is None:
        st.error("This evaluation is unavailable or you do not have access to it.")
        return
    report = get_accessible_report(actor_id, evaluation_id, database_path=database_path)
    st.markdown(f"### Evaluation EVL-{evaluation_id:07d}")
    st.caption(f"{evaluation['created_at']} UTC · {evaluation['model_name']} · {evaluation.get('evaluation_name') or 'Untitled evaluation'}")
    st.markdown("**Coding question**")
    st.write(evaluation["question_text"])
    if evaluation["code_blocks"]:
        for block in evaluation["code_blocks"]:
            index = int(block["block_index"])
            static_rows = (report or {}).get("static_analysis", [])
            findings = static_rows[index - 1].get("findings", []) if len(static_rows) >= index else []
            _render_code(block["code_text"], findings)
            if len(static_rows) >= index:
                _status_message(static_rows[index - 1].get("status", "unknown"))
                st.write(static_rows[index - 1].get("message", ""))
    else:
        st.info(NO_CODE_MESSAGE)
    if not report:
        st.info("No saved detailed report is available for this evaluation yet.")
        return

    tabs = st.tabs(("Execution and tests", "Performance and risks", "Explanation and evidence", "ML advisory and report"))
    with tabs[0]:
        execution_rows = report.get("docker_executions", [])
        if execution_rows:
            for index, execution in enumerate(execution_rows, start=1):
                st.markdown(f"**Code block {index} · Docker execution**")
                _status_message(execution.get("status", "unknown"))
                if execution.get("stdout"):
                    st.code(execution["stdout"], language="text")
                if execution.get("stderr"):
                    st.warning(execution["stderr"])
        else:
            st.info("Execution was not run because no Python block was extracted.")
        results = report.get("test_results", [])
        if results:
            passed = sum(item.get("status") == "passed" for item in results)
            st.metric("Function tests passed", f"{passed} / {len(results)}")
            st.dataframe(results, width="stretch", hide_index=True)
        else:
            st.info("No function tests were supplied for this evaluation.")
    with tabs[1]:
        metrics = report.get("performance_measurements", report.get("performance_metrics", report.get("metrics", [])))
        if metrics:
            st.dataframe(metrics, width="stretch", hide_index=True)
        else:
            st.info("Performance measurements are unavailable.")
        if evaluation["code_blocks"]:
            findings = [finding for item in report.get("static_analysis", []) for finding in item.get("findings", [])]
            if findings:
                for finding in findings:
                    st.warning(f"{finding.get('rule')}: {finding.get('message')}")
            else:
                st.info("No selected static risk patterns were found. Static analysis does not prove safety.")
    with tabs[2]:
        claims = report.get("claims", report.get("claim_verification", {}).get("results", []))
        if not claims:
            claims = get_claim_results(evaluation["response_id"], database_path)
        if claims:
            for index, claim in enumerate(claims, start=1):
                with st.expander(f"Claim {index} · {claim.get('status', 'Not evaluated')}", expanded=index == 1):
                    st.write(claim.get("claim_text", ""))
                    _status_message(claim.get("status", "Not evaluated"))
                    st.caption(claim.get("reason", ""))
                    if claim.get("evidence_text"):
                        st.markdown("**Retrieved evidence**")
                        st.text(claim["evidence_text"])
                    if claim.get("source_url"):
                        st.markdown(f"[Open source documentation]({claim['source_url']})")
        else:
            st.info("No explanation claims were identified.")
        st.markdown("**Explanation text**")
        st.text(evaluation.get("explanation_text") or "No explanation text was found.")
    with tabs[3]:
        signals = report.get("signals", {})
        ml = signals.get("ml_reliability", report.get("ml_reliability", {}))
        st.markdown("**ML ADVISORY**")
        if ml.get("available") and ml.get("prediction") is not None:
            st.metric("Estimated upstream pass_rate", f"{ml.get('prediction', 0):.1%}")
            st.caption(f"Model: {ml.get('model', 'unknown')} · target: {ml.get('target', 'pass_rate')}")
        else:
            st.info("ML model unavailable" if not ml.get("reason") else ml["reason"])
        st.caption("This Phase 17 model estimates the upstream dataset's execution pass_rate. It is not a general code correctness or security classifier.")
        st.download_button(
            "Download reliability report (JSON)",
            data=json.dumps(report, ensure_ascii=False, indent=2),
            file_name=f"codeguard-evaluation-{evaluation_id}.json",
            mime="application/json",
            key=f"cg_download_report_{evaluation_id}",
        )
        with st.expander("Report fields", expanded=False):
            st.json(report, expanded=False)


def _evaluate_page(actor: dict[str, Any], database_path) -> None:
    st.title("New evaluation")
    st.caption("Analyze an AI answer through CodeGuard's existing Python, Docker, evidence, and advisory components.")
    response_source = st.radio("Response source", ("Manual paste", "OpenAI API"), horizontal=True, key="cg_response_source")
    with st.form("cg_evaluation_form", clear_on_submit=False):
        question = st.text_area("Coding question", height=110, placeholder="Describe the task this answer should solve.")
        col_name, col_source = st.columns(2)
        name = col_name.text_input("Evaluation name (optional)")
        if response_source == "Manual paste":
            response = st.text_area("AI response", height=240, placeholder="Paste an answer with ```python fences or paste Python directly.")
            source = col_source.text_input("Model / source (optional)", value="Manual input")
            api_model = ""
        else:
            response = ""
            api_model = col_source.text_input("OpenAI model", value=os.environ.get("CODEGUARD_OPENAI_MODEL", "gpt-6-astra"))
            st.caption("Optional API usage may be billed. The key is read from OPENAI_API_KEY in the process environment and is never entered here.")
        with st.expander("Optional function tests", expanded=False):
            function_name = st.text_input("Function to test", placeholder="solution")
            test_cases_json = st.text_area("Test cases as JSON list", value="[]", help='Example: [{"inputs": [[1,2]], "expected": 3}]')
        timeout = st.slider("Docker timeout (seconds)", min_value=1, max_value=10, value=3)
        submit = st.form_submit_button("Analyze answer", type="primary", use_container_width=True)
    if submit:
        if not question.strip():
            st.error("Enter the coding question first.")
            return
        generated_response = None
        api_metrics: list[dict[str, Any]] = []
        if response_source == "OpenAI API":
            try:
                with st.spinner("Requesting an answer from the configured OpenAI Responses API…"):
                    generated_response = OpenAIResponsesProvider(model_name=api_model.strip() or None).generate(question)
                response = generated_response.text
                source = f"{generated_response.provider_name} / {generated_response.model_name}"
                api_metrics.append({
                    "metric_name": "model_api_wall_time",
                    "metric_value": generated_response.duration_seconds,
                    "unit": "seconds",
                    "measurement_type": "Host-observed remote API request wall time; includes network and provider processing",
                })
                for token_name in ("input_tokens", "output_tokens", "total_tokens"):
                    token_value = getattr(generated_response, token_name)
                    if token_value is not None:
                        api_metrics.append({"metric_name": f"model_api_{token_name}", "metric_value": token_value, "unit": "tokens", "measurement_type": "Token count reported by the API response"})
            except ProviderError as error:
                st.error(str(error))
                return
        try:
            test_cases = json.loads(test_cases_json or "[]")
            if not isinstance(test_cases, list) or len(test_cases) > 10:
                raise ValueError("Provide a JSON list containing at most 10 test cases.")
            if test_cases and (not function_name.strip() or any(not isinstance(item, dict) for item in test_cases)):
                raise ValueError("Provide a function name and object entries for the test cases.")
        except (json.JSONDecodeError, ValueError) as error:
            st.error(str(error))
            return

        progress_rows: list[tuple[str, str]] = []
        result = None
        with st.status("Starting CodeGuard analysis", expanded=True) as status:
            def update_stage(label: str, state: str) -> None:
                progress_rows.append((label, state))
                status.write(f"{label}: {state.replace('_', ' ')}")
                if state == "running":
                    status.update(label=f"In progress · {label}", state="running")

            try:
                result = run_evaluation(
                    actor["id"], question, response, evaluation_name=name,
                    model_name=source.strip() or "Manual input", test_function=function_name,
                    test_cases=test_cases, timeout_seconds=timeout,
                    api_metrics=api_metrics,
                    database_path=database_path, on_stage=update_stage,
                )
                status.update(label=f"Evaluation EVL-{result['evaluation_id']:07d} saved", state="complete")
            except (ValueError, AuthorizationError) as error:
                status.update(label="Evaluation needs attention", state="error")
                st.error(str(error))
            except Exception as error:
                log_event("EVALUATION_FAILED", user_id=actor["id"], level="ERROR", component="ui", error_type=type(error).__name__, database_path=database_path)
                status.update(label="Evaluation could not be completed", state="error")
                st.error("The evaluation could not be completed. A developer can inspect the sanitized error type in the event log." if actor["role"] == USER else f"Evaluation failed: {type(error).__name__}")
        if result:
            st.session_state["cg_last_evaluation_id"] = result["evaluation_id"]
            st.success(f"Evaluation EVL-{result['evaluation_id']:07d} saved to your account.")
            _render_report(actor["id"], result["evaluation_id"], database_path)


def _render_home(actor: dict[str, Any], database_path) -> None:
    st.markdown('<div class="cg-hero"><div class="cg-kicker">Your CodeGuard workspace</div><div class="cg-hero-title">Review AI-generated Python with evidence you can inspect.</div><div class="cg-muted">Run focused checks, review their separate results, and return to your saved evaluations at any time.</div></div>', unsafe_allow_html=True)
    rows = list_accessible_evaluations(actor["id"], limit=500, database_path=database_path)
    metrics = st.columns(3)
    metrics[0].metric("My evaluations", len(rows))
    metrics[1].metric("With Python code", sum(row["code_block_count"] > 0 for row in rows))
    metrics[2].metric("With function tests", sum(row["tests_total"] > 0 for row in rows))
    st.caption("Counts come from your saved SQLite records. Each check remains a separate signal.")
    if rows:
        from collections import Counter

        activity = Counter(row["created_at"][:10] for row in rows if row.get("created_at"))
        st.line_chart({"Your evaluations": dict(sorted(activity.items()))}, height=190)
    st.subheader("Recent evaluations")
    if rows:
        st.dataframe(
            [{"ID": f"EVL-{row['id']:07d}", "Date (UTC)": row["created_at"], "Name": row["evaluation_name"] or "Untitled", "Question": row["question_text"], "Source": row["model_name"], "Tests": f"{row['tests_passed']} / {row['tests_total']}" if row["tests_total"] else "Not run"} for row in rows[:8]],
            width="stretch", hide_index=True,
        )
    else:
        st.info("No evaluations yet. Start with a new evaluation to see results and history here.")


def _render_history(actor: dict[str, Any], database_path) -> None:
    st.title("My evaluations")
    search = st.text_input("Search question, name, or model/source", key="cg_history_search")
    rows = list_accessible_evaluations(actor["id"], limit=500, search=search, database_path=database_path)
    c1, c2, c3 = st.columns(3)
    tests_filter = c1.selectbox("Test status", ("All", "Has tests", "No tests", "All tests passed"))
    claim_filter = c2.selectbox("Claim status", ("All", "Has claims", "No claims"))
    sort_order = c3.selectbox("Sort", ("Newest first", "Oldest first"))
    if tests_filter == "Has tests":
        rows = [row for row in rows if row["tests_total"]]
    elif tests_filter == "No tests":
        rows = [row for row in rows if not row["tests_total"]]
    elif tests_filter == "All tests passed":
        rows = [row for row in rows if row["tests_total"] and row["tests_passed"] == row["tests_total"]]
    if claim_filter == "Has claims":
        rows = [row for row in rows if row["claims_total"]]
    elif claim_filter == "No claims":
        rows = [row for row in rows if not row["claims_total"]]
    if sort_order == "Oldest first":
        rows.reverse()
    page_size = 20
    pages = max(1, (len(rows) + page_size - 1) // page_size)
    page = st.number_input("Page", min_value=1, max_value=pages, value=1, step=1)
    page_rows = rows[(int(page) - 1) * page_size : int(page) * page_size]
    if not rows:
        st.info("No evaluations match these filters.")
        return
    st.dataframe(
        [{"ID": f"EVL-{row['id']:07d}", "Date (UTC)": row["created_at"], "Name": row["evaluation_name"] or "Untitled", "Question": row["question_text"], "Model/source": row["model_name"], "Python blocks": row["code_block_count"], "Tests": f"{row['tests_passed']} / {row['tests_total']}" if row["tests_total"] else "Not run", "Claims": row["claims_total"]} for row in page_rows],
        width="stretch", hide_index=True,
    )
    selected = st.selectbox("Open detailed result", [row["id"] for row in page_rows], format_func=lambda item: f"EVL-{item:07d} · {next(row['evaluation_name'] or row['question_text'][:65] for row in page_rows if row['id'] == item)}")
    _render_report(actor["id"], selected, database_path)


def _render_compare(actor: dict[str, Any], database_path) -> None:
    st.title("Compare evaluations")
    rows = list_accessible_evaluations(actor["id"], limit=500, database_path=database_path)
    groups = group_evaluations_by_question(rows)
    if not groups:
        st.info("No repeated question has multiple saved responses yet. Evaluate the same question with different AI responses to compare them.")
        return
    labels = {key: values for key, values in groups.items()}
    selected_group = st.selectbox("Question", list(labels), format_func=lambda key: labels[key][0]["question_text"][:150])
    group_rows = labels[selected_group]
    chosen = st.multiselect("Responses", [row["id"] for row in group_rows], default=[row["id"] for row in group_rows[:2]], format_func=lambda item: f"EVL-{item:07d} · {next(row['model_name'] for row in group_rows if row['id'] == item)}", max_selections=8)
    comparison = []
    for item_id in chosen:
        detail = get_accessible_evaluation(actor["id"], item_id, database_path=database_path)
        if not detail:
            continue
        tests = get_test_results(detail["response_id"], database_path)
        claims = get_claim_results(detail["response_id"], database_path)
        report = get_accessible_report(actor["id"], item_id, database_path=database_path)
        comparison.append({
            "Evaluation": f"EVL-{item_id:07d}", "Model/source": detail["model_name"],
            "Python blocks": len(detail["code_blocks"]),
            "Static result": ", ".join(item.get("status", "") for item in (report or {}).get("static_analysis", [])) or "Not checked",
            "Docker execution": ", ".join(item.get("status", "") for item in (report or {}).get("docker_executions", [])) or "Not run",
            "Tests passed": f"{sum(item['status']=='passed' for item in tests)} / {len(tests)}" if tests else "Not run",
            "Claims supported": sum(item.get("status") == "Supported" for item in claims),
            "Claims contradicted": sum(item.get("status") == "Contradicted" for item in claims),
            "ML pass_rate advisory": (report or {}).get("ml_reliability", {}).get("prediction", "Unavailable"),
        })
    if comparison:
        st.dataframe(comparison, width="stretch", hide_index=True)
        st.caption("Comparisons keep static, execution, test, evidence, and ML results separate. The ML value is not a correctness score.")


def _render_profile(actor: dict[str, Any], database_path) -> None:
    st.title("Profile")
    st.write(f"Role: **{actor['role']}**")
    st.caption(f"Account created: {actor['created_at']} · Last login: {actor.get('last_login') or 'This account has not signed in before.'}")
    with st.form("cg_profile_form"):
        username = st.text_input("Username or email", value=actor["username"])
        display_name = st.text_input("Display name", value=actor.get("display_name", ""))
        submitted = st.form_submit_button("Save profile")
    if submitted:
        try:
            updated = update_profile(actor["id"], username, display_name, database_path)
            st.success("Profile updated.")
            st.session_state["cg_username"] = updated["username"]
        except AuthenticationError as error:
            st.error(str(error))


def _developer_guard(actor_id: int, database_path) -> dict[str, Any]:
    return require_role(actor_id, DEVELOPER, database_path)


def _render_dev_overview(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("Developer overview")
    stats = developer_statistics(actor_id, database_path)
    fields = (
        ("Total evaluations", stats["total_evaluations"]),
        ("Evaluations today (UTC)", stats["evaluations_today_utc"]),
        ("Successful Docker evaluations", stats["successful_evaluations"]),
        ("Failed evaluations", stats["failed_evaluations"]),
        ("Average Python process time", f"{stats['average_python_process_seconds']:.4f} s" if stats["average_python_process_seconds"] is not None else "Unavailable"),
        ("Docker executions", stats["docker_executions"]),
        ("Claims analyzed", stats["claims_analyzed"]),
        ("Evidence lookups", stats["evidence_lookups"]),
        ("Errors today (UTC)", stats["errors_today_utc"]),
    )
    for start in range(0, len(fields), 4):
        cols = st.columns(4)
        for col, (label, value) in zip(cols, fields[start : start + 4]):
            col.metric(label, value)
    st.caption(f"Active model: {stats['active_model']} · SQLite: {stats['database_status']} · No combined reliability score is calculated.")
    rows = list_accessible_evaluations(actor_id, limit=10, database_path=database_path)
    st.subheader("Recent system activity")
    if rows:
        st.dataframe([{"ID": f"EVL-{row['id']:07d}", "UTC": row["created_at"], "Owner ID": row["owner_user_id"], "Question": row["question_text"], "Source": row["model_name"]} for row in rows], width="stretch", hide_index=True)
    else:
        st.info("No evaluations yet.")
    recent_logs = list_events(actor_id, limit=12, database_path=database_path)
    if recent_logs:
        st.subheader("Latest events")
        st.dataframe([{key: item[key] for key in ("timestamp", "level", "event", "evaluation_id", "component", "status", "error_type")} for item in recent_logs], width="stretch", hide_index=True)
    else:
        st.info("No logs yet.")


def _render_dev_evaluations(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("All evaluations")
    search = st.text_input("Search all evaluation questions, names, or sources", key="cg_dev_eval_search")
    rows = list_accessible_evaluations(actor_id, limit=500, search=search, database_path=database_path)
    if not rows:
        st.info("No evaluations yet.")
        return
    st.dataframe([{"ID": f"EVL-{row['id']:07d}", "UTC": row["created_at"], "Name": row["evaluation_name"], "Owner": row["owner_user_id"], "Question": row["question_text"], "Source": row["model_name"], "Tests": f"{row['tests_passed']}/{row['tests_total']}"} for row in rows], width="stretch", hide_index=True)
    selected = st.selectbox("Open evaluation", [row["id"] for row in rows], format_func=lambda item: f"EVL-{item:07d}")
    _render_report(actor_id, selected, database_path)


def _render_dev_logs(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("Application logs")
    event_names = ["All", *sorted({row["event"] for row in list_events(actor_id, limit=MAX_LOG_ROWS, database_path=database_path)})]
    with st.expander("Filters", expanded=True):
        a, b, c = st.columns(3)
        search = a.text_input("Search", key="cg_log_search")
        level = b.selectbox("Level", ("All", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
        event = c.selectbox("Event", event_names)
        d, e, f = st.columns(3)
        evaluation_id = d.text_input("Evaluation ID", placeholder="EVL-0000128")
        errors_only = e.toggle("Errors only", value=False)
        start_date = f.date_input("From date", value=None, key="cg_log_start")
        end_date = st.date_input("Through date", value=None, key="cg_log_end")
    rows = list_events(
        actor_id,
        limit=500, search=search, level=level, event=event, evaluation_id=evaluation_id,
        errors_only=errors_only, start_date=start_date.isoformat() if isinstance(start_date, date) else "",
        end_date=end_date.isoformat() if isinstance(end_date, date) else "", database_path=database_path,
    )
    if not rows:
        st.info("No logs yet." if not list_events(actor_id, limit=1, database_path=database_path) else "No events match these filters.")
        return
    st.dataframe([{key: row[key] for key in ("timestamp", "level", "event", "evaluation_id", "actor", "component", "duration_ms", "status", "error_type")} for row in rows], width="stretch", hide_index=True)
    for row in rows:
        with st.expander(f"{row['level']} · {row['event']} · {row['evaluation_id'] or 'system'}"):
            st.json(row["details"], expanded=False)


def _render_dev_health(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("System health")
    st.caption("Each status below comes from a live or artifact-backed check. The Docker probe never runs submitted code.")
    if st.button("Run health checks", type="primary", key="cg_run_health"):
        with st.spinner("Checking SQLite, Docker, model inference, evidence, directories, and configuration…"):
            st.session_state["cg_health_result"] = collect_health(actor_id, PROJECT_ROOT, database_path)
    result = st.session_state.get("cg_health_result")
    if not result:
        st.info("Run the checks to collect current system state.")
        return
    _status_message(result["status"])
    st.caption(f"Checked at {result['checked_at_utc']}")
    for component, details in result["checks"].items():
        with st.expander(f"{component} · {details.get('status', 'UNKNOWN')}", expanded=details.get("status") not in {"READY", "ONLINE"}):
            safe = {key: value for key, value in details.items() if key not in {"secret", "password", "token", "api_key"}}
            st.json(safe, expanded=False)


def _render_dev_docker(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("Docker execution boundary")
    st.warning("Local development execution boundary — not a production sandbox.")
    result = docker_status(actor_id, database_path)
    _status_message(result.get("status", "UNKNOWN"))
    st.json(result, expanded=True)
    config = docker_configuration()
    st.dataframe([{"Control": key.replace("_", " ").title(), "Configured value": json.dumps(value) if isinstance(value, dict) else value} for key, value in config.items()], width="stretch", hide_index=True)
    if st.button("Run harmless Python runtime probe", key="cg_docker_runtime_probe"):
        probe = run_docker_runtime_probe(actor_id, database_path=database_path)
        if probe["status"] == "READY":
            st.success(probe["message"])
        else:
            st.warning(probe["message"])


def _render_dev_ml(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("ML observability")
    model_path = PROJECT_ROOT / "models" / "phase17" / "pass_rate_predictor.joblib"
    config_files = ("feature_config.json", "training_config.json", "target_definition.json")
    st.write("**Phase 17 model:** " + ("Artifact present" if model_path.is_file() else "ML model unavailable"))
    if model_path.is_file():
        prediction = predict_pass_rate("def solution(values):\n    return sum(values)\n")
        if prediction.get("status") == "predicted":
            st.success(f"Inference loaded · model {prediction.get('model')} · target {prediction.get('target', 'pass_rate')}")
        else:
            st.warning(prediction.get("reason", "ML model unavailable"))
        st.caption("The Phase 17 model predicts the upstream dataset's pass_rate target and is NOT a general code correctness or security classifier.")
        st.metric("Phase 17 dataset usable records", prediction.get("dataset_size", {}).get("usable_records", "Not recorded"))
        for filename in config_files:
            path = PROJECT_ROOT / "models" / "phase17" / filename
            if path.is_file():
                with st.expander(filename):
                    st.json(json.loads(path.read_text(encoding="utf-8")), expanded=False)
        with st.expander("Run an advisory inference check", expanded=False):
            sample_code = st.text_area("Python code for ML advisory", value="def solution(values):\n    return sum(values)", key="cg_dev_ml_sample")
            if st.button("Predict source-domain pass_rate", key="cg_dev_ml_predict"):
                probe = predict_pass_rate(sample_code)
                if probe.get("status") == "predicted":
                    st.metric("Predicted upstream pass_rate", f"{probe['prediction']:.1%}")
                    st.json({key: probe.get(key) for key in ("model", "model_version", "task", "dataset_name", "dataset_size", "feature_fields", "feature_summary", "confidence_note", "limitations")}, expanded=False)
                else:
                    st.info("ML model unavailable")
                    st.caption(probe.get("reason", ""))
    metrics_path = PROJECT_ROOT / "docs" / "research" / "phase17" / "phase17_model_results.md"
    if metrics_path.is_file():
        with st.expander("Recorded held-out experiment metrics"):
            st.markdown(metrics_path.read_text(encoding="utf-8"))
    st.caption(f"Model artifact: `{model_path.relative_to(PROJECT_ROOT)}`. Inference does not execute code.")


def _corpus_documents() -> list[dict[str, Any]]:
    path = PROJECT_ROOT / "backend" / "src" / "codeguard" / "corpus" / "python_docs.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else value.get("documents", value.get("chunks", []))


def _render_dev_evidence(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("Evidence corpus")
    try:
        documents = _corpus_documents()
        st.metric("Corpus documents", len(documents))
        sources = sorted({row.get("url", row.get("source_url", "")) for row in documents if row.get("url") or row.get("source_url")})
        st.metric("Source URLs", len(sources))
        topics = sorted({row.get("topic", "") for row in documents if row.get("topic")})
        st.caption("Topics: " + (", ".join(topics) if topics else "Topic labels are not recorded in the checked-in corpus."))
        st.dataframe([{"Source URL": url} for url in sources], width="stretch", hide_index=True)
        query = st.text_input("Try a corpus retrieval", value="Python list mutability")
        if query.strip():
            matches = retrieve_evidence(query, top_k=5)
            if matches:
                st.dataframe([{"Title": item.get("title"), "Section": item.get("section"), "Score": item.get("retrieval_score"), "Source": item.get("url"), "Text": item.get("text")} for item in matches], width="stretch", hide_index=True)
            else:
                st.info("No evidence matched this query in the current corpus.")
    except (OSError, ValueError, TypeError) as error:
        st.error(f"Evidence corpus unavailable: {type(error).__name__}")


def _count_csv(path: Path, status_field: str = "") -> dict[str, Any]:
    counts: dict[str, int] = {}
    total = 0
    if not path.is_file():
        return {"available": False, "rows": 0, "counts": counts}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            total += 1
            if status_field:
                key = str(row.get(status_field, "unknown"))
                counts[key] = counts.get(key, 0) + 1
    return {"available": True, "rows": total, "counts": counts}


def _render_phase16_review(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.subheader("Phase 16 human review workspace")
    queue_csv = PHASE16_DIR / "review" / "review_queue.csv"
    review_db = PHASE16_DIR / "review" / "reviews.sqlite3"
    try:
        if not queue_csv.exists():
            build_phase16_workspace(PHASE16_DIR)
        initialize_review_db(queue_csv, review_db)
        counts = review_counts(review_db)
        cols = st.columns(4)
        for col, label, key in zip(cols, ("Queue", "Pending", "Reviewed", "Adjudicated"), ("total", "pending", "reviewed", "adjudicated")):
            col.metric(label, counts.get(key, 0))
        statuses = st.selectbox("Review status", ("Pending + disputed", "All", "Pending", "Disputed", "Reviewed / agreement", "Adjudicated", "Rejected"))
        status_map = {"Pending + disputed": {"pending", "disputed"}, "All": None, "Pending": {"pending"}, "Disputed": {"disputed"}, "Reviewed / agreement": {"reviewed"}, "Adjudicated": {"adjudicated"}, "Rejected": {"rejected"}}
        partition = st.selectbox("Review partition", ("All", "Internal", "External"))
        part = {"All": None, "Internal": "internal", "External": "external"}[partition]
        records = list_review_records(review_db, statuses=status_map[statuses], partition=part)
        if not records:
            st.info("No review records match this filter.")
            return
        review_id = st.selectbox("Candidate ID", [item["review_id"] for item in records])
        record = get_review_record(review_db, review_id)
        st.caption(f"{record.get('dataset_partition', '').upper()} · {record.get('review_status')} · {record.get('adjudication_status')}")
        st.markdown("**Claim**")
        st.write(record.get("claim", ""))
        st.markdown("**Evidence**")
        st.text(record.get("evidence", "No evidence supplied."))
        if record.get("source_url"):
            st.markdown(f"[Open official source]({record['source_url']})")
        if st.toggle("Hide proposed label while reviewing", value=True, key=f"cg_phase16_hide_{review_id}"):
            st.info("Proposed label hidden.")
        else:
            st.warning("Proposed label is unverified; do not treat it as an answer key.")
            st.write(record.get("proposed_label", ""))
        if record.get("review_status") not in {"adjudicated", "rejected"}:
            with st.form("cg_phase16_review_form"):
                slot = st.radio("Reviewer slot", ("A", "B"), horizontal=True)
                reviewer_id = st.text_input("Your real reviewer identifier")
                decision = st.selectbox("Review decision", tuple(sorted(REVIEW_DECISIONS)))
                confidence = st.slider("Confidence", 1, 5, 3)
                notes = st.text_area("Review rationale")
                mode = st.radio("Review method", ("Evidence only", "Evidence plus official source check"), horizontal=True)
                submit = st.form_submit_button("Save independent review")
            if submit:
                try:
                    source_verified = mode.startswith("Evidence plus")
                    save_independent_review(review_db, review_id, slot, decision=decision, confidence=confidence, notes=notes, reviewer_id=reviewer_id, review_mode="source_verified" if source_verified else "evidence_only", source_verified=source_verified)
                    st.success("Independent review saved.")
                    st.rerun()
                except (ValueError, KeyError) as error:
                    st.error(str(error))
        if record.get("review_status") in {"reviewed", "disputed"}:
            st.warning("A distinct, independent adjudicator is required before an adjudicated label is exported.")
            with st.form("cg_phase16_adjudication_form"):
                adjudicator = st.text_input("Real adjudicator identifier")
                decision = st.selectbox("Final decision", tuple(sorted(REVIEW_DECISIONS - {"Needs adjudication"})))
                notes = st.text_area("Adjudication rationale")
                submit = st.form_submit_button("Save adjudication")
            if submit:
                try:
                    save_adjudication(review_db, review_id, decision=decision, notes=notes, adjudicator_id=adjudicator)
                    st.success("Adjudication saved.")
                    st.rerun()
                except (ValueError, KeyError) as error:
                    st.error(str(error))
    except (OSError, sqlite3.Error, ValueError) as error:
        st.error(f"The Phase 16 review workspace could not be opened: {type(error).__name__}")


def _render_dev_datasets(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("Dataset observability")
    metadata_paths = (
        PROJECT_ROOT / "data" / "ml" / "research_dataset" / "dataset_metadata.json",
        PROJECT_ROOT / "data" / "raw" / "phase17" / "DATASET_METADATA.json",
    )
    for path in metadata_paths:
        if not path.is_file():
            st.info(f"Dataset metadata unavailable: {path.relative_to(PROJECT_ROOT)}")
            continue
        metadata = json.loads(path.read_text(encoding="utf-8"))
        with st.expander(str(metadata.get("dataset_name", path.stem)), expanded=True):
            st.json(metadata, expanded=False)
            st.caption("Reported metadata is shown from the checked-in dataset card; counts are not recomputed unless local source records are present.")
    pending = _count_csv(PROJECT_ROOT / "data" / "ml" / "phase16_5" / "pending_review.csv")
    if pending["available"]:
        st.metric("Pending review records in CSV", pending["rows"])
        st.caption("This is a proposal/review queue. It is not human verified or a gold-labelled dataset.")
    else:
        st.info("No candidate dataset yet.")
    _render_phase16_review(actor_id, database_path)


def _render_dev_users(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("User management information")
    users = list_users(actor_id, database_path)
    st.metric("Accounts", len(users))
    if users:
        st.dataframe(users, width="stretch", hide_index=True)
    else:
        st.info("No user accounts yet.")
    st.caption("Password hashes and credentials are never shown in this view. Account deletion and password reset are not implemented.")


def _render_dev_settings(actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    st.title("Application settings")
    st.dataframe([
        {"Setting": "CODEGUARD_ENV", "Value": os.environ.get("CODEGUARD_ENV", "local")},
        {"Setting": "LOG_LEVEL", "Value": os.environ.get("LOG_LEVEL", "INFO")},
        {"Setting": "OPENAI_API_KEY", "Value": "Configured" if os.environ.get("OPENAI_API_KEY", "").strip() else "Not configured"},
        {"Setting": "Database", "Value": str(database_path)},
        {"Setting": "Docker integration", "Value": "Uses existing restricted Docker runner"},
        {"Setting": "Evaluated language", "Value": "Python"},
    ], width="stretch", hide_index=True)
    st.caption("Secret values are never displayed. API keys are read only from the process environment when a user chooses the provider.")


def _render_user_page(page: str, actor: dict[str, Any], database_path) -> None:
    require_role(actor["id"], USER, database_path) if actor["role"] == USER else require_role(actor["id"], DEVELOPER, database_path)
    if page == "HOME":
        _render_home(actor, database_path)
    elif page == "NEW EVALUATION":
        _evaluate_page(actor, database_path)
    elif page == "MY EVALUATIONS":
        _render_history(actor, database_path)
    elif page == "COMPARE":
        _render_compare(actor, database_path)
    elif page == "PROFILE":
        _render_profile(actor, database_path)
    else:
        st.error("Page unavailable.")


def _render_developer_page(page: str, actor_id: int, database_path) -> None:
    _developer_guard(actor_id, database_path)
    renderers = {
        "OVERVIEW": _render_dev_overview,
        "EVALUATIONS": _render_dev_evaluations,
        "LOGS": _render_dev_logs,
        "SYSTEM HEALTH": _render_dev_health,
        "DOCKER": _render_dev_docker,
        "ML": _render_dev_ml,
        "EVIDENCE": _render_dev_evidence,
        "DATASETS": _render_dev_datasets,
        "USERS": _render_dev_users,
        "SETTINGS": _render_dev_settings,
    }
    renderer = renderers.get(page)
    if renderer:
        renderer(actor_id, database_path)
    else:
        st.error("Developer page unavailable.")


def render_application(database_path=None) -> None:
    """Entry point used by Streamlit and AppTest."""
    database_override = os.environ.get("CODEGUARD_DATABASE_PATH", "").strip()
    database_path = Path(database_path or database_override or DEFAULT_DATABASE_PATH)
    st.set_page_config(page_title="CodeGuard AI", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
    _theme()
    actor = _actor(database_path)
    if actor is None:
        _render_landing(database_path)
        return
    role = actor["role"]
    allowed_pages = DEVELOPER_NAVIGATION if role == DEVELOPER else USER_NAVIGATION
    with st.sidebar:
        st.markdown("## CODEGUARD AI")
        st.caption("Developer console" if role == DEVELOPER else "Your reliability workspace")
        st.markdown(f"**{actor.get('display_name') or actor['username']}** · {role}")
        page_state = "cg_navigation_developer" if role == DEVELOPER else "cg_navigation_user"
        current = st.session_state.get(page_state, allowed_pages[0])
        if current not in allowed_pages:
            current = allowed_pages[0]
        page = st.radio("Navigation", allowed_pages, index=allowed_pages.index(current), key=page_state, label_visibility="collapsed")
        st.divider()
        if st.button("Sign out", use_container_width=True, key="cg_sign_out"):
            _clear_session()
            st.rerun()
        st.caption("Local research/product prototype · Python only")
    st.markdown(f'<div class="cg-banner"><span class="cg-kicker">{role} workspace</span>　{page}</div>', unsafe_allow_html=True)
    if role == DEVELOPER:
        _render_developer_page(page, actor["id"], database_path)
    elif role == USER:
        _render_user_page(page, actor, database_path)
    else:
        _clear_session()
        st.error("This account role is not recognized.")
