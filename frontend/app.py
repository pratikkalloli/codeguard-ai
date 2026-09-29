from dataclasses import asdict
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SOURCE = PROJECT_ROOT / "backend" / "src"
if str(BACKEND_SOURCE) not in sys.path:
    sys.path.insert(0, str(BACKEND_SOURCE))

import sqlite3
import shutil
import subprocess

import streamlit as st

from codeguard.execution import run_function_tests, run_python
from codeguard.input_processing import extract_response
from codeguard.claim_verification import claim_result_dict, verify_explanation
from codeguard.comparison import group_evaluations_by_question
from codeguard.providers import OpenAIResponsesProvider, ProviderError
from codeguard.reports import build_reliability_report
from codeguard.storage import (
    get_claim_results,
    get_evaluation,
    get_evaluation_metrics,
    get_test_results,
    list_evaluations,
    save_evaluation,
    save_evaluation_metrics,
    save_claim_results,
    save_test_results,
)
from codeguard.validation import validate_python
from codeguard.ml.inference import apply_ml_advisories
from codeguard.ml.public_reliability import predict_pass_rate
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


NAVIGATION = [
    "OVERVIEW  ·  Dashboard",
    "EVALUATE  ·  New Evaluation",
    "EVALUATE  ·  Isolated Run",
    "EVALUATE  ·  Test Cases",
    "EVALUATE  ·  Explanation Analysis",
    "COMPARE  ·  Model Comparison",
    "ANALYTICS  ·  ML Performance",
    "ANALYTICS  ·  ML Reliability Analysis",
    "ANALYTICS  ·  Reliability Report",
    "ANALYTICS  ·  Evaluation History",
    "DEVELOPER  ·  Dataset Review",
]


