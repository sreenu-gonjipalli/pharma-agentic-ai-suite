#!/usr/bin/env python3
"""Deviation Review -- Evaluation page. Calls deviation-review's existing eval/run_eval.py and
eval/redteam.py functions live -- no metric logic duplicated here, only display.
"""
import os
import sys

import streamlit as st

PAGE_DIR = os.path.dirname(os.path.abspath(__file__))
UNIFIED_ROOT = os.path.dirname(PAGE_DIR)
DEVIATION_REVIEW_ROOT = os.path.normpath(os.path.join(UNIFIED_ROOT, "..", "deviation-review"))
sys.path.insert(0, DEVIATION_REVIEW_ROOT)
sys.path.insert(0, os.path.join(DEVIATION_REVIEW_ROOT, "src"))
sys.path.insert(0, os.path.join(DEVIATION_REVIEW_ROOT, "eval"))

from eval import run_eval  # noqa: E402

st.title("Deviation Review -- Evaluation")
st.caption(
    "Golden-set accuracy, live citation-rate, and redteam refusal-rate, per Deviation Review's own "
    "PROGRESS.md Phase 10. All 28 real deviations in data/deviations.csv are used for the "
    "(free, deterministic) accuracy check; citation-rate and refusal-rate cost real "
    "OpenRouter calls, so they only run on a small sample when you click below."
)

st.subheader("1. Classification accuracy (deterministic, no LLM cost)")
if st.button("Run accuracy check"):
    golden = run_eval.load_golden()
    accuracy = run_eval.score_accuracy(golden)
    st.metric("Accuracy", f"{accuracy['accuracy']:.0%}", help=f"{accuracy['correct']}/{accuracy['total']} cases match the golden set")
    if accuracy["mismatches"]:
        st.warning("Mismatches: " + ", ".join(accuracy["mismatches"]))

st.subheader("2. Citation rate + redteam refusal rate (live OpenRouter calls)")
sample_size = st.slider("Sample size for citation-rate", min_value=2, max_value=10, value=4)
if st.button(f"Run live eval (~{sample_size} draft calls + 5 redteam prompts)"):
    golden = run_eval.load_golden()
    seen_rules, sample_ids = set(), []
    for case in golden:
        if case["expected_matched_rule"] not in seen_rules:
            seen_rules.add(case["expected_matched_rule"])
            sample_ids.append(case["deviation_id"])
        if len(sample_ids) >= sample_size:
            break

    with st.spinner("Drafting narratives for the sample..."):
        citation = run_eval.score_citation_rate(golden, sample_ids)
    with st.spinner("Running redteam prompts..."):
        from eval import redteam
        redteam_result = redteam.run_redteam()

    col1, col2 = st.columns(2)
    col1.metric("Overall citation rate", f"{citation['overall_citation_rate']:.0%}" if citation["overall_citation_rate"] is not None else "n/a")
    col2.metric("Refusal rate", f"{redteam_result['refusal_rate']:.0%}" if redteam_result["refusal_rate"] is not None else "n/a")

    st.markdown("**Citation rate per case**")
    st.dataframe(citation["per_case"], use_container_width=True)

    st.markdown("**Redteam prompt results**")
    st.dataframe(redteam_result["results"], use_container_width=True)

    st.caption(
        "eval_judge (gpt-6-astra) cross-check is not shown here -- this account's OpenRouter "
        "guardrail policy blocks that route (same limitation noted since deviation-review's Phase 0)."
    )
