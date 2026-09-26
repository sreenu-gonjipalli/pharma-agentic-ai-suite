#!/usr/bin/env python3
"""Human-in-the-loop approval gate (CLAUDE.md Phase 7, Rule 3: "Human approval is blocking. No
final output without a recorded approver identity + timestamp.")

This is the *only* code path that can write to logs/approved/ -- no other module in this repo
produces a finalized deliverable. `approve_case` always records the approver/decision/timestamp
into the working case (logs/cases/<id>.json); it only additionally writes the finalized copy to
logs/approved/<id>.json when the decision is APPROVE. EDIT/REJECT are recorded for audit but
never finalize anything, so finalisation stays blocked until an explicit APPROVE.

Runnable standalone: `python3 -m src.hitl DEV-2026-0091 --approver "J. Alvarez" --decision APPROVE`.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

CASES_DIR = Path(__file__).resolve().parent.parent / "logs" / "cases"
APPROVED_DIR = Path(__file__).resolve().parent.parent / "logs" / "approved"

DECISIONS = ("APPROVE", "EDIT", "REJECT")


class GuardrailViolation(RuntimeError):
    """Raised on an attempted APPROVE of a case that still carries unresolved
    src/guardrails.py violations -- defense in depth alongside the .claude/hooks/ PostToolUse
    hook, which only fires for Claude Code tool calls, not a direct Python/Streamlit call."""


def load_case(deviation_id: str) -> dict:
    path = CASES_DIR / f"{deviation_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No saved case at {path} -- run `python3 -m src.supervisor {deviation_id} --save` first."
        )
    with open(path) as f:
        return json.load(f)


def approve_case(deviation_id: str, approver: str, decision: str, notes: str = "") -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}, got {decision!r}")
    if not approver:
        raise ValueError("approver identity is required -- Rule 3.")

    case = load_case(deviation_id)
    if decision == "APPROVE" and case.get("guardrail_violations"):
        raise GuardrailViolation(
            f"Cannot APPROVE {deviation_id}: unresolved guardrail violations -- "
            + "; ".join(case["guardrail_violations"])
        )
    case["approval"] = {
        "approver": approver,
        "decision": decision,
        "notes": notes,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    with open(CASES_DIR / f"{deviation_id}.json", "w") as f:
        json.dump(case, f, indent=2, default=str)

    if decision == "APPROVE":
        case["status"] = "FINAL"
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        with open(APPROVED_DIR / f"{deviation_id}.json", "w") as f:
            json.dump(case, f, indent=2, default=str)

    return case


def main():
    parser = argparse.ArgumentParser(description="Human approval gate (standalone).")
    parser.add_argument("deviation_id")
    parser.add_argument("--approver", required=True, help="reviewer identity -- never optional")
    parser.add_argument("--decision", required=True, choices=DECISIONS)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    case = approve_case(args.deviation_id, args.approver, args.decision, args.notes)
    print(json.dumps(case["approval"], indent=2))
    if case.get("status") == "FINAL":
        print(f"FINAL -- written to logs/approved/{args.deviation_id}.json")
    else:
        print(f"Not finalized (decision={args.decision}) -- logs/approved/ untouched.")


if __name__ == "__main__":
    main()