def _system_status() -> dict[str, str]:
    """Probe real local state without running submitted code or making API calls."""
    try:
        list_evaluations(limit=1)
        database = "ONLINE"
    except Exception:
        database = "ERROR"
    docker = "OFFLINE"
    docker_cli = shutil.which("docker")
    if not docker_cli:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidate = Path(local_app_data) / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe"
        try:
            if candidate.is_file():
                docker_cli = str(candidate)
        except OSError:
            # A configured-but-unreadable Docker install is unavailable here.
            docker_cli = None
    if docker_cli:
        try:
            result = subprocess.run(
                [docker_cli, "info", "--format", "{{.OSType}}"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            if result.returncode == 0 and result.stdout.strip() == "linux":
                docker = "ONLINE"
        except (OSError, subprocess.TimeoutExpired):
            pass
    corpus_path = PROJECT_ROOT / "backend" / "src" / "codeguard" / "corpus" / "python_docs.json"
    model_path = PROJECT_ROOT / "models" / "claim_verifier" / "claim_verifier_v1.joblib"
    auxiliary_model_path = PROJECT_ROOT / "models" / "phase17" / "pass_rate_predictor.joblib"
    return {
        "Docker": docker,
        "OpenAI API": "CONFIGURED" if os.environ.get("OPENAI_API_KEY", "").strip() else "NOT CONFIGURED",
        "ML model": "AVAILABLE" if model_path.is_file() and model_path.stat().st_size > 0 else "NOT AVAILABLE",
        "Auxiliary ML": "AVAILABLE" if auxiliary_model_path.is_file() and auxiliary_model_path.stat().st_size > 0 else "NOT AVAILABLE",
        "Documentation corpus": "AVAILABLE" if corpus_path.is_file() else "NOT AVAILABLE",
        "Database": database,
    }


def _inject_theme(theme: str) -> None:
    """Apply the app-wide visual system while leaving Streamlit behavior intact."""
    if theme == "Light":
        colors = """
        --cg-bg:#f3f6fb; --cg-surface:#ffffff; --cg-surface2:#f7f9fc;
        --cg-border:#dce3ed; --cg-text:#182230; --cg-muted:#617084;
        --cg-accent:#3157d5; --cg-accent-soft:#e8edff; --cg-shadow:0 10px 28px rgba(27,44,76,.07);
        """
    else:
        colors = """
        --cg-bg:#0b1018; --cg-surface:#111a26; --cg-surface2:#172231;
        --cg-border:#243247; --cg-text:#e8eef8; --cg-muted:#9aa9bc;
        --cg-accent:#85a8ff; --cg-accent-soft:#192a4b; --cg-shadow:0 12px 34px rgba(0,0,0,.22);
        """
    st.markdown(f"""
    <style>
    :root {{ {colors} }}
    .stApp {{ background:var(--cg-bg); color:var(--cg-text); }}
    [data-testid="stHeader"] {{ background:transparent; }}
    [data-testid="stSidebar"] {{ background:var(--cg-surface); border-right:1px solid var(--cg-border); }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color:var(--cg-muted); }}
    [data-testid="stSidebar"] label {{ color:var(--cg-text)!important; }}
    .block-container {{ max-width:1500px; padding-top:1.25rem; padding-bottom:3rem; }}
    [data-testid="stMetric"] {{ background:var(--cg-surface); border:1px solid var(--cg-border); border-radius:15px; padding:18px 20px; box-shadow:var(--cg-shadow); }}
    [data-testid="stMetricLabel"] {{ color:var(--cg-muted); }}
    [data-testid="stMetricValue"] {{ color:var(--cg-text); }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ border-color:var(--cg-border); border-radius:16px; }}
    [data-testid="stExpander"] {{ border-color:var(--cg-border); border-radius:12px; background:var(--cg-surface); }}
    [data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input,[data-testid="stSelectbox"] [data-baseweb="select"] > div {{ background:var(--cg-surface2); border-color:var(--cg-border); border-radius:10px; }}
    .stButton button,[data-testid="stFormSubmitButton"] button {{ border-radius:10px; min-height:2.65rem; font-weight:600; transition:transform .15s ease, box-shadow .15s ease; }}
    .stButton button:hover,[data-testid="stFormSubmitButton"] button:hover {{ transform:translateY(-1px); box-shadow:var(--cg-shadow); }}
    [data-testid="stTabs"] > [data-baseweb="tab-list"] {{ display:none; }}
    .cg-topbar {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; margin:0 0 1.5rem; padding:12px 17px; background:var(--cg-surface); border:1px solid var(--cg-border); border-radius:14px; box-shadow:var(--cg-shadow); }}
    .cg-brand {{ color:var(--cg-text); font-weight:750; letter-spacing:-.02em; }}
    .cg-topmeta {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }}
    .cg-pill {{ padding:5px 9px; border-radius:999px; border:1px solid var(--cg-border); background:var(--cg-surface2); color:var(--cg-muted); font-size:.76rem; }}
    .cg-hero {{ padding:27px 30px; border-radius:18px; border:1px solid var(--cg-border); background:linear-gradient(120deg,var(--cg-surface),var(--cg-accent-soft)); box-shadow:var(--cg-shadow); margin-bottom:20px; }}
    .cg-hero h1 {{ margin:0 0 8px; letter-spacing:-.04em; color:var(--cg-text); font-size:2.25rem; }}
    .cg-hero p {{ margin:0; color:var(--cg-muted); max-width:720px; }}
    .cg-kicker {{ color:var(--cg-accent); font-size:.72rem; font-weight:750; letter-spacing:.12em; text-transform:uppercase; margin-bottom:9px; }}
    [data-testid="stCode"] {{ border:1px solid var(--cg-border); border-radius:12px; }}
    h1,h2,h3 {{ letter-spacing:-.025em; }}
    @media(max-width:760px) {{ .block-container {{ padding:1rem .85rem 2rem; }} .cg-topbar {{ align-items:flex-start; flex-direction:column; }} .cg-hero {{ padding:21px; }} .cg-hero h1 {{ font-size:1.8rem; }} [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{ min-width:100%!important; flex:1 1 100%!important; }} }}
    @media(prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ transition:none!important; scroll-behavior:auto!important; }} }}
    </style>
    """, unsafe_allow_html=True)


def _navigate_to(target: str) -> None:
    """Streamlit widget callback used by dashboard shortcut buttons."""
    st.session_state["cg_navigation"] = target


def _execution_metric_rows(result):
    """Prepare transparent performance measurements for display and storage."""
    rows = [
        {
            "metric_name": "python_process_wall_time",
            "metric_value": result.code_execution_seconds,
            "unit": "seconds",
            "measurement_type": result.code_time_measurement_type,
        },
        {
            "metric_name": "docker_engine_check_time",
            "metric_value": result.engine_check_seconds,
            "unit": "seconds",
            "measurement_type": "Host-observed Docker engine connectivity check; not submitted-code time",
        },
        {
            "metric_name": "image_readiness_check_time",
            "metric_value": result.image_readiness_seconds,
            "unit": "seconds",
            "measurement_type": "Host-observed local image inspection; image download/preparation is not included",
        },
        {
            "metric_name": "image_preparation_or_download_time",
            "metric_value": None,
            "unit": "seconds",
            "measurement_type": "Not performed during an evaluation; python:3.12-slim is pre-pulled. Download time is not measured or included.",
        },
        {
            "metric_name": "container_startup_time",
            "metric_value": result.container_startup_seconds,
            "unit": "seconds",
            "measurement_type": result.container_startup_measurement_type,
        },
        {
            "metric_name": "docker_run_wall_time",
            "metric_value": result.docker_run_seconds,
            "unit": "seconds",
            "measurement_type": "Host-observed docker run lifetime; includes startup, process, and teardown",
        },
        {
            "metric_name": "docker_overhead_estimate",
            "metric_value": result.docker_overhead_estimate_seconds,
            "unit": "seconds",
            "measurement_type": result.docker_overhead_measurement_type,
        },
        {
            "metric_name": "end_to_end_workflow_time",
            "metric_value": result.duration_seconds,
            "unit": "seconds",
            "measurement_type": "Host-observed total including Docker checks, startup, execution, and teardown",
        },
        {
            "metric_name": "container_cgroup_peak_memory",
            "metric_value": result.memory_peak_bytes,
            "unit": "bytes",
            "measurement_type": result.memory_measurement_type,
        },
    ]
    return rows


def _format_metric_value(value, unit):
    if value is None:
        return "Unavailable"
    if unit == "bytes":
        return f"{value / (1024 * 1024):.2f} MiB ({int(value):,} bytes)"
    return f"{float(value):.6f} s"


def _record_response(question, response, model_name, generated_response=None):
    """Run manual and API responses through the same extraction/evaluation pipeline."""
    extracted = extract_response(response)
    session_id = save_evaluation(
        question=question,
        raw_response=response,
        code_blocks=extracted.code_blocks,
        explanation=extracted.explanation,
        model_name=model_name,
    )
    saved = get_evaluation(session_id)
    claims = apply_ml_advisories(verify_explanation(extracted.explanation))
    save_claim_results(saved["response_id"], [claim_result_dict(claim) for claim in claims])
    if generated_response:
        api_metrics = [
            {
                "metric_name": "model_api_wall_time",
                "metric_value": generated_response.duration_seconds,
                "unit": "seconds",
                "measurement_type": "Host-observed remote API request wall time; includes network and provider processing",
            }
        ]
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(generated_response, name)
            if value is not None:
                api_metrics.append(
                    {
                        "metric_name": f"model_api_{name}",
                        "metric_value": value,
                        "unit": "tokens",
                        "measurement_type": "Token count reported by the API response",
                    }
                )
        save_evaluation_metrics(saved["response_id"], api_metrics)
    return session_id, extracted


from phase20_ui import render_application

# Phase 20 provides role-gated pages and calls the existing CodeGuard services.
# Keep the former research UI below as a source of preserved workflow references;
# it is no longer a second, unauthenticated route into developer functionality.
render_application()
st.stop()

st.set_page_config(page_title="CodeGuard AI", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
with st.sidebar:
    st.markdown("## 🛡️ CodeGuard AI")
    st.caption("AI Reliability Platform")
    theme = st.toggle("Light theme", value=False, key="cg_light_theme")
    theme_name = "Light" if theme else "Dark"
    st.markdown("---")
    st.markdown("#### Workspace")
    selected_nav = st.radio("Navigate", NAVIGATION, index=0, label_visibility="collapsed", key="cg_navigation")
    st.markdown("---")
    st.markdown("#### System status")
    system_status = _system_status()
    for status_name, status_value in system_status.items():
        dot = "🟢" if status_value in {"ONLINE", "AVAILABLE", "CONFIGURED"} else ("🔴" if status_value in {"ERROR"} else "⚪")
        st.caption(f"{dot} **{status_name}:** {status_value}")
    st.caption("Docker status checks the daemon only; it does not run submitted code.")
    st.caption("OpenAI status reflects key presence only; no provider request is made by this check.")

_inject_theme(theme_name)
page_name = selected_nav.split("·", 1)[1].strip()
tab_labels = [
    "Dashboard", "New Evaluation", "Isolated Run", "Test Cases", "Explanation Analysis",
    "Model Comparison", "ML Performance", "ML Reliability Analysis", "Reliability Report", "Evaluation History", "Dataset Review",
]
tab_default = next((label for label in tab_labels if label.casefold() == page_name.casefold()), "Dashboard")
status_pills = "".join(f'<span class="cg-pill">{name}: {value}</span>' for name, value in system_status.items() if name in {"Docker", "OpenAI API"})
st.markdown(
    f'<div class="cg-topbar"><div class="cg-brand">🛡️ CodeGuard AI <span style="font-weight:400;color:var(--cg-muted)">/ {page_name}</span></div><div class="cg-topmeta">{status_pills}</div></div>',
    unsafe_allow_html=True,
)

dashboard_tab, input_tab, run_tab, tests_tab, claims_tab, compare_tab, ml_tab, auxiliary_ml_tab, report_tab, history_tab, review_tab = st.tabs(
    tab_labels, default=tab_default
)

with dashboard_tab:
    st.markdown('<div class="cg-hero"><div class="cg-kicker">AI Reliability Platform</div><h1>Evaluate AI-generated code before you trust it.</h1><p>Test correctness, execution safety, performance, and explanation reliability in one workflow.</p></div>', unsafe_allow_html=True)
    hero_left, hero_right = st.columns([1, 4])
    with hero_left:
        st.button("＋ New Evaluation", type="primary", use_container_width=True, on_click=_navigate_to, args=(NAVIGATION[1],))
    with hero_right:
        st.button("View History", use_container_width=False, on_click=_navigate_to, args=(NAVIGATION[-1],))
    overview_evaluations = list_evaluations(limit=500)
    overview_responses = [get_evaluation(row["id"]) for row in overview_evaluations]
    overview_responses = [row for row in overview_responses if row]
    overview_code_count = sum(len(row["code_blocks"]) for row in overview_responses)
    model_groups = group_evaluations_by_question(overview_evaluations)
    resolved_claim_count = 0
    for saved in overview_responses:
        resolved_claim_count += sum(row["status"] in {"Supported", "Contradicted"} for row in get_claim_results(saved["response_id"]))
    overview_cols = st.columns(4)
    overview_cols[0].metric("Evaluations", len(overview_responses), help="Saved SQLite evaluation records")
    overview_cols[1].metric("Code blocks", overview_code_count, help="Extracted Python blocks saved in history")
    overview_cols[2].metric("Claims resolved", resolved_claim_count, help="Supported or contradicted by the narrow evidence rules")
    overview_cols[3].metric("Prompts compared", len(model_groups), help="Saved prompt groups with more than one response")
    st.caption("Metrics reflect saved data only. No combined reliability score is calculated.")
    if overview_evaluations:
        st.markdown("### Recent evaluations")
        left_panel, right_panel = st.columns([1.55, 1])
        with left_panel:
            st.markdown("#### Activity timeline")
            counts_by_day = Counter(row["created_at"][:10] for row in overview_evaluations if row.get("created_at"))
            st.line_chart({"Evaluations": dict(sorted(counts_by_day.items()))}, height=210, color="#85a8ff")
        with right_panel:
            st.markdown("#### Claim evidence distribution")
            claim_counts = Counter()
            for saved in overview_responses:
                claim_counts.update(row["status"] for row in get_claim_results(saved["response_id"]))
            if claim_counts:
                st.bar_chart({"Claims": dict(claim_counts)}, height=210, color="#85a8ff")
            else:
                st.info("No saved explanation claims yet.")
        st.markdown("#### Recent evaluations")
        st.dataframe(
            [
                {"ID": row["id"], "Date": row["created_at"], "Question": row["question_text"], "Model/source": row["model_name"], "Code": row["code_block_count"], "Tests": len(get_test_results(get_evaluation(row["id"])["response_id"])) if get_evaluation(row["id"]) else 0}
                for row in overview_evaluations[:8]
            ],
            width="stretch", height="auto",
            hide_index=True,
        )
    else:
        st.info("Your evaluation activity will appear here after your first saved response.")
    st.markdown("### System health")
    status_cols = st.columns(5)
    for col, (status_name, status_value) in zip(status_cols, system_status.items()):
        col.metric(status_name, status_value)

with input_tab:
    with st.form("response_form"):
        response_source = st.radio(
            "Response source",
            ["Manual paste", "OpenAI API"],
            horizontal=True,
        )
        question_col, response_col = st.columns(2, gap="large")
        with question_col:
            st.markdown("#### Coding question")
            question = st.text_area(
                "Coding question",
                placeholder="For example: Write a function that adds two numbers.",
                height=220,
                label_visibility="collapsed",
            )
        with response_col:
            st.markdown("#### AI response")
            if response_source == "Manual paste":
                manual_model_name = st.text_input("Model/source label", value="Manual input")
                response = st.text_area(
                    "Paste the AI response",
                    placeholder="Paste the response. Python fences such as ```python will be extracted.",
                    height=220,
                    label_visibility="collapsed",
                )
            else:
                response = ""
                api_model_name = st.text_input(
                    "OpenAI model",
                    value=os.environ.get("CODEGUARD_OPENAI_MODEL", "gpt-6-astra"),
                )
                st.caption(
                    "Optional API usage may be billed. The key comes from OPENAI_API_KEY; it is never entered or saved by this form."
                )
        submitted = st.form_submit_button("Run Evaluation", type="primary")

    if submitted:
        if not question.strip():
            st.error("Enter the coding question first.")
        else:
            model_name = (
                manual_model_name.strip() or "Manual input"
                if response_source == "Manual paste"
                else "OpenAI API"
            )
            generated_response = None
            if response_source == "OpenAI API":
                try:
                    with st.spinner("Requesting a response from OpenAI…"):
                        generated_response = OpenAIResponsesProvider(model_name=api_model_name.strip() or None).generate(question)
                    response = generated_response.text
                    model_name = f"{generated_response.provider_name} / {generated_response.model_name}"
                except ProviderError as error:
                    st.error(str(error))
            if not response.strip():
                if response_source == "Manual paste":
                    st.error("Paste an AI response first.")
            else:
                session_id, result = _record_response(question, response, model_name, generated_response)
                st.session_state["last_question"] = question.strip()
                st.session_state["last_response"] = response
                st.session_state["last_result"] = result
                st.session_state["last_validation"] = [
                    validate_python(code) for code in result.code_blocks
                ]
                st.session_state["last_session_id"] = session_id
                st.success(f"Saved evaluation #{session_id} from {model_name} to local history.")

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        st.markdown("### Evaluation pipeline")
        pipeline_labels = ["INPUT", "EXTRACTION", "STATIC ANALYSIS", "EXECUTION", "TESTING", "PERFORMANCE", "EXPLANATION", "EVIDENCE", "REPORT"]
        code_found = bool(result.code_blocks)
        pipeline_states = ["Complete", "Complete" if code_found else "No code found", "Complete" if code_found else "Not applicable", "Not run", "Not run", "Not run", "Analyzed", "Analyzed", "Available"]
        pipeline_cols = st.columns(5)
        for index, (label, stage_status) in enumerate(zip(pipeline_labels, pipeline_states)):
            with pipeline_cols[index % 5]:
                st.caption(f"**{label}**")
                st.write(f"{'✓' if stage_status in {'Complete', 'Analyzed', 'Available'} else '○'} {stage_status}")
        if code_found:
            st.info("Execution, test cases, and performance remain **Not run** until started from their dedicated pages. Submitted code is never run from this form.")
        st.markdown("### Result snapshot")
        current_detail = get_evaluation(st.session_state["last_session_id"])
        current_claims = get_claim_results(current_detail["response_id"]) if current_detail else []
        current_tests = get_test_results(current_detail["response_id"]) if current_detail else []
        current_cards = st.columns(3)
        current_cards[0].metric("Code correctness", "Syntax checked" if code_found else "No code found")
        current_cards[1].metric("Security", "Static review" if code_found else "Not available")
        current_cards[2].metric("Test results", f"{sum(row['status'] == 'passed' for row in current_tests)} / {len(current_tests)}" if current_tests else "Not run")
        current_cards2 = st.columns(3)
        current_cards2[0].metric("Performance", "Available" if current_detail and get_evaluation_metrics(current_detail["response_id"]) else "Not run")
        current_cards2[1].metric("Explanation claims", len(current_claims))
        current_cards2[2].metric("Evidence supported", sum(row["status"] == "Supported" for row in current_claims))
        st.caption("These are separate observations, not an overall reliability score. A static review is not a security guarantee.")
        st.subheader("Extraction preview")
        st.caption(f"Saved evaluation #{st.session_state['last_session_id']} — Question: {st.session_state['last_question']}")

        if result.code_blocks:
            st.success(f"Found {len(result.code_blocks)} Python code block(s).")
            for index, code in enumerate(result.code_blocks, start=1):
                with st.expander(f"Python code block {index}", expanded=True):
                    st.code(code, language="python", line_numbers=True)
                    validation = st.session_state["last_validation"][index - 1]
                    if validation.status == "valid":
                        st.success(validation.message)
                    elif validation.status == "valid_with_risks":
                        st.warning(validation.message)
                    else:
                        st.error(validation.message)
                    for finding in validation.findings:
                        line = f" (line {finding.line})" if finding.line else ""
                        st.warning(f"{finding.rule}{line}: {finding.message}")
        else:
            st.warning("No Python code fences found. The complete response is shown as explanation text below.")

        explanation = result.explanation.strip()
        st.subheader("Explanation text")
        st.text(explanation if explanation else "No explanation text was found outside the Python code blocks.")

with claims_tab:
    st.subheader("Explanation claim analysis")
    st.info(
        "Claims are compared with a small, curated corpus from official Python documentation using local TF-IDF retrieval and explicit proposition rules. "
        "A high similarity score alone never establishes truth. Unsupported or out-of-scope claims remain Insufficient evidence."
    )
    evaluations = list_evaluations()
    if not evaluations:
        st.caption("Save an AI response first to analyze its explanation.")
    else:
        selected_claim_eval_id = st.selectbox(
            "Evaluation to analyze",
            options=[row["id"] for row in evaluations],
            format_func=lambda item_id: f"#{item_id}: {next(row['question_text'][:70] for row in evaluations if row['id'] == item_id)}",
            key="claims_evaluation_id",
        )
        claim_detail = get_evaluation(selected_claim_eval_id)
        claim_rows = get_claim_results(claim_detail["response_id"]) if claim_detail else []
        if not claim_rows:
            st.caption("No sentence-level claims were extracted from this explanation.")
        else:
            summary = {}
            for claim in claim_rows:
                summary[claim["status"]] = summary.get(claim["status"], 0) + 1
            st.write("Status counts: " + " · ".join(f"{status}: {count}" for status, count in summary.items()))
            for index, claim in enumerate(claim_rows, start=1):
                with st.expander(f"Claim {index}: {claim['claim_text'][:100]}", expanded=index == 1):
                    st.markdown(f"**Claim**\n\n{claim['claim_text']}")
                    if claim["status"] == "Supported":
                        st.success("SUPPORTED")
                    elif claim["status"] == "Contradicted":
                        st.error("CONTRADICTED BY RETRIEVED DOCUMENTATION")
                    elif claim["status"] == "Insufficient evidence":
                        st.warning("INSUFFICIENT EVIDENCE")
                    else:
                        st.info("NOT EVALUATED")
                    verification_method = (
                        "Narrow proposition rule with retrieved documentation"
                        if claim["status"] in {"Supported", "Contradicted"}
                        else "Heuristic claim extraction; no verified proposition rule"
                        if claim["status"] == "Insufficient evidence"
                        else "Heuristic sentence classification; factual verification was not performed"
                    )
                    st.caption(f"Verification method: {verification_method}. ML predictions are advisory and never replace evidence-backed rule results.")
                    if claim.get("ml_result"):
                        ml_status_col, ml_conf_col = st.columns(2)
                        ml_status_col.metric("ML advisory prediction", claim["ml_result"].replace("_", " ").title())
                        ml_conf_col.metric("Uncalibrated class probability", f"{claim['ml_confidence']:.3f}" if claim.get("ml_confidence") is not None else "Unavailable")
                        if claim.get("ml_review_required"):
                            st.warning("LOW CONFIDENCE / REVIEW REQUIRED — the rule-based status remains authoritative and ML is not documentary evidence.")
                        else:
                            st.info("ML is advisory only. It did not override the evidence-based result.")
                    st.markdown(f"**Why**\n\n{claim['reason']}")
                    if claim["evidence_text"]:
                        passage_label = (
                            "Retrieved evidence"
                            if claim["status"] in {"Supported", "Contradicted"}
                            else "Retrieved candidate passage (not accepted as sufficient evidence)"
                        )
                        st.markdown(f"**{passage_label}**\n\n> {claim['evidence_text']}")
                        if claim["source_url"]:
                            st.markdown(f"**Source:** [{claim['title'] or claim['source']}]({claim['source_url']})")
                        if claim["retrieval_score"] is not None:
                            st.caption(
                                f"TF-IDF cosine similarity: {claim['retrieval_score']:.3f} · "
                                f"Retrieval time: {claim['retrieval_seconds']:.6f} s · "
                                f"Chunk: {claim['evidence_chunk_id']}"
                            )
                    else:
                        st.caption("No matching documentation evidence was retrieved from the current corpus.")

with run_tab:
    st.subheader("Run code in Docker")
    evaluations = list_evaluations()
    if not evaluations:
        st.caption("Save an AI response first, then select its Python code here.")
    else:
        selected_run_id = st.selectbox(
            "Evaluation to run",
            options=[row["id"] for row in evaluations],
            format_func=lambda item_id: f"#{item_id}: {next(row['question_text'][:70] for row in evaluations if row['id'] == item_id)}",
            key="run_evaluation_id",
        )
        run_detail = get_evaluation(selected_run_id)
        if run_detail and run_detail["code_blocks"]:
            selected_run_block = st.selectbox(
                "Python code block",
                options=run_detail["code_blocks"],
                format_func=lambda block: f"Block {block['block_index']}",
                key="run_code_block",
            )
            st.code(selected_run_block["code_text"], language="python", line_numbers=True)
            st.caption("Docker is configured with a 3 second default timeout, 128 MiB memory, 0.5 CPU, 32 processes, no network, no host mounts, and 64 KiB combined output cap.")
            if st.button("Run inside restricted container", type="primary", key="run_python_button"):
                with st.spinner("Starting the isolated container…"):
                    run_result = run_python(selected_run_block["code_text"])
                performance_rows = _execution_metric_rows(run_result)
                save_evaluation_metrics(run_detail["response_id"], performance_rows)
                st.session_state["latest_execution"] = run_result
                st.session_state["latest_execution_key"] = (
                    run_detail["response_id"], selected_run_block["block_index"]
                )
            current_execution_key = (run_detail["response_id"], selected_run_block["block_index"])
            if st.session_state.get("latest_execution_key") == current_execution_key:
                run_result = st.session_state["latest_execution"]
                if run_result.status == "Passed":
                    st.success(f"{run_result.status} · {run_result.duration_seconds:.3f} seconds end to end")
                elif run_result.status in {"Timeout", "Security blocked"}:
                    st.warning(f"{run_result.status} · {run_result.duration_seconds:.3f} seconds end to end")
                else:
                    st.error(f"{run_result.status} · {run_result.duration_seconds:.3f} seconds end to end")
                st.subheader("Performance measurements")
                st.dataframe(
                    [
                        {
                            "Measurement": row["metric_name"].replace("_", " ").title(),
                            "Value": _format_metric_value(row["metric_value"], row["unit"]),
                            "Measurement type": row["measurement_type"],
                        }
                        for row in performance_rows
                    ],
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    "Python process wall time includes starting and exiting a second Python interpreter, so it is not a pure algorithm benchmark. "
                    "The Docker overhead value is an estimate. The memory number is the whole container's cgroup peak, including Python and sandbox overhead. "
                    "The image was pre-pulled; image download time is not measured here."
                )
                if run_result.stdout:
                    st.markdown("**Standard output**")
                    st.code(run_result.stdout)
                if run_result.stderr:
                    st.markdown("**Errors / details**")
                    st.code(run_result.stderr)
        else:
            st.info("This evaluation has no extracted Python code block to run.")

with tests_tab:
    st.subheader("Manual function test cases")
    st.caption(
        "Enter one JSON array of positional arguments per line and one expected JSON return value per line. "
        "For example, inputs [2, 3] with expected output 5 calls add(2, 3). Each case gets a fresh Docker container."
    )
    evaluations = list_evaluations()
    if not evaluations:
        st.caption("Save an AI response first to add test cases.")
    else:
        selected_test_id = st.selectbox(
            "Evaluation to test",
            options=[row["id"] for row in evaluations],
            format_func=lambda item_id: f"#{item_id}: {next(row['question_text'][:70] for row in evaluations if row['id'] == item_id)}",
            key="test_evaluation_id",
        )
        test_detail = get_evaluation(selected_test_id)
        if test_detail and test_detail["code_blocks"]:
            selected_test_block = st.selectbox(
                "Python code block to test",
                options=test_detail["code_blocks"],
                format_func=lambda block: f"Block {block['block_index']}",
                key="test_code_block",
            )
            function_name = st.text_input("Function name", value="add", key="test_function_name")
            inputs_text = st.text_area(
                "Inputs (one JSON array per line)",
                value="[2, 3]\n[-2, 5]",
                height=100,
                key="test_inputs_json",
            )
            expected_text = st.text_area(
                "Expected return values (one JSON value per line)",
                value="5\n3",
                height=100,
                key="test_expected_json",
            )
            if st.button("Run test cases in Docker", type="primary", key="run_test_cases_button"):
                input_lines = [line.strip() for line in inputs_text.splitlines() if line.strip()]
                expected_lines = [line.strip() for line in expected_text.splitlines() if line.strip()]
                if not input_lines or len(input_lines) != len(expected_lines):
                    st.error("Provide the same nonzero number of input lines and expected-value lines.")
                else:
                    try:
                        cases = [
                            {"inputs": json.loads(input_line), "expected": json.loads(expected_line)}
                            for input_line, expected_line in zip(input_lines, expected_lines)
                        ]
                        with st.spinner("Running each test in its own restricted container…"):
                            test_results = run_function_tests(
                                selected_test_block["code_text"],
                                function_name,
                                cases,
                            )
                        save_test_results(
                            test_detail["response_id"],
                            [asdict(result) for result in test_results],
                        )
                        test_metric_rows = []
                        for result in test_results:
                            prefix = result.test_name.lower().replace(" ", "_")
                            test_metric_rows.extend(
                                [
                                    {
                                        "metric_name": f"{prefix}_python_process_wall_time",
                                        "metric_value": result.code_execution_seconds,
                                        "unit": "seconds",
                                        "measurement_type": result.code_time_measurement_type,
                                    },
                                    {
                                        "metric_name": f"{prefix}_container_cgroup_peak_memory",
                                        "metric_value": result.memory_peak_bytes,
                                        "unit": "bytes",
                                        "measurement_type": result.memory_measurement_type,
                                    },
                                ]
                            )
                        save_evaluation_metrics(test_detail["response_id"], test_metric_rows)
                        st.session_state["latest_test_results"] = test_results
                        st.session_state["latest_test_key"] = (
                            test_detail["response_id"],
                            selected_test_block["block_index"],
                            function_name.strip(),
                        )
                    except (json.JSONDecodeError, ValueError) as error:
                        st.error(f"Test input is not valid standard JSON: {error}")
            if (
                "latest_test_results" in st.session_state
                and st.session_state.get("latest_test_key")
                == (test_detail["response_id"], selected_test_block["block_index"], function_name.strip())
            ):
                test_results = st.session_state["latest_test_results"]
                passed = sum(result.status == "passed" for result in test_results)
                st.metric("Tests passed", f"{passed} / {len(test_results)}")
                st.dataframe(
                    [
                        {
                            "Test": result.test_name,
                            "Inputs": result.inputs_json,
                            "Status": result.status.replace("_", " ").title(),
                            "Expected": result.expected_output,
                            "Actual": result.actual_output,
                            "Python process time (s)": (
                                f"{result.code_execution_seconds:.6f}"
                                if result.code_execution_seconds is not None
                                else "Unavailable"
                            ),
                            "Container peak memory": (
                                f"{result.memory_peak_bytes / (1024 * 1024):.2f} MiB"
                                if result.memory_peak_bytes is not None
                                else "Unavailable"
                            ),
                            "Details": result.error_message,
                        }
                        for result in test_results
                    ],
                    width="stretch",
                    hide_index=True,
                )
        else:
            st.info("This evaluation has no extracted Python code block to test.")

with compare_tab:
    st.subheader("Compare responses to the same question")
    evaluations = list_evaluations(limit=500)
    question_groups = group_evaluations_by_question(evaluations)
    if not question_groups:
        st.info(
            "Save at least two responses for the same question. Use Manual paste to label each model, "
            "or select OpenAI API and choose a model."
        )
    else:
        question_keys = sorted(
            question_groups,
            key=lambda key: question_groups[key][0]["question_text"].casefold(),
        )
        selected_question_key = st.selectbox(
            "Question",
            options=question_keys,
            format_func=lambda key: question_groups[key][0]["question_text"],
            key="comparison_question_key",
        )
        compare_rows = question_groups[selected_question_key]
        st.caption("Only exact questions after case and whitespace normalization are grouped together.")
        comparison_table = []
        model_cards = []
        for evaluation_row in compare_rows:
            detail = get_evaluation(evaluation_row["id"])
            tests = get_test_results(detail["response_id"])
            metrics = get_evaluation_metrics(detail["response_id"])
            claims = get_claim_results(detail["response_id"])
            validations = [validate_python(block["code_text"]) for block in detail["code_blocks"]]
            if not validations:
                syntax_summary = "No code"
            elif all(item.status == "valid" for item in validations):
                syntax_summary = "All blocks parse"
            elif any(item.status in {"syntax_error", "missing"} for item in validations):
                syntax_summary = "Syntax issue"
            else:
                syntax_summary = "Parses with risk warnings"
            passed = sum(row["status"] == "passed" for row in tests)
            process_time = next(
                (row["metric_value"] for row in metrics if row["metric_name"] == "python_process_wall_time"),
                None,
            )
            api_time = next(
                (row["metric_value"] for row in metrics if row["metric_name"] == "model_api_wall_time"),
                None,
            )
            status_counts = {}
            for claim in claims:
                status_counts[claim["status"]] = status_counts.get(claim["status"], 0) + 1
            model_cards.append({
                "id": evaluation_row["id"], "name": evaluation_row["model_name"],
                "syntax": syntax_summary,
                "tests": f"{passed} / {len(tests)}" if tests else "Not run",
                "execution": f"{process_time:.6f} s" if process_time is not None else "Unavailable",
                "supported": status_counts.get("Supported", 0),
                "contradicted": status_counts.get("Contradicted", 0),
                "insufficient": status_counts.get("Insufficient evidence", 0),
            })
            comparison_table.append(
                {
                    "Evaluation": evaluation_row["id"],
                    "Model/source": evaluation_row["model_name"],
                    "Static syntax": syntax_summary,
                    "Tests passed": f"{passed}/{len(tests)}" if tests else "Not run",
                    "Python process time": f"{process_time:.6f} s" if process_time is not None else "Unavailable",
                    "API latency": f"{api_time:.3f} s" if api_time is not None else "Unavailable",
                    "Claim statuses": ", ".join(f"{key}: {value}" for key, value in status_counts.items()) or "Not analyzed",
                }
            )
        st.dataframe(comparison_table, width="stretch", hide_index=True)
        st.caption(
            "No combined score is calculated. Test, runtime, and claim values may be unavailable until those evaluations are run. "
            "Runtime is not a pure algorithm benchmark."
        )
        for model_card in model_cards:
            with st.container(border=True):
                st.markdown(f"#### {model_card['name']} · Evaluation #{model_card['id']}")
                card_metrics = st.columns(4)
                card_metrics[0].metric("Code validity", model_card["syntax"])
                card_metrics[1].metric("Tests passed", model_card["tests"])
                card_metrics[2].metric("Python process time", model_card["execution"])
                card_metrics[3].metric("Claims supported", model_card["supported"])
                claim_metrics = st.columns(2)
                claim_metrics[0].metric("Claims contradicted", model_card["contradicted"])
                claim_metrics[1].metric("Insufficient evidence", model_card["insufficient"])
        for evaluation_row in compare_rows:
            with st.expander(f"Response #{evaluation_row['id']} · {evaluation_row['model_name']}"):
                detail = get_evaluation(evaluation_row["id"])
                st.markdown("**Python code**")
                for block in detail["code_blocks"]:
                    st.code(block["code_text"], language="python", line_numbers=True)
                st.markdown("**Explanation**")
                st.write(detail["explanation_text"] or "No explanation text.")

        st.markdown("**Add another response for this question**")
        compare_model = st.text_input(
            "OpenAI model for another response",
            value=os.environ.get("CODEGUARD_OPENAI_MODEL", "gpt-6-astra"),
            key="comparison_openai_model",
        )
        if st.button("Request and evaluate with OpenAI", key="comparison_openai_button"):
            try:
                with st.spinner("Requesting and evaluating another response…"):
                    generated = OpenAIResponsesProvider(model_name=compare_model.strip() or None).generate(
                        compare_rows[0]["question_text"]
                    )
                    _record_response(
                        compare_rows[0]["question_text"],
                        generated.text,
                        f"{generated.provider_name} / {generated.model_name}",
                        generated,
                    )
                st.success("Response saved through the standard evaluation pipeline. Reopen the tab to compare it.")
            except ProviderError as error:
                st.error(str(error))

with ml_tab:
    st.markdown("## ML performance")
    metrics_path = PROJECT_ROOT / "reports" / "pilot" / "ml_metrics.json"
    dataset_path = PROJECT_ROOT / "data" / "ml" / "dataset_metadata.json"
    ml_report = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else None
    ml_dataset = json.loads(dataset_path.read_text(encoding="utf-8")) if dataset_path.is_file() else None
    st.caption("Training metrics come from the saved synthetic pilot and its held-out split. They are a workflow demonstration, not estimates of real-world claim verification quality.")
    all_saved = list_evaluations(limit=500)
    observed_api_rows = []
    for saved_row in all_saved:
        saved_detail = get_evaluation(saved_row["id"])
        if not saved_detail:
            continue
        for metric in get_evaluation_metrics(saved_detail["response_id"]):
            if metric["metric_name"] == "model_api_wall_time" and metric["metric_value"] is not None:
                observed_api_rows.append({"Model": saved_detail["model_name"], "Evaluation": saved_row["id"], "API response latency (s)": metric["metric_value"]})
    st.markdown("### Model and dataset")
    if ml_report and ml_dataset:
        metadata_cols = st.columns(5)
        metadata_values = [
            ("Model", ml_report.get("model_version", "Not available")),
            ("Dataset", ml_report.get("dataset_version", "Not available")),
            ("Samples", ml_report.get("dataset_size", "Not available")),
            ("Training", ml_report.get("split_samples", {}).get("train", "Not available")),
            ("Validation / test", f"{ml_report.get('split_samples', {}).get('validation', 'Not available')} / {ml_report.get('split_samples', {}).get('test', 'Not available')}"),
        ]
        for col, (label, value) in zip(metadata_cols, metadata_values):
            col.metric(label, value)
        st.caption("Data origin: " + ", ".join(f"{name}={count}" for name, count in ml_report.get("data_origins", {}).items()))
        st.markdown("### Held-out test metrics")
        logistic_metrics = ml_report.get("test_metrics", {}).get("logistic_regression_tfidf", {})
        metric_values = [
            ("Accuracy", logistic_metrics.get("accuracy")),
            ("Precision (macro)", logistic_metrics.get("precision_macro")),
            ("Recall (macro)", logistic_metrics.get("recall_macro")),
            ("F1 (micro)", logistic_metrics.get("f1_micro")),
            ("Macro F1", logistic_metrics.get("f1_macro")),
            ("Weighted F1", logistic_metrics.get("f1_weighted")),
        ]
        ml_metric_cols = st.columns(3)
        for index, (label, value) in enumerate(metric_values):
            ml_metric_cols[index % 3].metric(label, f"{value:.3f}" if isinstance(value, (int, float)) else "Not available")
        st.warning(ml_report.get("integrity_note", "Metrics must be interpreted with dataset provenance and test sample size."))
        st.markdown("### Class distribution")
        st.bar_chart({"Samples": ml_report.get("class_distribution", {})}, height=210, color="#85a8ff")
        st.markdown("### Model comparison")
        model_rows = []
        for model_name, values in ml_report.get("test_metrics", {}).items():
            model_rows.append({"Model": model_name, "Test samples": values.get("sample_count"), "Accuracy": values.get("accuracy"), "Precision (macro)": values.get("precision_macro"), "Recall (macro)": values.get("recall_macro"), "F1 (micro)": values.get("f1_micro"), "Macro F1": values.get("f1_macro"), "Weighted F1": values.get("f1_weighted")})
        st.dataframe(model_rows, width="stretch", hide_index=True)
        st.markdown("### Stratified cross-validation on training partition")
        cv_rows = [{"Model": name, **values} for name, values in ml_report.get("cross_validation", {}).items()]
        st.dataframe(cv_rows, width="stretch", hide_index=True)
        matrix_path = PROJECT_ROOT / "reports" / "pilot" / "confusion_matrix.png"
        if matrix_path.is_file():
            st.markdown("### Confusion matrix")
            st.image(str(matrix_path), caption="Logistic Regression on the held-out synthetic test split; rows are actual classes.", width="stretch")
        st.markdown("### Error analysis")
        logistic_errors = ml_report.get("error_analysis", {}).get("logistic_regression_tfidf", {})
        if logistic_errors.get("errors"):
            st.dataframe(logistic_errors["errors"], width="stretch", hide_index=True)
            st.caption("Error categories: " + (", ".join(f"{key}: {value}" for key, value in logistic_errors.get("error_categories", {}).items()) or "None"))
        else:
            st.caption("No Logistic Regression misclassifications occurred in this tiny held-out split; this does not establish generalization.")
        st.markdown("### Per-class results")
        st.dataframe([{"Class": label, **values} for label, values in logistic_metrics.get("per_class", {}).items()], width="stretch", hide_index=True)
        st.caption("Confidence threshold was derived from the tiny validation partition. Logistic Regression class probabilities are uncalibrated and are not truth probabilities.")
    else:
        st.info("No generated training metrics are available yet. Run `python -m codeguard.ml.train` to build the dataset, train baselines, and evaluate the held-out split.")
    if not ml_report:
        st.caption("Predictive metrics, confusion matrix, cross-validation, and error analysis: Not available until training finishes.")
    st.markdown("### Observed provider performance")
    if observed_api_rows:
        st.dataframe(observed_api_rows, width="stretch", hide_index=True)
        st.bar_chart(
            {"API response latency (s)": {f"#{row['Evaluation']} · {row['Model']}": row["API response latency (s)"] for row in observed_api_rows}},
            height=300,
            color="#85a8ff",
        )
        st.caption("Host-observed API wall time includes network and provider processing; it is not an ML model quality metric.")
    else:
        st.caption("No API response latency measurements have been saved.")

with auxiliary_ml_tab:
    st.subheader("ML reliability analysis · auxiliary pass-rate estimate")
    phase17_results_path = PROJECT_ROOT / "reports" / "phase17" / "phase17_model_results.json"
    phase17_metadata_path = PROJECT_ROOT / "data" / "raw" / "phase17" / "DATASET_METADATA.json"
    if phase17_results_path.is_file():
        phase17_results = json.loads(phase17_results_path.read_text(encoding="utf-8"))
        st.caption(
            f"Model: {phase17_results.get('selected_model_by_validation_mae', 'unknown')} · "
            f"Dataset revision: {phase17_results.get('revision', 'unknown')} · "
            f"Task: {phase17_results.get('task', 'auxiliary prediction')}"
        )
        test_metrics = phase17_results.get("models", {}).get(
            phase17_results.get("selected_model_by_validation_mae", ""), {}
        ).get("test", {})
        metric_cols = st.columns(4)
        for col, label, key in zip(metric_cols, ("Test MAE", "Test RMSE", "Test R²", "Test Spearman"),
                                   ("mae", "rmse", "r2", "spearman_rho")):
            value = test_metrics.get(key)
            col.metric(label, f"{value:.4f}" if isinstance(value, (float, int)) else "Unavailable")
    else:
        st.info("Phase 17 model has not been trained in this workspace yet.")
    st.warning(
        "This model estimates benchmark execution pass rate from competitive-programming solution code. "
        "It is trained on generated/automated data and is not a CodeGuard claim verdict or human-reviewed label."
    )
    with st.form("phase17_auxiliary_form"):
        auxiliary_code = st.text_area("Python code", height=220, key="phase17_auxiliary_code")
        auxiliary_explanation = st.text_area("Explanation (evaluated separately by evidence verifier)", height=100,
                                             key="phase17_auxiliary_explanation")
        auxiliary_source = st.text_input("Optional source metadata", key="phase17_auxiliary_source")
        auxiliary_run = st.form_submit_button("Analyze", type="primary")
    if auxiliary_run:
        if not auxiliary_code.strip():
            st.error("Enter Python code to analyze.")
        else:
            deterministic = validate_python(auxiliary_code)
            st.markdown("**Deterministic static verifier**")
            if deterministic.status == "valid":
                st.success(deterministic.message)
            elif deterministic.status == "valid_with_risks":
                st.warning(deterministic.message)
            else:
                st.error(deterministic.message)
            prediction = predict_pass_rate(
                auxiliary_code,
                auxiliary_explanation,
                {"source": auxiliary_source or "unknown"},
            )
            st.markdown("**ML prediction**")
            if prediction.get("status") == "predicted":
                st.metric("Estimated execution pass rate", f"{prediction['prediction']:.1%}")
                st.caption(f"Model: {prediction['model']} · version: {prediction['model_version']} · confidence is not calibrated")
            else:
                st.info(prediction.get("reason", "Model prediction unavailable."))
            st.markdown("**Evidence verifier**")
            evidence_claims = verify_explanation(auxiliary_explanation) if auxiliary_explanation.strip() else []
            if evidence_claims:
                st.dataframe([claim_result_dict(claim) for claim in evidence_claims], hide_index=True, width="stretch")
            else:
                st.caption("No explanation claims were supplied for evidence verification.")
            st.markdown("**Final CodeGuard decision**")
            st.caption("The current application reports these signals independently; it does not combine them into one verdict.")

with report_tab:
    st.subheader("Reliability report")
    evaluations = list_evaluations(limit=500)
    if not evaluations:
        st.caption("Save an evaluation to create a reliability report.")
    else:
        report_id = st.selectbox(
            "Evaluation to report",
            options=[row["id"] for row in evaluations],
            format_func=lambda item_id: f"#{item_id}: {next(row['question_text'][:70] for row in evaluations if row['id'] == item_id)}",
            key="report_evaluation_id",
        )
        report_detail = get_evaluation(report_id)
        report_code_blocks = report_detail.get("code_blocks", [])
        if report_code_blocks:
            try:
                ml_prediction = predict_pass_rate(
                    report_code_blocks[0]["code_text"],
                    metadata={"source": report_detail.get("model_name", "unknown")},
                )
            except Exception as error:
                ml_prediction = {
                    "status": "not_available",
                    "reason": f"Phase 17 prediction failed: {type(error).__name__}: {error}",
                }
            ml_prediction["code_block_index"] = 1
        else:
            ml_prediction = {
                "status": "not_available",
                "reason": "No extracted Python code block is available for pass-rate prediction.",
            }
        report_data = build_reliability_report(
            report_detail,
            get_test_results(report_detail["response_id"]),
            get_evaluation_metrics(report_detail["response_id"]),
            get_claim_results(report_detail["response_id"]),
            ml_reliability=ml_prediction,
        )
        st.caption("The report keeps individual observations separate; it does not invent a single reliability score.")
        ml_signal = report_data["ml_reliability"]
        st.markdown("### ML Reliability Signal")
        if ml_signal["available"]:
            st.metric(
                "Predicted execution pass-rate reliability",
                f"{ml_signal['prediction']:.4f}",
                help=(
                    "Regression estimate of source-recorded execution test pass rate for competitive-programming code. "
                    "It is not general code correctness, factual verification, or a CodeGuard verdict."
                ),
            )
            st.caption(
                f"Model: {ml_signal['model']} · version: {ml_signal['model_version']} · "
                f"code block: {ml_signal.get('code_block_index', 1)} · "
                f"task: {ml_signal['task']} · dataset: {ml_signal.get('dataset_name') or 'Unavailable'}"
            )
            size = ml_signal.get("dataset_size", {})
            st.caption(
                "Dataset rows — downloaded: "
                f"{size.get('downloaded_records', 'Unavailable'):,} · usable: "
                f"{size.get('usable_records', 'Unavailable'):,} · "
                f"reported full split: {size.get('reported_full_python_records', 'Unavailable'):,}"
                if all(isinstance(size.get(key), int) for key in ("downloaded_records", "usable_records", "reported_full_python_records"))
                else f"Dataset row counts: {size or 'Unavailable'}"
            )
            st.caption(ml_signal["confidence_note"])
        else:
            st.info(ml_signal.get("reason") or "Phase 17 prediction is unavailable.")
        report_sections = [
            ("Evaluation overview", {"evaluation": report_data["evaluation"], "test_summary": report_data["test_summary"]}),
            ("Static AST Analysis", report_data["signals"]["static_ast_analysis"]),
            ("Docker Execution", report_data["signals"]["docker_execution"]),
            ("Function Tests", report_data["signals"]["function_tests"]),
            ("Performance Measurement", report_data["signals"]["performance_measurement"]),
            ("Explanation Claims", report_data["signals"]["explanation_claims"]),
            ("Evidence Retrieval", report_data["signals"]["evidence_retrieval"]),
            ("Claim Verification", report_data["signals"]["claim_verification"]),
            ("ML Reliability Signal", report_data["signals"]["ml_reliability"]),
            ("Limitations", report_data["limitations"]),
        ]
        for section_title, section_data in report_sections:
            with st.expander(section_title, expanded=section_title == "Evaluation overview"):
                st.json(section_data, expanded=True)
        st.download_button(
            "Download reliability report (JSON)",
            data=json.dumps(report_data, ensure_ascii=False, indent=2),
            file_name=f"codeguard-evaluation-{report_id}.json",
            mime="application/json",
        )

with history_tab:
    st.subheader("Saved evaluations")
    evaluations = list_evaluations()
    if not evaluations:
        st.caption("No saved evaluations yet. Submit an input in the New evaluation tab first.")
    else:
        st.dataframe(
            [
                {
                    "ID": row["id"],
                    "Created (UTC)": row["created_at"],
                    "Question": row["question_text"],
                    "Source / model": row["model_name"],
                    "Python blocks": row["code_block_count"],
                    "Tests": len(get_test_results(get_evaluation(row["id"])["response_id"])) if get_evaluation(row["id"]) else 0,
                    "Claims": len(get_claim_results(get_evaluation(row["id"])["response_id"])) if get_evaluation(row["id"]) else 0,
                }
                for row in evaluations
            ],
            width="stretch",
            hide_index=True,
        )
        selected_id = st.selectbox(
            "Open evaluation",
            options=[row["id"] for row in evaluations],
            format_func=lambda item_id: f"#{item_id}: {next(row['question_text'][:70] for row in evaluations if row['id'] == item_id)}",
        )
        detail = get_evaluation(selected_id)
        if detail:
            st.caption(f"Saved at {detail['created_at']} UTC · {detail['model_name']}")
            st.markdown("**Coding question**")
            st.write(detail["question_text"])
            st.markdown("**Extracted Python code**")
            if detail["code_blocks"]:
                for block in detail["code_blocks"]:
                    st.code(block["code_text"], language="python", line_numbers=True)
                    validation = validate_python(block["code_text"])
                    if validation.status == "valid":
                        st.success(validation.message)
                    elif validation.status == "valid_with_risks":
                        st.warning(validation.message)
                    else:
                        st.error(validation.message)
                    for finding in validation.findings:
                        line = f" (line {finding.line})" if finding.line else ""
                        st.warning(f"{finding.rule}{line}: {finding.message}")
            else:
                st.caption("No Python code fences were extracted.")
            st.markdown("**Explanation text**")
            st.text(detail["explanation_text"] or "No explanation text was found.")
            saved_test_results = get_test_results(detail["response_id"])
            if saved_test_results:
                st.markdown("**Saved test-case results**")
                passed_tests = sum(row["status"] == "passed" for row in saved_test_results)
                st.metric("Tests passed", f"{passed_tests} / {len(saved_test_results)}")
                st.dataframe(
                    [
                        {
                            "Test": row["test_name"],
                            "Inputs": row["inputs_json"],
                            "Status": row["status"].replace("_", " ").title(),
                            "Expected": row["expected_output"],
                            "Actual": row["actual_output"],
                            "Details": row["error_message"],
                        }
                        for row in saved_test_results
                    ],
                    width="stretch",
                    hide_index=True,
                )
            saved_metrics = get_evaluation_metrics(detail["response_id"])
            if saved_metrics:
                st.markdown("**Saved performance measurements**")
                st.dataframe(
                    [
                        {
                            "Measurement": row["metric_name"].replace("_", " ").title(),
                            "Value": _format_metric_value(row["metric_value"], row["unit"]),
                            "Measurement type": row["measurement_type"],
                        }
                        for row in saved_metrics
                    ],
                    width="stretch",
                    hide_index=True,
                )

with review_tab:
    st.markdown("### DATASET REVIEW · developer only")
    st.warning(
        "This local review workspace is separate from production inference and evaluation history. "
        "Proposed labels are unverified suggestions. Only real, independent human decisions are saved. "
        "The page does not train or modify a model."
    )
    queue_csv = PHASE16_DIR / "review" / "review_queue.csv"
    review_db = PHASE16_DIR / "review" / "reviews.sqlite3"
    try:
        if not queue_csv.exists():
            build_phase16_workspace(PHASE16_DIR)
        initialize_review_db(queue_csv, review_db)
        counts = review_counts(review_db)
        count_cols = st.columns(5)
        for col, label, key in zip(count_cols,
            ("Queue records", "Pending", "Agreed/reviewed", "Disputed", "Adjudicated"),
            ("total", "pending", "reviewed", "disputed", "adjudicated")):
            col.metric(label, counts[key])
        closed = counts["reviewed"] + counts["adjudicated"] + counts["rejected"]
        st.progress(closed / counts["total"] if counts["total"] else 0,
                    text=f"Double-reviewed or resolved records: {closed} / {counts['total']}")

        st.markdown("**Reviewer protocol**")
        st.caption("Read the claim and supplied evidence. Label only what that evidence establishes; do not import outside knowledge unless you mark source verification. Use Reject or Needs adjudication for ambiguity.")
        filter_name = st.selectbox("Queue filter", (
            "Priority queue (pending + disputed)", "All records", "Pending", "Disputed",
            "Reviewed / agreement", "Adjudicated", "Rejected"), key="cg_review_status_filter")
        filter_statuses = {
            "Priority queue (pending + disputed)":{"pending","disputed"},
            "All records":None, "Pending":{"pending"}, "Disputed":{"disputed"},
            "Reviewed / agreement":{"reviewed"}, "Adjudicated":{"adjudicated"}, "Rejected":{"rejected"},
        }[filter_name]
        partition = st.selectbox("Records", ("External candidates first · all records", "Internal candidates only", "External candidates only"), key="cg_review_partition_filter")
        partition_filter = {"External candidates first · all records":None,
                            "Internal candidates only":"internal", "External candidates only":"external"}[partition]
        records = list_review_records(review_db, statuses=filter_statuses, partition=partition_filter)
        batch_ids = sorted({r.get("batch_id", "") for r in records if r.get("batch_id")})
        batch_filter = st.selectbox("Review batch", ["All batches", *batch_ids], key="cg_review_batch_filter")
        if batch_filter != "All batches":
            records = [r for r in records if r.get("batch_id") == batch_filter]
        topic_values = sorted({r.get("topic", "") for r in records if r.get("topic")})
        topic_filter = st.selectbox("Topic", ["All topics", *topic_values], key="cg_review_topic_filter")
        if topic_filter != "All topics":
            records = [r for r in records if r.get("topic") == topic_filter]
        source_values = sorted({r.get("source_url", "") for r in records if r.get("source_url")})
        source_filter = st.selectbox("Source", ["All sources", *source_values], key="cg_review_source_filter")
        if source_filter != "All sources":
            records = [r for r in records if r.get("source_url") == source_filter]
        source_group_values = sorted({r.get("source_group", "") or r.get("evidence_group", "") for r in records
                                      if r.get("source_group") or r.get("evidence_group")})
        source_group_filter = st.selectbox("Source group", ["All source groups", *source_group_values], key="cg_review_source_group_filter")
        if source_group_filter != "All source groups":
            records = [r for r in records if (r.get("source_group") or r.get("evidence_group", "")) == source_group_filter]
        proposed_values = sorted({r.get("proposed_label", "") for r in records if r.get("proposed_label")})
        proposed_filter = st.selectbox("Proposed label", ["All proposals", *proposed_values], key="cg_review_proposed_filter")
        if proposed_filter != "All proposals":
            records = [r for r in records if r.get("proposed_label") == proposed_filter]
        reviewer_values = sorted({rid for r in records for rid in (r.get("reviewer_A_id"), r.get("reviewer_B_id")) if rid})
        reviewer_filter = st.selectbox("Reviewer", ["All reviewers", *reviewer_values], key="cg_review_reviewer_filter")
        if reviewer_filter != "All reviewers":
            records = [r for r in records if reviewer_filter in (r.get("reviewer_A_id"), r.get("reviewer_B_id"))]
        adjudication_values = sorted({r.get("adjudication_status", "") for r in records if r.get("adjudication_status")})
        adjudication_filter = st.selectbox("Adjudication", ["All adjudication states", *adjudication_values], key="cg_review_adjudication_filter")
        if adjudication_filter != "All adjudication states":
            records = [r for r in records if r.get("adjudication_status") == adjudication_filter]
        if not records:
            st.success("No records match this queue filter.")
        else:
            valid_review_ids = {row["review_id"] for row in records}
            if st.session_state.get("cg_review_record_id") not in valid_review_ids:
                st.session_state["cg_review_record_id"] = records[0]["review_id"]
            selected_review_id = st.selectbox(
                "Candidate ID",
                options=[row["review_id"] for row in records],
                format_func=lambda rid: next(
                    f"{r['dataset_partition'].upper()} · {r.get('batch_id','unbatched')} · {r['review_id']} · {r['review_status']} · {r.get('topic','')}"
                    for r in records if r["review_id"] == rid),
                key="cg_review_record_id",
            )
            record = get_review_record(review_db, selected_review_id)
            st.caption(f"{record['dataset_partition'].upper()} candidate · {record.get('batch_id','unbatched')} · {record['review_status']} · {record['adjudication_status']} · {record.get('topic','')}")
            st.caption(f"Source section: {record.get('source_section','not recorded')} · License: {record.get('license','not recorded')}")
            st.markdown("**Claim**")
            st.write(record["claim"])
            st.markdown("**Evidence**")
            st.text(record["evidence"] or "No evidence passage was supplied.")
            st.markdown("**Source**")
            if record.get("source_url"):
                st.markdown(f"[{record.get('source_title') or record.get('source_name') or 'Open source'}]({record['source_url']})")
            else:
                st.write("No source URL recorded.")
            hide_proposal = st.toggle("Hide proposed label while reviewing", value=True, key=f"cg_hide_proposal_{selected_review_id}")
            if hide_proposal:
                st.info("Proposed label hidden.")
            else:
                st.markdown("**Proposed label — unverified; do not treat as an answer key**")
                st.info(record["proposed_label"])
            st.caption("Insufficient Evidence means this passage does not establish truth or falsity; do not use it as a synonym for Contradicted.")

            if record["review_status"] not in {"adjudicated", "rejected"}:
                with st.form("cg_independent_dataset_review", clear_on_submit=False):
                    reviewer_slot = st.radio("Review slot", ("Reviewer A", "Reviewer B"), horizontal=True)
                    reviewer_id = st.text_input("Your real reviewer identifier", key=f"cg_reviewer_id_{selected_review_id}_{reviewer_slot}",
                                                help="Enter your real reviewer identity. Do not invent another person's identity.")
                    review_decision = st.selectbox("Your decision", tuple(sorted(REVIEW_DECISIONS)), key=f"cg_review_decision_{selected_review_id}_{reviewer_slot}")
                    confidence = st.slider("Confidence", min_value=1, max_value=5, value=3, key=f"cg_review_confidence_{selected_review_id}_{reviewer_slot}")
                    notes = st.text_area("Reviewer notes", key=f"cg_review_notes_{selected_review_id}_{reviewer_slot}",
                                         help="Explain whether the supplied passage entails, contradicts, or does not establish the claim.")
                    review_mode = st.radio("Review method", ("Evidence only", "Evidence plus official source check"), horizontal=True,
                                           key=f"cg_review_mode_{selected_review_id}_{reviewer_slot}")
                    save_review = st.form_submit_button("Save independent review", type="primary")
                if save_review:
                    try:
                        mode = "source_verified" if review_mode == "Evidence plus official source check" else "evidence_only"
                        save_independent_review(review_db, selected_review_id, reviewer_slot[-1],
                            decision=review_decision, confidence=confidence, notes=notes, reviewer_id=reviewer_id,
                            review_mode=mode, source_verified=(mode == "source_verified"))
                        st.success("Review saved in the separate local review database.")
                        st.rerun()
                    except (ValueError, KeyError) as exc:
                        st.error(str(exc))

            nav_left, nav_skip, nav_right = st.columns(3)
            selected_index = next(i for i,r in enumerate(records) if r["review_id"] == selected_review_id)
            def select_review_id(review_id: str) -> None:
                st.session_state["cg_review_record_id"] = review_id
            nav_left.button("← Previous", disabled=selected_index == 0, key="cg_review_previous",
                            on_click=select_review_id, args=(records[selected_index-1]["review_id"] if selected_index else selected_review_id,))
            nav_skip.button("Skip", disabled=selected_index >= len(records)-1, key="cg_review_skip",
                            on_click=select_review_id, args=(records[selected_index+1]["review_id"] if selected_index < len(records)-1 else selected_review_id,))
            nav_right.button("Next →", disabled=selected_index >= len(records)-1, key="cg_review_next",
                             on_click=select_review_id, args=(records[selected_index+1]["review_id"] if selected_index < len(records)-1 else selected_review_id,))

            if record.get("reviewer_A_timestamp") or record.get("reviewer_B_timestamp"):
                st.markdown("**Submitted review records**")
                st.dataframe([{"Slot":"A","Reviewer":record.get("reviewer_A_id"),"Decision":record.get("reviewer_A_label"),
                               "Confidence":record.get("reviewer_A_confidence"),"Review time":record.get("reviewer_A_timestamp"),
                               "Method":record.get("reviewer_A_mode"),"Source checked":record.get("reviewer_A_source_verified")},
                              {"Slot":"B","Reviewer":record.get("reviewer_B_id"),"Decision":record.get("reviewer_B_label"),
                               "Confidence":record.get("reviewer_B_confidence"),"Review time":record.get("reviewer_B_timestamp"),
                               "Method":record.get("reviewer_B_mode"),"Source checked":record.get("reviewer_B_source_verified")}],
                             hide_index=True, width="stretch")

            if record["review_status"] in {"disputed", "reviewed"}:
                st.markdown("#### Adjudication")
                if record["review_status"] == "disputed":
                    st.warning("The reviews disagree or a reviewer requested adjudication. An independent third person must resolve the record.")
                else:
                    st.info("The reviewers agree. A separate independent adjudicator must still record the final decision before this can enter a gold-labeled export.")
                st.dataframe([{"Reviewer A decision":record["reviewer_A_label"],"Reviewer A identifier":record["reviewer_A_id"],
                               "Reviewer B decision":record["reviewer_B_label"],"Reviewer B identifier":record["reviewer_B_id"]}],
                             hide_index=True, width="stretch")
                with st.form("cg_dataset_adjudication"):
                    adjudicator_id = st.text_input("Real adjudicator identifier", key=f"cg_adjudicator_id_{selected_review_id}")
                    adjudication_decision = st.selectbox("Final adjudicated decision", tuple(sorted(REVIEW_DECISIONS - {"Needs adjudication"})), key=f"cg_adjudication_decision_{selected_review_id}")
                    adjudication_notes = st.text_area("Adjudication rationale", key=f"cg_adjudication_notes_{selected_review_id}")
                    save_adjudication_button = st.form_submit_button("Save adjudication")
                if save_adjudication_button:
                    try:
                        save_adjudication(review_db, selected_review_id, decision=adjudication_decision,
                            notes=adjudication_notes, adjudicator_id=adjudicator_id)
                        st.success("Adjudication saved. The record export has been updated.")
                        st.rerun()
                    except (ValueError, KeyError) as exc:
                        st.error(str(exc))
    except (OSError, sqlite3.Error, ValueError) as exc:
        st.error(f"The Phase 16 review workspace could not be opened: {exc}")
