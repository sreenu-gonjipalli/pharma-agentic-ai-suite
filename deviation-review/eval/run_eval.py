#!/usr/bin/env python3
"""Evaluation harness (CLAUDE.md Phase 10). Reports the 3 metrics this phase's plan calls for:

  accuracy       -- fraction of eval/golden_set.json cases where the (deterministic) Classifier
                     decision matches the recorded expected decision. Cheap: no LLM calls.
  citation_rate  -- for a live-drafted sample of cases, the fraction of that case's evidence
                     record_ids that actually appear in the CAPADrafter/protocol-deviation draft
                     text. Sampled (not all 28) because this is the metric that costs real
                     OpenRouter calls.
  refusal_rate   -- from eval/redteam.py: fraction of adversarial prompts (asking the drafter to
                     make an out-of-scope release/rejection or causality call) that the model
                     correctly declines/defers rather than complying with.

An `eval_judge` (gpt-6-astra) cross-check of citation quality is attempted per CLAUDE.md
Section 5's model table and reported if it succeeds; this account's OpenRouter guardrail policy
blocks that route (same blocker documented since Phase 0), so it degrades to "unavailable"
rather than failing the whole eval run.
"""
import argparse
import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.retrieval import gather_evidence  # noqa: E402
from agents.data_check import run_data_check  # noqa: E402
from agents.classifier import classify  # noqa: E402
from agents.capa_drafter import draft  # noqa: E402
from llm import call_route_with_retry  # noqa: E402
import redteam  # noqa: E402

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_set.json"


def load_golden() -> list[dict]:
    with open(GOLDEN_PATH) as f:
        return json.load(f)


def score_accuracy(golden: list[dict]) -> dict:
    total = len(golden)
    correct = 0
    mismatches = []
    for case in golden:
        bundle = gather_evidence(case["deviation_id"])
        checked = run_data_check(bundle)
        decision = classify(checked["domain"], checked["flags"])
        matches = (
            checked["domain"] == case["expected_domain"]
            and checked["flags"] == case["expected_flags"]
            and decision["matched_rule"] == case["expected_matched_rule"]
            and decision["severity"] == case["expected_severity"]
            and decision.get("product_impact") == case["expected_product_impact"]
            and decision.get("reportable") == case["expected_reportable"]
        )
        if matches:
            correct += 1
        else:
            mismatches.append(case["deviation_id"])
    return {"total": total, "correct": correct, "accuracy": round(correct / total, 4), "mismatches": mismatches}


def score_citation_rate(golden: list[dict], sample_ids: list[str]) -> dict:
    per_case = []
    for case in golden:
        if case["deviation_id"] not in sample_ids:
            continue
        bundle = gather_evidence(case["deviation_id"])
        checked = run_data_check(bundle)
        decision = classify(checked["domain"], checked["flags"])
        text, error, _meta = draft(bundle, checked, decision)
        record_ids = case["evidence_record_ids"]
        if not text:
            per_case.append({"deviation_id": case["deviation_id"], "citation_rate": None, "error": error})
            continue
        cited = sum(1 for rid in record_ids if rid in text)
        per_case.append({
            "deviation_id": case["deviation_id"],
            "evidence_count": len(record_ids),
            "cited_count": cited,
            "citation_rate": round(cited / len(record_ids), 4) if record_ids else None,
        })
    valid = [c["citation_rate"] for c in per_case if c["citation_rate"] is not None]
    overall = round(sum(valid) / len(valid), 4) if valid else None
    return {"per_case": per_case, "overall_citation_rate": overall}


def try_eval_judge(golden: list[dict], sample_ids: list[str]) -> dict:
    case = next((c for c in golden if c["deviation_id"] == sample_ids[0]), None)
    if not case:
        return {"available": False, "error": "no sample case"}
    prompt = (
        f"Rate 1-5 how well-cited this deviation classification is (placeholder eval_judge check): "
        f"{json.dumps(case)}"
    )
    try:
        content, _ = call_route_with_retry("eval_judge", [{"role": "user", "content": prompt}])
        return {"available": True, "response": content}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description="DevGuard evaluation harness.")
    parser.add_argument("--sample", type=int, default=6, help="how many cases to run live citation-rate on")
    args = parser.parse_args()

    golden = load_golden()

    accuracy = score_accuracy(golden)

    seen_rules = set()
    sample_ids = []
    for case in golden:
        if case["expected_matched_rule"] not in seen_rules:
            seen_rules.add(case["expected_matched_rule"])
            sample_ids.append(case["deviation_id"])
        if len(sample_ids) >= args.sample:
            break

    citation = score_citation_rate(golden, sample_ids)
    redteam_result = redteam.run_redteam()
    eval_judge = try_eval_judge(golden, sample_ids)

    report = {
        "accuracy": accuracy,
        "citation_rate": citation,
        "refusal_rate": redteam_result,
        "eval_judge_cross_check": eval_judge,
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
