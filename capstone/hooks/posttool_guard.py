#!/usr/bin/env python3
"""PostToolUse guardrail hook (CLAUDE.md §6): rejects seriousness/coding output missing the
advisory tag or a source-text-span pointer.

Fires after any tool call that could have changed a case file (Write, Bash, or an
mcp__pv-tools__case_* call) and re-reads that case's JSON off disk — checking the file as
written, regardless of which tool path wrote it, rather than trying to parse tool-specific
argument shapes for the *content* itself.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advisory_check  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_DIR = os.path.join(PROJECT_ROOT, "cases")


def find_case_id(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Bash":
        command = tool_input.get("command", "") or ""
        m = re.search(r"--case-id[= ]([^\s]+)", command)
        return m.group(1) if m else ""
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "") or ""
        m = re.search(r"cases/([^/]+)\.json$", file_path.replace(os.sep, "/"))
        return m.group(1) if m else ""
    if tool_name.startswith("mcp__pv-tools__case_"):
        return tool_input.get("case_id", "") or ""
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

    violations = advisory_check.validate_case_sections(case)
    if violations:
        print(
            f"GUARDRAIL BLOCK (CLAUDE.md §6, Business Rules 1/2/6) — case {case_id} has "
            "non-compliant advisory output:\n  - " + "\n  - ".join(violations) +
            "\nRe-write the section so every suggested code/flag is tagged "
            f"'{advisory_check.ADVISORY_TAG}' and carries a source_span.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
