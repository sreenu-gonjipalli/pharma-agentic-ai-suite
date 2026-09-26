#!/usr/bin/env python3
"""Deviation Review -- Case Pipeline page (unified_app). Runs deviation-review's Supervisor
live, shows the evidence bundle as readable tables (not raw JSON), and logs a human approval
decision via deviation-review's own src/hitl.approve_case -- the only path to logs/approved/,
same shape as the PV page's approval form (named approver, one of APPROVE/EDIT/REJECT, notes;
never a bare yes/no).

Deviation Review is a separate, independently-governed project (../deviation-review) -- this
page only imports and calls its existing code, never forks or edits its own logic (per this
folder's ground rules in PROGRESS.md).
"""
import csv
import glob
import json
import os
import sys

import streamlit as st

PAGE_DIR = os.path.dirname(os.path.abspath(__file__))
UNIFIED_ROOT = os.path.dirname(PAGE_DIR)
DEVIATION_REVIEW_ROOT = os.path.normpath(os.path.join(UNIFIED_ROOT, "..", "deviation-review"))
sys.path.insert(0, DEVIATION_REVIEW_ROOT)

from src import supervisor, hitl, trace as trace_log  # noqa: E402

CASES_DIR = os.path.join(DEVIATION_REVIEW_ROOT, "logs", "cases")
DEVIATIONS_CSV = os.path.join(DEVIATION_REVIEW_ROOT, "data", "deviations.csv")

st.title("Deviation Review -- Case Pipeline")
st.caption(
    "Prototype only -- synthetic data, no real patient/product data, no connection to a live "
    "quality or clinical system. Every classification is advisory until a human approver logs "
    "an APPROVE decision below."
)


def list_deviation_ids():
    with open(DEVIATIONS_CSV, newline="") as f:
        return [r["deviation_id"] for r in csv.DictReader(f)]


def list_saved_cases():
    paths = sorted(glob.glob(os.path.join(CASES_DIR, "*.json")), reverse=True)
    return [os.path.splitext(os.path.basename(p))[0] for p in paths]


def as_table(value):
    """Render a single record or a list of records as a readable table instead of raw JSON."""
    if isinstance(value, list):
        st.dataframe(value, use_container_width=True)
    elif isinstance(value, dict):
        st.dataframe([value], use_container_width=True)
    else:
        st.write(value)


with st.sidebar:
    st.subheader("OpenRouter")
    if os.environ.get("OPENROUTER_API_KEY"):
        st.success("OPENROUTER_API_KEY is set.")
    else:
        st.error("OPENROUTER_API_KEY is not set -- prose steps (summary/rationale/draft) will fail.")
    st.caption(
        "Known limitation (deviation-review/PROGRESS.md Phase 0): this account's OpenRouter workspace "
        "guardrail policy blocks every route except `analysis_drafting` -- an account dashboard "
        "setting, not a code bug. Retrieval summary and classification rationale will show a "
        "captured error; CAPA/narrative drafting is the one step confirmed to run live."
    )

    st.subheader("Deviations")
    deviation_ids = list_deviation_ids()
    picked = st.selectbox("Pick a deviation_id", deviation_ids)
    saved = list_saved_cases()
    if saved:
        st.caption("Already-run cases: " + ", ".join(saved))

if "active_deviation_id" not in st.session_state:
    st.session_state.active_deviation_id = None

st.header("1. Run the pipeline")
run_clicked = st.button(f"Run Retrieval → DataCheck → Classifier → CAPADrafter on {picked}")

if run_clicked:
    progress = st.progress(0.0, text="Running...")
    try:
        state = supervisor.run_case(picked, record_trace=True)
        progress.progress(1.0, text="Done")
        supervisor.save_case(state)
        st.session_state.active_deviation_id = picked
        st.success(f"Pipeline complete: {picked}")
    except Exception as e:
        st.error(f"Pipeline error: {e}")

deviation_id = st.session_state.active_deviation_id

