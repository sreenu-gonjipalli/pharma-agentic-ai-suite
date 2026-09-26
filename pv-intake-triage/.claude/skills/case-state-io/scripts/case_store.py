#!/usr/bin/env python3
"""Read/init/update the shared per-case JSON state (CLAUDE.md §5).

Functions here are the single source of truth for case-file I/O — both the CLI below and
`mcp/pv_tools_server.py` import them directly, so validation/guardrail logic never has to be
duplicated between the Bash fallback path and the MCP tool path.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

VALID_SECTIONS = {"intake", "coding", "triage", "duplicate_check", "narrative"}
VALID_DECISIONS = {"APPROVE", "EDIT", "REJECT"}
CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "cases")
CASES_DIR = os.path.normpath(CASES_DIR)


def case_path(case_id: str) -> str:
    safe_id = os.path.basename(case_id)
    return os.path.join(CASES_DIR, f"{safe_id}.json")


def load_case(case_id: str) -> dict:
    path = case_path(case_id)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No case file at {path}")
    with open(path, "r") as f:
        return json.load(f)


def save_case(case_id: str, case: dict) -> None:
    os.makedirs(CASES_DIR, exist_ok=True)
    with open(case_path(case_id), "w") as f:
        json.dump(case, f, indent=2)


def init_case(case_id: str) -> dict:
    path = case_path(case_id)
    if os.path.exists(path):
        raise FileExistsError(f"Case {case_id} already exists; not overwriting.")
    case = {
        "case_id": case_id,
        "status": "IN_PROGRESS",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }
    save_case(case_id, case)
    return case


def update_case(case_id: str, section: str, data, agent: str, action: str) -> dict:
    if section not in VALID_SECTIONS:
        raise ValueError(f"Invalid section '{section}'. Must be one of {sorted(VALID_SECTIONS)}")
    case = load_case(case_id)
    case[section] = data
    case.setdefault("history", []).append({
        "agent": agent,
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    save_case(case_id, case)
    return case


def approve_case(case_id: str, reviewer: str, decision: str, notes: str = "") -> dict:
    """Human approval gate (CLAUDE.md §8/§10). This is the *only* path that can set
    status to FINAL, and it is intentionally not exposed as an MCP tool or listed in any
    sub-agent's tool access — it is a human-run CLI action, never something an agent invokes
    on its own initiative."""
    if decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid decision '{decision}'. Must be one of {sorted(VALID_DECISIONS)}")
    if not reviewer:
        raise ValueError("A reviewer name is required to log a human approval event.")
    case = load_case(case_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    event = {"reviewer": reviewer, "decision": decision, "notes": notes, "timestamp": timestamp}
    case.setdefault("human_approval", []).append(event)
    if decision == "APPROVE":
        case["status"] = "FINAL"
    elif decision == "REJECT":
        case["status"] = "REJECTED"
    else:
        case["status"] = "IN_PROGRESS"
    case.setdefault("history", []).append({
        "agent": f"human-reviewer:{reviewer}",
        "action": f"review_decision:{decision}",
        "timestamp": timestamp,
    })
    save_case(case_id, case)
    return case


def cmd_init(args):
    try:
        case = init_case(args.case_id)
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(case, indent=2))


def cmd_read(args):
    print(json.dumps(load_case(args.case_id), indent=2))


def cmd_update(args):
    try:
        case = update_case(args.case_id, args.section, json.loads(args.data), args.agent, args.action)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(case, indent=2))


def cmd_approve(args):
    try:
        case = approve_case(args.case_id, args.reviewer, args.decision, args.notes or "")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(case, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--case-id", required=True)
    p_init.set_defaults(func=cmd_init)

    p_read = sub.add_parser("read")
    p_read.add_argument("--case-id", required=True)
    p_read.set_defaults(func=cmd_read)

    p_update = sub.add_parser("update")
    p_update.add_argument("--case-id", required=True)
    p_update.add_argument("--section", required=True)
    p_update.add_argument("--data", required=True, help="JSON string for this section's contents")
    p_update.add_argument("--agent", required=True)
    p_update.add_argument("--action", required=True)
    p_update.set_defaults(func=cmd_update)

    p_approve = sub.add_parser(
        "approve",
        help="Human reviewer only — logs an approval/edit/reject decision; APPROVE is the only way to reach FINAL.",
    )
    p_approve.add_argument("--case-id", required=True)
    p_approve.add_argument("--reviewer", required=True, help="Name/ID of the human reviewer")
    p_approve.add_argument("--decision", required=True, choices=sorted(VALID_DECISIONS))
    p_approve.add_argument("--notes", default="")
    p_approve.set_defaults(func=cmd_approve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
