#!/usr/bin/env python3
"""Read-only MCP server over the deviation log (CLAUDE.md Phase 2: 4 read-only servers).

Wraps data/deviations.csv. No write tools exist here by design (Section 2 Rule 6) — the
Supervisor/sub-agents can only read the log, never file or edit a deviation record.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

FILE = "deviations.csv"
SERVER = "deviations"

mcp = FastMCP(
    SERVER,
    instructions=(
        "Read-only access to the DevGuard deviation log (data/deviations.csv). Every response "
        "carries a source block per CLAUDE.md Section 6. No tool here can create, edit, or "
        "close a deviation record."
    ),
)


@mcp.tool()
def get_deviation(deviation_id: str) -> dict:
    """Fetch one deviation record by its deviation_id (e.g. 'DEV-2026-0091')."""
    rows = common.read_csv(FILE)
    for row in rows:
        if row["deviation_id"] == deviation_id:
            return common.with_source(row, SERVER, "get_deviation", deviation_id, FILE)
    return common.with_source(None, SERVER, "get_deviation", deviation_id, FILE)


@mcp.tool()
def list_deviations(domain: str = "", batch_id: str = "", subject_id: str = "") -> dict:
    """List deviation records, optionally filtered by domain ('clinical'|'manufacturing'),
    batch_id, and/or subject_id. Any filter left empty is not applied."""
    rows = common.read_csv(FILE)
    if domain:
        rows = [r for r in rows if r["domain"] == domain]
    if batch_id:
        rows = [r for r in rows if r["batch_id"] == batch_id]
    if subject_id:
        rows = [r for r in rows if r["subject_id"] == subject_id]
    record_id = f"domain={domain or '*'},batch_id={batch_id or '*'},subject_id={subject_id or '*'}"
    return common.with_source(rows, SERVER, "list_deviations", record_id, FILE)


if __name__ == "__main__":
    mcp.run()