if deviation_id:
    case_path = os.path.join(CASES_DIR, f"{deviation_id}.json")
    if not os.path.exists(case_path):
        st.error(f"No saved case for {deviation_id} yet -- run the pipeline above.")
        case = None
    else:
        with open(case_path) as f:
            case = json.load(f)

    if case:
        st.header(f"2. Evidence bundle -- {deviation_id}")
        approval = case.get("approval")
        status = case.get("status", "IN_PROGRESS" if not approval else approval["decision"])
        badge = {"FINAL": "🟢 FINAL", "REJECT": "🔴 REJECTED", "EDIT": "🟠 NEEDS EDIT"}.get(status, "🟡 IN_PROGRESS")
        st.markdown(f"**Status:** {badge}  |  **Domain:** {case.get('domain')}")

        violations = case.get("guardrail_violations") or []
        if violations:
            st.error("Guardrail violations (Rule 1/3, Section 1) -- must be resolved before APPROVE:\n\n"
                      + "\n".join(f"- {v}" for v in violations))

        with st.expander("Source evidence (Retrieval)", expanded=True):
            for item in case["bundle"]["evidence"]:
                if "source" in item:
                    src = item["source"]
                    st.markdown(f"**{src['record_id']}** — `{src['tool']}` ({src['file']})")
                    as_table(item["value"])
                else:
                    st.markdown(f"**Document search:** \"{item.get('query')}\"")
                    rows = [{
                        "record_id": r["source"]["record_id"],
                        "score": r["value"].get("score"),
                        "text": (r["value"].get("text") or "")[:200],
                    } for r in item.get("results", [])]
                    st.dataframe(rows, use_container_width=True)
            if case.get("summary"):
                st.info(f"Retrieval summary: {case['summary']}")
            elif case.get("summary_error"):
                st.caption(f"Retrieval summary unavailable: {case['summary_error'][:200]}")

        with st.expander("Deterministic findings (DataCheck)", expanded=True):
            flags = case.get("flags", {})
            st.dataframe([{"check": k, "result": v} for k, v in flags.items()], use_container_width=True)
            st.dataframe(
                [{"check": f["check"], "evidence": f["evidence_source"]["record_id"]} for f in case.get("findings", [])],
                use_container_width=True,
            )

        if case.get("replanned"):
            st.warning(f"Re-planned: {case.get('replan_reason')}")
            st.dataframe(case.get("affected_batches", []), use_container_width=True)

        with st.expander("Classification (Classifier)", expanded=True):
            decision = case.get("decision", {})
            impact_label = decision.get("classify_question", "Impact?")
            impact_value = decision.get("product_impact") if decision.get("product_impact") is not None else decision.get("reportable")
            st.dataframe([{
                "Severity": decision.get("severity"),
                impact_label: impact_value,
                "Approver role": decision.get("approver_role"),
                "Matched rule": decision.get("matched_rule"),
            }], use_container_width=True)
            if decision.get("rationale"):
                st.write(decision["rationale"])
            elif decision.get("rationale_error"):
                st.caption(f"Rationale unavailable: {decision['rationale_error'][:200]}")

        with st.expander("Draft narrative (CAPADrafter)", expanded=True):
            if case.get("draft"):
                st.markdown(case["draft"])
            else:
                st.caption(f"Draft unavailable: {case.get('draft_error', 'not run')}")

        with st.expander("Trace (model / tool / evidence / tokens / latency / cost)"):
            rows = trace_log.load_trace(deviation_id)
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("No trace recorded for this run.")

        st.header("3. Human approval gate")
        st.caption(
            f"Only APPROVE moves this case to FINAL. Required approver role for this "
            f"classification: **{case.get('decision', {}).get('approver_role', 'n/a')}**. Never a "
            "bare yes/no -- the reviewer names themselves, picks one of three explicit decisions, "
            "and may leave notes."
        )
        with st.form("deviation_review_approval_form"):
            approver = st.text_input("Approver name/ID")
            decision_choice = st.radio("Decision", ["APPROVE", "EDIT", "REJECT"], index=None)
            notes = st.text_area("Notes")
            approve_clicked = st.form_submit_button("Log review decision")

        if approve_clicked:
            if not approver:
                st.warning("An approver name is required to log a decision (Rule 3).")
            elif decision_choice is None:
                st.warning("Pick one of APPROVE / EDIT / REJECT.")
            else:
                try:
                    updated = hitl.approve_case(deviation_id, approver, decision_choice, notes)
                    st.success(f"Logged {decision_choice} by {approver}. "
                               f"Status is now {updated.get('status', decision_choice)}.")
                    st.rerun()
                except hitl.GuardrailViolation as e:
                    st.error(str(e))

        if approval:
            st.subheader("Approval record")
            st.dataframe([approval], use_container_width=True)
else:
    st.info("Pick a deviation_id in the sidebar and run the pipeline above.")
