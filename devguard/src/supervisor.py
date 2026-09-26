#!/usr/bin/env python3
"""Supervisor (CLAUDE.md Phase 5). Plans -> delegates to sub-agents -> re-plans on new
evidence -> assembles the final case state. The state object threads through every step so
later phases (guardrails, HITL, trace) can act on one consistent record.

Re-plan trigger (this phase's "done when"): a `service_breach` finding (stale calibration) adds
an `affected_batch_survey` step that was not in the initial plan, surveying every other batch
processed on the same equipment during the overdue window -- each checked against its own lab
evidence, never assumed impacted just because it shares equipment (Phase 1's fixed-case design).

Runnable standalone: `python -m src.supervisor DEV-2026-0091`.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp_servers"))

from agents.retrieval import gather_evidence, summarize  # noqa: E402
from agents.data_check import run_data_check  # noqa: E402
from agents.classifier import classify, rationale  # noqa: E402
from agents.capa_drafter import draft  # noqa: E402
import common  # noqa: E402
import trace as trace_log  # noqa: E402
import guardrails  # noqa: E402

INITIAL_PLAN = ["retrieval", "data_check", "classify", "capa_draft"]


def affected_batch_survey(equipment_id: str, window_start: str, window_end: str, exclude_batch: str) -> list[dict]:
    """Every other batch processed on `equipment_id` between `window_start` (the missed
    service due date) and `window_end` (this deviation's process date), each with its own lab
    result checked -- sharing equipment during a service breach is not itself product impact."""
    trace_rows = common.read_csv("equipment_traces.csv")
    batch_ids = set()
    for row in trace_rows:
        if row["equipment_id"] != equipment_id:
            continue
        process_date = row["timestamp"][:10]
        if window_start <= process_date <= window_end and row["batch_id"] != exclude_batch:
            batch_ids.add(row["batch_id"])

    lab_rows = common.read_csv("lab_results.csv")
    survey = []
    for batch_id in sorted(batch_ids):
        failing = [r for r in lab_rows if r["batch_id"] == batch_id and r["pass_fail"] == "fail"]
        survey.append({"batch_id": batch_id, "lab_fail": bool(failing), "failing_tests": failing})
    return survey


def run_case(deviation_id: str, record_trace: bool = False) -> dict:
    state = {"deviation_id": deviation_id, "initial_plan": list(INITIAL_PLAN), "plan": list(INITIAL_PLAN), "replanned": False}
    if record_trace:
        trace_log.reset_trace(deviation_id)

    state["bundle"] = gather_evidence(deviation_id)
    state["domain"] = state["bundle"]["domain"]
    if record_trace:
        for item in state["bundle"]["evidence"]:
            if "source" in item:
                sources = [item["source"]]
            else:  # doc_server.search_documents returns {"query", "results": [{"value","source"},...]}
                sources = [r["source"] for r in item.get("results", [])]
            for src in sources:
                trace_log.record_step(deviation_id, "retrieval", "retrieval", tool=f"{src['server']}.{src['tool']}", evidence_id=src["record_id"])

    summary_text, summary_error, summary_meta = summarize(state["bundle"])
    state["summary"] = summary_text
    state["summary_error"] = summary_error
    if record_trace:
        trace_log.record_step(deviation_id, "retrieval_summary", "retrieval", model=summary_meta["model"],
                               route_result=summary_meta["route_result"])

    checked = run_data_check(state["bundle"])
    state["flags"] = checked["flags"]
    state["findings"] = checked["findings"]
    if record_trace:
        for f in checked["findings"]:
            trace_log.record_step(deviation_id, "data_check", "data_check", tool=f"src.checks.{f['check']}",
                                   evidence_id=f["evidence_source"]["record_id"])

    if state["flags"].get("service_breach") and "affected_batch_survey" not in state["plan"]:
        idx = state["plan"].index("data_check") if "data_check" in state["plan"] else 1
        state["plan"].insert(idx + 1, "affected_batch_survey")
        state["replanned"] = True
        state["replan_reason"] = (
            "service_breach=True (stale calibration) -- surveying other batches on the same "
            "equipment during the overdue window before classifying"
        )
        breach_finding = next(f for f in checked["findings"] if f["check"] == "service_breach")
        equipment_id = breach_finding["evidence_source"]["record_id"]
        window_start = breach_finding["result"]["next_due_date"]
        window_end = state["bundle"]["evidence"][0]["value"]["date"]
        primary_batch = state["bundle"]["evidence"][0]["value"].get("batch_id", "")
        state["affected_batches"] = affected_batch_survey(equipment_id, window_start, window_end, primary_batch)
        if record_trace:
            trace_log.record_step(deviation_id, "affected_batch_survey", "supervisor",
                                   tool="equipment_traces.csv+lab_results.csv", evidence_id=equipment_id)

    state["decision"] = classify(state["domain"], state["flags"])
    rationale_text, rationale_error, rationale_meta = rationale(state["domain"], state["flags"], state["decision"])
    state["decision"]["rationale"] = rationale_text
    state["decision"]["rationale_error"] = rationale_error
    if record_trace:
        trace_log.record_step(deviation_id, "classify", "classifier", tool=f"packs.{state['domain']}.rules",
                               evidence_id=state["decision"]["matched_rule"], model=rationale_meta["model"],
                               route_result=rationale_meta["route_result"])

    draft_text, draft_error, draft_meta = draft(state["bundle"], checked, state["decision"])
    state["draft"] = draft_text
    state["draft_error"] = draft_error
    if record_trace:
        trace_log.record_step(deviation_id, "capa_draft", "capadrafter", model=draft_meta["model"],
                               route_result=draft_meta["route_result"])

    # In-process guardrail check (Phase 6): the .claude/hooks/ PostToolUse hook only fires for
    # Claude Code tool calls, not for a direct Python import (CLI, or the unified Streamlit
    # app) -- so run the same validator here too, mirroring the capstone sibling project's
    # app/pipeline.py doing its own advisory_check calls rather than relying on hooks alone.
    state["guardrail_violations"] = guardrails.validate_case(state)

    return state


def save_case(state: dict) -> Path:
    """Persist the assembled case under logs/cases/ so the PostToolUse guardrail hook (Phase 6)
    can re-read and validate it after a Bash run -- the same re-read-from-disk pattern the
    capstone sibling project uses for its cases/ store."""
    out_dir = Path(__file__).resolve().parent.parent / "logs" / "cases"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{state['deviation_id']}.json"
    with open(path, "w") as f:
        json.dump(state, f, indent=2, default=str)
    return path


def main():
    parser = argparse.ArgumentParser(description="Supervisor (standalone).")
    parser.add_argument("deviation_id")
    parser.add_argument("--save", action="store_true", help="persist the case to logs/cases/<id>.json")
    parser.add_argument("--trace", action="store_true", help="record a step-by-step trace to logs/traces/<id>.jsonl")
    args = parser.parse_args()
    state = run_case(args.deviation_id, record_trace=args.trace)
    if args.save:
        state["_saved_to"] = str(save_case(state))
    print(json.dumps(state, indent=2, default=str))


if __name__ == "__main__":
    main()
