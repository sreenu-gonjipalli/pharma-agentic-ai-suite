#!/usr/bin/env python3
"""PV Evaluation page (CLAUDE.md Section 11). Runs eval/run_eval.py's existing metric
functions live and renders the result -- no metric logic duplicated here, only display.
"""
import os
import sys

import streamlit as st

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "eval"))

import run_eval  # noqa: E402
import llm_client  # noqa: E402

st.title("PV Evaluation")
st.caption(
    "Metrics per CLAUDE.md Section 11, computed against eval/fixtures.json (a 4-case "
    "hand-written sample -- not a validation dataset). See docs/evaluation.md for the full "
    "methodology."
)

st.subheader("1. Guardrail-violation catch rate (no LLM needed)")
if st.button("Run guardrail check"):
    report = run_eval.eval_guardrail_catch_rate()
    st.metric("Catch rate", f"{report['catch_rate']:.0%}", help="8 deliberately non-compliant payloads fed to hooks/advisory_check.py")
    st.dataframe(report["rows"], use_container_width=True)

st.subheader("2. Coding recall / seriousness agreement / duplicate recall / latency")
providers = llm_client.available_providers()
if not providers:
    st.error("No LLM provider configured -- set OPENROUTER_API_KEY or GROQ_API_KEY to run these metrics.")
else:
    st.caption(f"Will run app/pipeline.py end-to-end against each fixture using: {', '.join(providers)}.")
    if st.button("Run pipeline metrics (calls the live LLM provider, ~1 min)"):
        with st.spinner("Running pipeline against eval/fixtures.json..."):
            pipeline_report = run_eval.eval_pipeline_metrics()
            latency_report = run_eval.eval_latency(pipeline_report["case_ids"])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Coding recall", f"{pipeline_report['coding_recall']:.0%}" if pipeline_report["coding_recall"] is not None else "n/a")
        col2.metric("Seriousness agreement", f"{pipeline_report['seriousness_agreement']:.0%}" if pipeline_report["seriousness_agreement"] is not None else "n/a")
        col3.metric("Duplicate recall", f"{pipeline_report['duplicate_recall']:.0%}" if pipeline_report["duplicate_recall"] is not None else "n/a")
        col4.metric("Avg latency/case", f"{latency_report['avg_seconds']}s" if latency_report["avg_seconds"] else "n/a")

        st.dataframe(pipeline_report["per_case"], use_container_width=True)
