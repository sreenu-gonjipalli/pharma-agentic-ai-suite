#!/usr/bin/env python3
"""Deviation Review -- Observability & Traceability page. Reads deviation-review's existing
logs/traces/*.jsonl via src/trace.py's load_trace() -- no new logging/reading logic.
"""
import glob
import os
import sys

import streamlit as st

PAGE_DIR = os.path.dirname(os.path.abspath(__file__))
UNIFIED_ROOT = os.path.dirname(PAGE_DIR)
DEVIATION_REVIEW_ROOT = os.path.normpath(os.path.join(UNIFIED_ROOT, "..", "deviation-review"))
sys.path.insert(0, DEVIATION_REVIEW_ROOT)

from src import trace as trace_log  # noqa: E402

st.title("Deviation Review -- Observability & Traceability")
st.caption(
    "Per-step trace (model, tool, evidence_id, tokens, latency, cost) -- metadata only, no "
    "prompt/response content (Rule 5). One logs/traces/<deviation_id>.jsonl file per run."
)

trace_dir = os.path.join(DEVIATION_REVIEW_ROOT, "logs", "traces")
ids = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(trace_dir, "*.jsonl")))

if not ids:
    st.info("No traces recorded yet -- run the Deviation Review pipeline with tracing enabled first.")
else:
    picked = st.selectbox("Deviation", ["-- all --"] + ids)

    if picked == "-- all --":
        all_rows = []
        for did in ids:
            for row in trace_log.load_trace(did):
                all_rows.append({"deviation_id": did, **row})
        st.dataframe(all_rows, use_container_width=True)

        total_cost = sum(float(r["cost_usd"]) for r in all_rows if r.get("cost_usd") not in ("", None))
        total_tokens = sum(int(r["total_tokens"]) for r in all_rows if r.get("total_tokens") not in ("", None))
        col1, col2, col3 = st.columns(3)
        col1.metric("Runs", len(ids))
        col2.metric("Total tokens (successful calls)", total_tokens)
        col3.metric("Total cost", f"${total_cost:.4f}")
    else:
        rows = trace_log.load_trace(picked)
        st.dataframe(rows, use_container_width=True)
