#!/usr/bin/env python3
"""Trace + observability (CLAUDE.md Phase 8, Section 7 diagram). One append-only JSONL file
per case (logs/traces/<deviation_id>.jsonl), one line per step: agent, tool, evidence_id,
model, tokens, latency, cost. `render_trace` renders the full chain as a plain-text table for
a reviewer/auditor -- no raw prompt/response content is ever recorded here (Rule 5: prompt
logging disabled), only metadata.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

TRACE_DIR = Path(__file__).resolve().parent.parent / "logs" / "traces"

COLUMNS = ["step", "agent", "tool", "evidence_id", "model", "total_tokens", "latency_seconds", "cost_usd"]


def _trace_path(deviation_id: str) -> Path:
    return TRACE_DIR / f"{deviation_id}.jsonl"


def reset_trace(deviation_id: str) -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    _trace_path(deviation_id).write_text("")


def record_step(deviation_id: str, step: str, agent: str, tool: str = "", evidence_id: str = "",
                 model: str = "", route_result: dict | None = None) -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "step": step,
        "agent": agent,
        "tool": tool,
        "evidence_id": evidence_id,
        "model": model,
        "prompt_tokens": (route_result or {}).get("prompt_tokens", ""),
        "completion_tokens": (route_result or {}).get("completion_tokens", ""),
        "total_tokens": (route_result or {}).get("total_tokens", ""),
        "latency_seconds": (route_result or {}).get("latency_seconds", ""),
        "cost_usd": (route_result or {}).get("cost_usd", ""),
    }
    with open(_trace_path(deviation_id), "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_trace(deviation_id: str) -> list[dict]:
    path = _trace_path(deviation_id)
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def render_trace(deviation_id: str) -> str:
    rows = load_trace(deviation_id)
    if not rows:
        return f"(no trace recorded for {deviation_id})"

    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in COLUMNS}
    header = " | ".join(c.ljust(widths[c]) for c in COLUMNS)
    sep = "-+-".join("-" * widths[c] for c in COLUMNS)
    lines = [header, sep]
    for r in rows:
        lines.append(" | ".join(str(r.get(c, "")).ljust(widths[c]) for c in COLUMNS))
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Render a case's trace table.")
    parser.add_argument("deviation_id")
    args = parser.parse_args()
    print(render_trace(args.deviation_id))


if __name__ == "__main__":
    main()
