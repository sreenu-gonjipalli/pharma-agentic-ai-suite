#!/usr/bin/env python3
"""CAPADrafter sub-agent (CLAUDE.md Phase 4). Drafts the CAPA/deviation narrative from the
full assembled case (evidence + DataCheck flags + Classifier decision) using the domain pack's
prompt template and the `analysis_drafting` route -- prose only; every number in the draft must
already exist in the evidence passed in (Rule 2), and the draft must state the pending-approval
requirement (Rule 3).

Runnable standalone: `python -m src.agents.capa_drafter DEV-2026-0091`.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.retrieval import gather_evidence  # noqa: E402
from agents.data_check import run_data_check  # noqa: E402
from agents.classifier import classify  # noqa: E402
from llm import call_route_with_retry, load_config  # noqa: E402

PACKS_DIR = Path(__file__).resolve().parent.parent.parent / "packs"


def load_pack_prompt(domain: str) -> str:
    with open(PACKS_DIR / domain / "prompts.yaml") as f:
        return yaml.safe_load(f)["capa_system"]


def draft(bundle: dict, checked: dict, decision: dict) -> tuple[str | None, str | None, dict]:
    system = load_pack_prompt(bundle["domain"])
    case_json = json.dumps({
        "deviation": bundle["evidence"][0]["value"],
        "findings": checked["findings"],
        "classification": decision,
    }, default=str)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Case evidence and classification:\n{case_json}"},
    ]
    meta = {"route": "analysis_drafting", "model": load_config()["routes"]["analysis_drafting"]["model"], "route_result": None}
    try:
        content, result = call_route_with_retry("analysis_drafting", messages)
        meta["route_result"] = result.model_dump()
        return content, None, meta
    except Exception as exc:
        return None, str(exc), meta


def main():
    parser = argparse.ArgumentParser(description="CAPADrafter sub-agent (standalone).")
    parser.add_argument("deviation_id")
    args = parser.parse_args()

    bundle = gather_evidence(args.deviation_id)
    checked = run_data_check(bundle)
    decision = classify(checked["domain"], checked["flags"])
    text, error, meta = draft(bundle, checked, decision)

    print(json.dumps({"deviation_id": args.deviation_id, "draft": text, "draft_error": error, "draft_meta": meta}, indent=2, default=str))


if __name__ == "__main__":
    main()
