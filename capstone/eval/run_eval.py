#!/usr/bin/env python3
"""Evaluation harness for CLAUDE.md Section 11.

Metrics computed, against eval/fixtures.json (small hand-labeled sample -- not a substitute
for a real validation dataset, this is a capstone prototype):
  1. MedDRA coding precision/recall  -- does the correct term appear in the top-3 candidates.
  2. Seriousness-flag agreement      -- does pv-triage's overall label match the expected one.
  3. Duplicate-detection precision/recall -- does the near-duplicate fixture get flagged.
  4. Guardrail-violation catch rate on adversarial input -- feed hooks/advisory_check.py a set
     of deliberately non-compliant payloads and confirm every one is rejected.
  5. End-to-end latency per case -- from logs/traceability.jsonl timestamps.

Requires a working LLM provider (OPENROUTER_API_KEY or GROQ_API_KEY) for metrics 1-3 and 5,
since intake/triage/narrative go through app/pipeline.py. Metric 4 needs no LLM and no network.
Run: python3 eval/run_eval.py
"""
import json
import os
import sys
from datetime import datetime

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(EVAL_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "hooks"))

import pipeline  # noqa: E402
import advisory_check  # noqa: E402
import trace_logger  # noqa: E402

FIXTURES_PATH = os.path.join(EVAL_DIR, "fixtures.json")


def eval_pipeline_metrics():
    with open(FIXTURES_PATH) as f:
        fixtures = json.load(f)

    coding_hits, coding_total = 0, 0
    triage_agree, triage_total = 0, 0
    case_id_by_note = {}
    per_case_rows = []

    for fx in fixtures:
        try:
            case = pipeline.run_full_pipeline(fx["raw_text"])
        except Exception as e:
            per_case_rows.append({"case_note": fx["case_note"], "error": str(e)})
            continue

        case_id_by_note[fx["case_note"]] = case["case_id"]

        found_terms = {
            c["term"] for block in case.get("coding", []) for c in block.get("candidates", [])
        }
        for expected in fx.get("expected_event_terms", []):
            coding_total += 1
            if expected in found_terms:
                coding_hits += 1

        triage_total += 1
        actual_overall = case.get("triage", {}).get("overall")
        if actual_overall == fx.get("expected_overall_seriousness"):
            triage_agree += 1

        per_case_rows.append({
            "case_note": fx["case_note"],
            "case_id": case["case_id"],
            "coding_terms_found": sorted(found_terms),
            "triage_overall": actual_overall,
        })

    # Duplicate-detection precision/recall: any fixture naming expected_duplicate_of_note
    # should have that fixture's case_id among its duplicate_check matches.
    dup_hits, dup_total = 0, 0
    for fx in fixtures:
        target_note = fx.get("expected_duplicate_of_note")
        if not target_note or fx["case_note"] not in case_id_by_note:
            continue
        dup_total += 1
        case = pipeline.case_store.load_case(case_id_by_note[fx["case_note"]])
        matched_ids = {m["case_id"] for m in case.get("duplicate_check", {}).get("matches", [])}
        if case_id_by_note.get(target_note) in matched_ids:
            dup_hits += 1

    return {
        "coding_recall": round(coding_hits / coding_total, 2) if coding_total else None,
        "seriousness_agreement": round(triage_agree / triage_total, 2) if triage_total else None,
        "duplicate_recall": round(dup_hits / dup_total, 2) if dup_total else None,
        "per_case": per_case_rows,
        "case_ids": list(case_id_by_note.values()),
    }


# Deliberately non-compliant payloads a real pv-coding/pv-triage/pv-intake/pv-narrative output
# must never look like -- each should be caught by hooks/advisory_check.py.
ADVERSARIAL_PAYLOADS = [
    ("coding", "missing advisory tag", [{"candidates": [{"term": "Nausea", "confidence": 0.9, "source_span": "x"}]}]),
    ("coding", "missing source_span", [{"status": advisory_check.ADVISORY_TAG, "candidates": [{"term": "Nausea", "confidence": 0.9}]}]),
    ("coding", "missing confidence", [{"status": advisory_check.ADVISORY_TAG, "candidates": [{"term": "Nausea", "source_span": "x"}]}]),
    ("triage", "missing advisory tag", {"overall": "SERIOUS", "criteria": {"death": {"result": "SUPPORTED", "source_span": "x"}}, "rationale": "r"}),
    ("triage", "missing rationale", {"status": advisory_check.ADVISORY_TAG, "overall": "SERIOUS", "criteria": {"death": {"result": "SUPPORTED", "source_span": "x"}}}),
    ("triage", "missing source_span", {"status": advisory_check.ADVISORY_TAG, "overall": "SERIOUS", "criteria": {"death": {"result": "SUPPORTED"}}, "rationale": "r"}),
    ("intake", "fabricated value with no source_span", {"patient": {"value": "45 year old male", "source_span": None}}),
    ("narrative", "missing mandated disclaimer", {"text": "Patient took drug X and felt fine."}),
]


def eval_guardrail_catch_rate():
    validators = {
        "coding": advisory_check.validate_coding,
        "triage": advisory_check.validate_triage,
        "intake": advisory_check.validate_intake,
        "narrative": advisory_check.validate_narrative,
    }
    caught = 0
    rows = []
    for section, label, payload in ADVERSARIAL_PAYLOADS:
        violations = validators[section](payload)
        ok = len(violations) > 0
        caught += 1 if ok else 0
        rows.append({"section": section, "case": label, "caught": ok, "violations": violations})
    return {"catch_rate": round(caught / len(ADVERSARIAL_PAYLOADS), 2), "rows": rows}


def eval_latency(case_ids):
    latencies = []
    for cid in case_ids:
        steps = trace_logger.read_steps(cid)
        if len(steps) < 2:
            continue
        times = [datetime.fromisoformat(s["timestamp"]) for s in steps]
        latencies.append((max(times) - min(times)).total_seconds())
    if not latencies:
        return {"avg_seconds": None, "n": 0}
    return {"avg_seconds": round(sum(latencies) / len(latencies), 2), "n": len(latencies)}


def main():
    print("== Guardrail-violation catch rate (adversarial input, no LLM/network needed) ==")
    guardrail_report = eval_guardrail_catch_rate()
    print(json.dumps(guardrail_report, indent=2))

    if not (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GROQ_API_KEY")):
        print("\nNo LLM provider configured -- skipping coding/seriousness/duplicate/latency "
              "metrics (they require app/pipeline.py to run end-to-end).")
        return

    print("\n== Running pipeline against eval/fixtures.json ==")
    pipeline_report = eval_pipeline_metrics()
    print(json.dumps(pipeline_report, indent=2))

    print("\n== End-to-end latency per case ==")
    latency_report = eval_latency(pipeline_report["case_ids"])
    print(json.dumps(latency_report, indent=2))

    full_report = {
        "guardrail": guardrail_report,
        "pipeline": pipeline_report,
        "latency": latency_report,
    }
    out_path = os.path.join(EVAL_DIR, "results.json")
    with open(out_path, "w") as f:
        json.dump(full_report, f, indent=2)
    print(f"\nFull report written to {out_path}")


if __name__ == "__main__":
    main()
