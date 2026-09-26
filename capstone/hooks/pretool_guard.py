#!/usr/bin/env python3
"""PreToolUse guardrail hook (CLAUDE.md §6, Business Rule 3).

Blocks:
  1. Any Bash command that looks like an external-submission/transmission call — no tool in
     this codebase is authorized to file/transmit a case anywhere (Business Rule 3), so any
     attempt (network call, mail, upload, "submit"/"file"/"transmit" verbs) is rejected outright.
  2. Any tool call whose name itself suggests submission/transmission — defense in depth in
     case such a tool is ever added to an MCP server without updating this hook.
  3. File writes (via the Write tool) outside cases/, logs/, or memory/ — the only directories
     agents are allowed to write into per §6 and §5.
  4. Any Write to logs/traceability.jsonl specifically — that log is append-only (§7); it must be
     appended via Bash `>>`, never overwritten wholesale by the Write tool.

Exit 0 = allow. Exit 2 = block; stderr is surfaced back to the calling agent as the reason.
"""
import json
import os
import re
import sys

SUBMISSION_PATTERNS = [
    r"\bcurl\b", r"\bwget\b", r"\bhttpie\b", r"\bhttp\b\s+POST", r"\bnc\b\s+-", r"\bnetcat\b",
    r"\bssh\b", r"\bscp\b", r"\bsftp\b", r"\bftp\b", r"\brsync\b.*::", r"\bsmtp", r"sendmail",
    r"requests\.(post|put|patch)", r"urllib\.request", r"httpx\.(post|put|patch)",
    r"socket\.connect", r"boto3", r"paramiko", r"\be2b\b", r"gateway", r"submit_case",
    r"file_report", r"transmit", r"\bdispatch\b",
]
SUBMISSION_TOOL_NAME_RE = re.compile(r"submit|transmit|dispatch|file_report|send_to_(regulator|agency)", re.I)

ALLOWED_WRITE_PREFIXES = ("cases/", "logs/", "memory/")


def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def relative_to_root(path: str, cwd: str) -> str:
    if not os.path.isabs(path):
        path = os.path.join(cwd or project_root(), path)
    try:
        return os.path.relpath(os.path.normpath(path), project_root())
    except ValueError:
        return path


def block(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)


def check_bash(tool_input: dict) -> None:
    command = tool_input.get("command", "") or ""
    for pattern in SUBMISSION_PATTERNS:
        if re.search(pattern, command, re.I):
            block(
                "GUARDRAIL BLOCK (Business Rule 3 — no autonomous submission): command matches "
                f"'{pattern}'. No tool in this codebase may transmit or file a case to an "
                "external system. If a real submission integration is ever needed, it requires "
                "a separate, explicit human decision and an update to CLAUDE.md §3.3 first."
            )


def check_write(tool_input: dict, cwd: str) -> None:
    file_path = tool_input.get("file_path", "") or ""
    rel = relative_to_root(file_path, cwd).replace(os.sep, "/")
    if rel.endswith("logs/traceability.jsonl"):
        block(
            "GUARDRAIL BLOCK (CLAUDE.md §7): logs/traceability.jsonl is append-only. Use a "
            "shell append (`>>`) via Bash, not the Write tool, which overwrites the whole file."
        )
    if not any(rel == p.rstrip("/") or rel.startswith(p) for p in ALLOWED_WRITE_PREFIXES):
        block(
            "GUARDRAIL BLOCK (CLAUDE.md §6): file writes are only allowed under cases/, logs/, "
            f"or memory/. Rejected write to '{rel}'."
        )


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd", "") or ""

    if SUBMISSION_TOOL_NAME_RE.search(tool_name):
        block(
            "GUARDRAIL BLOCK (Business Rule 3 — no autonomous submission): tool name "
            f"'{tool_name}' looks like an external-submission call, which is never permitted."
        )

    if tool_name == "Bash":
        check_bash(tool_input)
    elif tool_name == "Write":
        check_write(tool_input, cwd)

    sys.exit(0)


if __name__ == "__main__":
    main()
