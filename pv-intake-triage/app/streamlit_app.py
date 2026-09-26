#!/usr/bin/env python3
"""Streamlit demo UI for the standalone PV pipeline (app/pipeline.py).

This is a local-only demonstration surface, per CLAUDE.md: it runs the same five-stage
pipeline (intake -> coding -> triage -> duplicate-check -> narrative), shows the reviewer an
evidence bundle (Section 8), and the ONLY way a case reaches FINAL is the human approval form
below calling case_store.approve_case directly -- never a bare yes/no control, and never
something the pipeline itself can call.
"""
import os
import sys
import json
import glob

import streamlit as st

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
sys.path.insert(0, APP_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, ".claude", "skills", "case-state-io", "scripts"))

import pipeline  # noqa: E402
import llm_client  # noqa: E402
import trace_logger  # noqa: E402
import case_store  # noqa: E402

CASES_DIR = case_store.CASES_DIR

st.set_page_config(page_title="PV Case Intake & Triage (Prototype)", layout="wide")

st.title("Agentic AI for Pharmacovigilance Case Intake & Triage")
st.caption(
    "Prototype only -- NOT a validated clinical/regulatory system, not connected to a live "
    "safety database, and not authorized to submit a real ICSR. Every clinical/regulatory "
    "output below is a draft pending mandatory human sign-off (CLAUDE.md)."
)

ADVISORY_TAG = pipeline.ADVISORY_TAG


def list_case_ids():
    paths = sorted(glob.glob(os.path.join(CASES_DIR, "*.json")), reverse=True)
    return [os.path.splitext(os.path.basename(p))[0] for p in paths]


with st.sidebar:
    st.subheader("LLM provider")
    providers = llm_client.available_providers()
    if providers:
        st.success("Configured: " + ", ".join(providers))
    else:
        st.error("No provider configured -- set OPENROUTER_API_KEY or GROQ_API_KEY and restart.")

    st.subheader("Cases")
    case_ids = list_case_ids()
    selected = st.selectbox("Open an existing case", ["-- new case --"] + case_ids)
    if st.button("Refresh"):
        st.rerun()

if "active_case_id" not in st.session_state:
    st.session_state.active_case_id = None if selected == "-- new case --" else selected
elif selected != "-- new case --":
    st.session_state.active_case_id = selected

st.header("1. Submit a raw adverse-event report")
with st.form("intake_form"):
    raw_text = st.text_area(
        "Raw report text (call-center transcript, email, literature excerpt)",
        height=160,
        placeholder="Example: Patient is a 54 year old female taking Metformin... developed severe "
        "nausea and was admitted to hospital overnight...",
    )
    run_clicked = st.form_submit_button("Run pipeline (intake -> coding -> triage -> duplicate -> narrative)")

if run_clicked:
    if not raw_text.strip():
        st.warning("Enter some report text first.")
    else:
        progress = st.progress(0.0, text="Starting...")
        steps = ["intake", "coding", "triage", "duplicate_check", "narrative"]

        def on_step(name, case):
            idx = steps.index(name) + 1
            progress.progress(idx / len(steps), text=f"Completed: {name}")

        try:
            case = pipeline.run_full_pipeline(raw_text, progress_cb=on_step)
            st.session_state.active_case_id = case["case_id"]
            st.success(f"Pipeline complete: {case['case_id']}")
        except pipeline.GuardrailViolation as e:
            st.error(f"Guardrail blocked this case: {e}")
        except RuntimeError as e:
            st.error(f"Pipeline error: {e}")

case_id = st.session_state.active_case_id

if case_id:
    try:
        case = case_store.load_case(case_id)
    except FileNotFoundError:
        st.error(f"Case {case_id} not found.")
        case = None

    if case:
        st.header(f"2. Evidence bundle -- {case_id}")
        status = case.get("status", "IN_PROGRESS")
        badge = {"FINAL": "🟢 FINAL", "REJECTED": "🔴 REJECTED", "IN_PROGRESS": "🟡 IN_PROGRESS"}.get(status, status)
        st.markdown(f"**Status:** {badge}")

        intake = case.get("intake", {})
        with st.expander("Source excerpt", expanded=True):
            st.text(intake.get("raw_report_text", "NOT REPORTED"))

        with st.expander("Extracted fields (pv-intake)", expanded=True):
            for key, val in intake.items():
                if key == "raw_report_text":
                    continue
                st.json({key: val})

        with st.expander("MedDRA coding candidates (pv-coding)", expanded=True):
            coding = case.get("coding", [])
            if not coding:
                st.info("Not run yet.")
            for block in coding:
                st.markdown(f"**Event:** {block.get('event')} -- `{block.get('status')}`")
                st.table(block.get("candidates", []))

        with st.expander("Seriousness / expectedness (pv-triage)", expanded=True):
            triage = case.get("triage", {})
            if not triage:
                st.info("Not run yet.")
            else:
                st.markdown(f"**Overall:** {triage.get('overall')} -- `{triage.get('status')}`")
                st.json(triage.get("criteria", {}))
                st.markdown(f"**Expectedness:** {triage.get('expectedness')}")
                st.markdown(f"**Rationale:** {triage.get('rationale')}")

        with st.expander("Duplicate check (pv-duplicate)", expanded=True):
            dup = case.get("duplicate_check", {})
            matches = dup.get("matches", [])
            if not matches:
                st.info("No candidate duplicates found.")
            else:
                st.table(matches)

        with st.expander("Draft narrative (pv-narrative)", expanded=True):
            narrative = case.get("narrative", {})
            if not narrative:
                st.info("Not run yet.")
            else:
                st.text(narrative.get("text", ""))

        with st.expander("History"):
            st.json(case.get("history", []))

        with st.expander("Traceability log for this case"):
            st.json(trace_logger.read_steps(case_id))

        st.header("3. Human approval gate")
        st.caption(
            "Only APPROVE moves this case to FINAL. This is never a bare yes/no -- the reviewer "
            "must name themselves, pick one of three explicit decisions, and may leave notes "
            "(CLAUDE.md Section 8)."
        )
        with st.form("approval_form"):
            reviewer = st.text_input("Reviewer name/ID")
            decision = st.radio("Decision", ["APPROVE", "EDIT", "REJECT"], index=None)
            notes = st.text_area("Notes (required context for EDIT/REJECT)")
            approve_clicked = st.form_submit_button("Log review decision")

        if approve_clicked:
            if not reviewer:
                st.warning("A reviewer name is required to log a decision.")
            elif decision is None:
                st.warning("Pick one of APPROVE / EDIT / REJECT.")
            else:
                updated = case_store.approve_case(case_id, reviewer, decision, notes)
                trace_logger.log_step(case_id, f"human-reviewer:{reviewer}", f"review_decision:{decision}",
                                       "human", "evidence bundle", decision, guardrail_result="PASS")
                st.success(f"Logged {decision} by {reviewer}. Case status is now {updated['status']}.")
                st.rerun()

        approvals = case.get("human_approval", [])
        if approvals:
            st.subheader("Approval history")
            st.table(approvals)
else:
    st.info("Run the pipeline above, or pick an existing case from the sidebar.")
