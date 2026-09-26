#!/usr/bin/env python3
"""PostToolUse guardrail hook (CLAUDE.md Phase 6/Section 2).

Fires after any Bash or Write call that could have produced a saved case (e.g. `python3 -m
src.supervisor <id> --save`, which writes logs/cases/<id>.json). Re-reads that case off disk
and rejects (exit 2) if src/guardrails.py finds a violation -- checking the file as written,
not the tool-specific argument shapes.
"""
import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASES_DIR = os.path.join(PROJECT_ROOT, "logs", "cases")

sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
import guardrails  # noqa: E402


def find_case_id(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Bash":
        command = tool_input.get("command", "") or ""
        m = re.search(r"src\.supervisor\s+([A-Za-z0-9_.\-]+)", command)
        return m.group(1) if m else ""
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "") or ""
        m = re.search(r"logs/cases/([^/]+)\.json$", file_path.replace(os.sep, "/"))
        return m.group(1) if m else ""
    return ""


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    case_id = find_case_id(tool_name, tool_input)
    if not case_id:
        sys.exit(0)

    case_path = os.path.join(CASES_DIR, f"{os.path.basename(case_id)}.json")
    if not os.path.exists(case_path):
        sys.exit(0)

    with open(case_path) as f:
        case = json.load(f)

    violations = guardrails.validate_case(case)
    if violations:
        print(
            f"GUARDRAIL BLOCK (CLAUDE.md Section 2) -- case {case_id} has non-compliant "
            "output:\n  - " + "\n  - ".join(violations),
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
