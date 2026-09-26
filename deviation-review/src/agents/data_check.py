#!/usr/bin/env python3
"""DataCheck sub-agent (CLAUDE.md Phase 4). Pure Python, no LLM (Rule 2: numbers from code) --
runs the deterministic checks in src/checks/ against a Retrieval evidence bundle and returns
boolean flags + detailed findings, each traceable to its source evidence item.

Runnable standalone: `python -m src.agents.data_check DEV-2026-0091`.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.retrieval import gather_evidence  # noqa: E402
from checks.excursion import excursion_events  # noqa: E402
from checks.service import service_breach  # noqa: E402
from checks.visit import visit_window_breach  # noqa: E402


def _find(bundle: dict, server: str, tool: str):
    for item in bundle["evidence"]:
        if item["source"]["server"] == server and item["source"]["tool"] == tool:
            return item
    return None


def run_data_check(bundle: dict) -> dict:
    domain = bundle["domain"]
    deviation = bundle["evidence"][0]["value"]
    findings = []
    flags = {}

    if domain == "manufacturing":
        trace_item = _find(bundle, "equipment", "get_temperature_trace")
        events = excursion_events(trace_item["value"])
        above = [e for e in events if e["direction"] == "above"]
        flags["excursion_above_spec"] = bool(above)
        findings.append({
            "check": "excursion_above_spec", "result": above,
            "evidence_source": trace_item["source"],
        })

        maint_item = _find(bundle, "equipment", "get_maintenance_history")
        breach = service_breach(maint_item["value"], deviation["date"])
        flags["service_breach"] = bool(breach["breach"])
        findings.append({
            "check": "service_breach", "result": breach,
            "evidence_source": maint_item["source"],
        })

        lab_item = _find(bundle, "plantdata", "get_lab_results")
        failing = [r for r in lab_item["value"] if r["pass_fail"] == "fail"]
        flags["lab_fail"] = bool(failing)
        findings.append({
            "check": "lab_fail", "result": failing,
            "evidence_source": lab_item["source"],
        })

    elif domain == "clinical":
        visits_item = _find(bundle, "plantdata", "get_subject_visits")
        breaches = []
        for visit in visits_item["value"]:
            result = visit_window_breach(visit["planned_date"], visit["visit_window_days"], visit["actual_date"])
            result["visit_name"] = visit["visit_name"]
            if result["breach"]:
                breaches.append(result)
        flags["visit_window_breach"] = bool(breaches)
        findings.append({
            "check": "visit_window_breach", "result": breaches,
            "evidence_source": visits_item["source"],
        })

    else:
        raise ValueError(f"Unknown domain '{domain}'")

    return {"deviation_id": bundle["deviation_id"], "domain": domain, "flags": flags, "findings": findings}


def main():
    parser = argparse.ArgumentParser(description="DataCheck sub-agent (standalone).")
    parser.add_argument("deviation_id")
    args = parser.parse_args()
    bundle = gather_evidence(args.deviation_id)
    print(json.dumps(run_data_check(bundle), indent=2, default=str))


if __name__ == "__main__":
    main()
