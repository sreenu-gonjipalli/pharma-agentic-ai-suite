#!/usr/bin/env python3
"""Search cases/ for likely duplicates of a given case, by simple field overlap."""
import argparse
import glob
import json
import os

CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "cases")
CASES_DIR = os.path.normpath(CASES_DIR)
THRESHOLD = 0.4


def flat_text(case: dict) -> str:
    intake = case.get("intake", {})
    parts = [
        str(intake.get("patient", "")),
        str(intake.get("drugs", "")),
        str(intake.get("events", "")),
        str(intake.get("dates", "")),
    ]
    return " ".join(parts).lower()


def similarity(a: str, b: str) -> float:
    tokens_a, tokens_b = set(a.split()), set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return round(len(tokens_a & tokens_b) / len(tokens_a | tokens_b), 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    args = parser.parse_args()

    target_path = os.path.join(CASES_DIR, f"{args.case_id}.json")
    if not os.path.exists(target_path):
        print(json.dumps({"matches": [], "error": f"case {args.case_id} not found"}, indent=2))
        return

    with open(target_path) as f:
        target = json.load(f)
    target_text = flat_text(target)

    matches = []
    for path in glob.glob(os.path.join(CASES_DIR, "*.json")):
        other_id = os.path.splitext(os.path.basename(path))[0]
        if other_id == args.case_id:
            continue
        with open(path) as f:
            other = json.load(f)
        sim = similarity(target_text, flat_text(other))
        if sim >= THRESHOLD:
            matches.append({
                "case_id": other_id,
                "similarity": sim,
                "status": "SUGGESTED — PENDING HUMAN REVIEW",
            })

    matches.sort(key=lambda m: m["similarity"], reverse=True)
    print(json.dumps({"matches": matches}, indent=2))


if __name__ == "__main__":
    main()
