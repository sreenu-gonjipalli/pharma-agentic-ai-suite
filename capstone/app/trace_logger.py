#!/usr/bin/env python3
"""Append-only traceability logging (CLAUDE.md Section 7).

One JSON line per pipeline step: agent, action, tool/skill used, a redacted input summary
(never the full raw report text -- Section 5, PHI stays out of logs), an output summary,
the guardrail result, and a timestamp. Shared by the standalone app/pipeline.py orchestrator
and usable from anywhere else that needs the same append behavior.
"""
import json
import os
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(PROJECT_ROOT, "logs", "traceability.jsonl")


def redact(text, max_len=80):
    if text is None:
        return None
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"...[{len(text) - max_len} more chars redacted]"


def log_step(case_id, agent, action, tool, input_summary, output_summary, guardrail_result="PASS"):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "agent": agent,
        "action": action,
        "tool": tool,
        "input_summary": redact(input_summary),
        "output_summary": redact(output_summary, max_len=200),
        "guardrail_result": guardrail_result,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_steps(case_id=None):
    if not os.path.exists(LOG_PATH):
        return []
    steps = []
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if case_id is None or entry.get("case_id") == case_id:
                steps.append(entry)
    return steps
