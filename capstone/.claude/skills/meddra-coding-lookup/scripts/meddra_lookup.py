#!/usr/bin/env python3
"""Look up MedDRA-style candidate terms for a free-text event description.

Uses a small local sample terminology file (NOT the real MedDRA dictionary — this is a capstone
prototype). Matching is deliberately simple (token overlap + substring) and transparent, so a
reviewer can see exactly why a candidate was suggested.
"""
import argparse
import json
import os

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "meddra_sample.json")


def load_terms():
    with open(DATA_PATH) as f:
        return json.load(f)


def score(text: str, term_entry: dict) -> float:
    text_l = text.lower()
    candidates = [term_entry["pt"]] + term_entry["llt"]
    best = 0.0
    for cand in candidates:
        cand_l = cand.lower()
        if cand_l in text_l or text_l in cand_l:
            best = max(best, 0.9)
            continue
        text_tokens = set(text_l.split())
        cand_tokens = set(cand_l.split())
        if not cand_tokens:
            continue
        overlap = len(text_tokens & cand_tokens) / len(cand_tokens)
        best = max(best, overlap * 0.7)
    return round(best, 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="Free-text event description")
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()

    terms = load_terms()
    scored = [(score(args.text, t), t) for t in terms]
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for s, t in scored[: args.top]:
        results.append({
            "term": t["pt"] if s > 0 else "NO MATCH FOUND",
            "soc": t["soc"] if s > 0 else None,
            "confidence": s,
            "source_span": args.text,
        })
    if not any(r["confidence"] > 0 for r in results):
        results = [{"term": "NO MATCH FOUND", "soc": None, "confidence": 0.0, "source_span": args.text}]

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
