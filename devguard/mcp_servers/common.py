"""Shared helpers for DevGuard's read-only MCP servers (CLAUDE.md Section 6: every tool
response must carry a source block; Section 2 Rule 6: these servers expose no write tools)."""
import csv
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_csv(filename: str) -> list[dict]:
    path = os.path.join(DATA_DIR, filename)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def with_source(value, server: str, tool: str, record_id: str, file: str) -> dict:
    return {
        "value": value,
        "source": {
            "server": server,
            "tool": tool,
            "record_id": record_id,
            "file": file,
            "retrieved_at": now_iso(),
        },
    }
