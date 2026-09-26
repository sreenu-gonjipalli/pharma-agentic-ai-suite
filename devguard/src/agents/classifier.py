#!/usr/bin/env python3
"""Classifier sub-agent (CLAUDE.md Phase 4/9). Loads the domain pack's rules.yaml and applies
the first matching rule to DataCheck's flags -- the severity/impact decision itself is always
deterministic policy (never an LLM judgment call). Adding packs/clinical/ later (Phase 9)
requires no change to this file, only a new rules.yaml with matching flag names.

An optional one-paragraph rationale is drafted via the `triage_guardrail` route (prose only,
per Rule 2) -- best-effort, same degrade-gracefully approach as Retrieval's summary.

Runnable standalone: `python -m src.agents.classifier DEV-2026-0091`.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.retrieval import gather_evidence  # noqa: E402
from agents.data_check import run_data_check  # noqa: E402
from llm import call_route_with_retry, load_config  # noqa: E402

PACKS_DIR = Path(__file__).resolve().parent.parent.parent / "packs"


def load_pack_rules(domain: str) -> dict:
    with open(PACKS_DIR / domain / "rules.yaml") as f:
        return yaml.safe_load(f)


def classify(domain: str, flags: dict) -> dict:
    pack = load_pack_rules(domain)
    for rule in pack["rules"]:
        if all(flags.get(flag, False) for flag in rule["if_all"]):
            return {
                "matched_rule": rule["id"],
                "severity": rule["severity"],
                "product_impact": rule.get("product_impact"),
                "reportable": rule.get("reportable"),
                "approver_role": pack["approver_role"],
                "classify_question": pack["classify_question"],
            }
    default = pack["default"]
    return {
        "matched_rule": default["id"],
        "severity": default["severity"],
        "product_impact": default.get("product_impact"),
        "reportable": default.get("reportable"),
        "approver_role": pack["approver_role"],
        "classify_question": pack["classify_question"],
    }


def rationale(domain: str, flags: dict, decision: dict) -> tuple[str | None, str | None, dict]:
    prompt = (
        f"Domain: {domain}. Deterministic findings: {json.dumps(flags)}. Classification "
        f"decision (already made by rules, do not change it): {json.dumps(decision)}. "
        "Write one short paragraph explaining why this severity follows from these findings. "
        "Do not introduce any fact not listed above."
    )
    meta = {"route": "triage_guardrail", "model": load_config()["routes"]["triage_guardrail"]["model"], "route_result": None}
    try:
        content, result = call_route_with_retry("triage_guardrail", [{"role": "user", "content": prompt}])
        meta["route_result"] = result.model_dump()
        return content, None, meta
    except Exception as exc:
        return None, str(exc), meta


def main():
    parser = argparse.ArgumentParser(description="Classifier sub-agent (standalone).")
    parser.add_argument("deviation_id")
    parser.add_argument("--no-rationale", action="store_true")
    args = parser.parse_args()

    bundle = gather_evidence(args.deviation_id)
    checked = run_data_check(bundle)
    decision = classify(checked["domain"], checked["flags"])
    if not args.no_rationale:
        text, error, meta = rationale(checked["domain"], checked["flags"], decision)
        decision["rationale"] = text
        decision["rationale_error"] = error
        decision["rationale_meta"] = meta

    print(json.dumps({"deviation_id": args.deviation_id, "flags": checked["flags"], "decision": decision}, indent=2, default=str))


if __name__ == "__main__":
    main()
