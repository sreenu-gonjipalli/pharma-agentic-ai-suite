#!/usr/bin/env python3
"""Unified shell (Phase 3): one Streamlit process, sidebar switch between the two separate
projects this session built -- ../capstone (PV Intake & Triage) and ../devguard (shown here
under its user-facing name "Deviation Review" -- the underlying project/folder is still called
devguard, only the UI label changed). Neither project's code is copied or forked here -- this
file only points `st.navigation` at each project's page scripts: capstone's own
app/{streamlit_app,eval_page,trace_page}.py (unmodified, native to that project), and this
folder's own pages/deviation_review_*.py (devguard has no native UI of its own, so its pages
live here, same as Phase 1/2 established).

Pages are grouped under two sidebar section headers -- still 6 distinct top-level pages, just
organized rather than a flat list.
"""
import os

import streamlit as st

UNIFIED_ROOT = os.path.dirname(os.path.abspath(__file__))
CAPSTONE_APP_DIR = os.path.normpath(os.path.join(UNIFIED_ROOT, "..", "capstone", "app"))
PAGES_DIR = os.path.join(UNIFIED_ROOT, "pages")

st.set_page_config(page_title="PV / Deviation Review Suite", layout="wide")

pg = st.navigation({
    "PV Intake & Triage": [
        st.Page(os.path.join(CAPSTONE_APP_DIR, "streamlit_app.py"), title="Case Pipeline", icon="🧪", url_path="pv-pipeline"),
        st.Page(os.path.join(CAPSTONE_APP_DIR, "eval_page.py"), title="Evaluation", icon="📊", url_path="pv-evaluation"),
        st.Page(os.path.join(CAPSTONE_APP_DIR, "trace_page.py"), title="Observability & Traceability", icon="🧾", url_path="pv-trace"),
    ],
    "Deviation Review": [
        st.Page(os.path.join(PAGES_DIR, "deviation_review_pipeline.py"), title="Case Pipeline", icon="🛡️", url_path="dr-pipeline"),
        st.Page(os.path.join(PAGES_DIR, "deviation_review_evaluation.py"), title="Evaluation", icon="📊", url_path="dr-evaluation"),
        st.Page(os.path.join(PAGES_DIR, "deviation_review_trace.py"), title="Observability & Traceability", icon="🧾", url_path="dr-trace"),
    ],
})
pg.run()
