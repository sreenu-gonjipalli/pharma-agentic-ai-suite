#!/usr/bin/env python3
"""PV Observability & Traceability page (CLAUDE.md Section 7). Reads logs/traceability.jsonl
via the existing trace_logger.read_steps() -- no new logging/reading logic, only display.
"""
import os
import sys

import streamlit as st

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

import trace_logger  # noqa: E402

st.title("PV Observability & Traceability")
st.caption(
    "Append-only audit trail (CLAUDE.md Section 7): one row per pipeline step -- agent, "
    "action, tool, redacted input/output, guardrail result, timestamp. Metadata only, never "
    "the full raw report text (Section 5)."
)

steps = trace_logger.read_steps()
if not steps:
    st.info("No traceability entries yet -- run the PV pipeline at least once.")
else:
    case_ids = sorted({s["case_id"] for s in steps}, reverse=True)
    picked = st.selectbox("Filter by case_id", ["-- all cases --"] + case_ids)
    rows = steps if picked == "-- all cases --" else [s for s in steps if s["case_id"] == picked]
    st.dataframe(rows, use_container_width=True)
    st.caption(f"{len(rows)} of {len(steps)} total steps shown.")
