#!/usr/bin/env python3
"""PreToolUse guardrail hook (CLAUDE.md Section 6/2, Phase 6).

Blocks:
  1. Any Bash command whose leading program (in each pipeline segment) is not on a small
     allowlist of tools this project's agents actually need (Section 6: "no network calls
     outside OpenRouter + local MCP"). Positive allowlisting rather than naming specific
     forbidden network tools -- anything not explicitly needed for this repo's work is refused
     by default, network clients included.
  2. Any Write outside logs/ -- agents have nothing else to write at runtime; data/, packs/,
     src/, mcp_servers/, .claude/ are developer-maintained code/config, never agent output.

Exit 0 = allow. Exit 2 = block; stderr is surfaced back to the calling agent as the reason.
"""
import json
import os
import re
import sys

ALLOWED_COMMANDS = {
    "python3", "python", "pip", "pip3", "pytest",
    "ls", "cat", "head", "tail", "wc", "grep", "find", "sort", "uniq", "awk", "sed",
    "echo", "printf", "mkdir", "pwd", "cd", "test", "true", "false",
    "git",
}

ALLOWED_WRITE_PREFIX = "logs/"

PIPELINE_SPLIT_RE = re.compile(r"[|;&]{1,2}")


def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


def leading_command(segment: str) -> str:
    segment = segment.strip()
    while segment.startswith(("(", "!", "sudo ")):
        segment = segment.lstrip("(!").strip()
        if segment.startswith("sudo "):
            segment = segment[len("sudo "):].strip()
    parts = segment.split()
    if not parts:
        return ""
    # skip leading VAR=value environment assignments
    i = 0
    while i < len(parts) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", parts[i]):
        i += 1
    return parts[i] if i < len(parts) else ""


def check_bash(tool_input: dict) -> None:
    command = tool_input.get("command", "") or ""
    for segment in PIPELINE_SPLIT_RE.split(command):
        cmd = leading_command(segment)
        if cmd and cmd not in ALLOWED_COMMANDS:
            block(
                "GUARDRAIL BLOCK (CLAUDE.md Section 6 -- 'no network calls outside OpenRouter + "
                f"local MCP'): command '{cmd}' is not on this project's Bash allowlist "
                f"({sorted(ALLOWED_COMMANDS)})."
            )


def check_write(tool_input: dict, cwd: str) -> None:
    file_path = tool_input.get("file_path", "") or ""
    rel = relative_to_root(file_path, cwd).replace(os.sep, "/")
    if not (rel == ALLOWED_WRITE_PREFIX.rstrip("/") or rel.startswith(ALLOWED_WRITE_PREFIX)):
        block(
            f"GUARDRAIL BLOCK (CLAUDE.md Phase 6): file writes are only allowed under logs/. "
            f"Rejected write to '{rel}'."
        )


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd", "") or ""

    if tool_name == "Bash":
        check_bash(tool_input)
    elif tool_name == "Write":
        check_write(tool_input, cwd)

    sys.exit(0)


if __name__ == "__main__":
    main()
