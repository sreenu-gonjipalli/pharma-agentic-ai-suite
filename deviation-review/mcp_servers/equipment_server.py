#!/usr/bin/env python3
"""Read-only MCP server over equipment evidence (CLAUDE.md Phase 2: 4 read-only servers).

Wraps data/equipment_traces.csv (temperature time series) and data/maintenance.csv (service /
calibration history). Numbers stay raw here — CLAUDE.md Rule 2 reserves excursion/breach
computation for src/checks/ (Phase 3), never this server or an LLM.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

TRACE_FILE = "equipment_traces.csv"
MAINT_FILE = "maintenance.csv"
SERVER = "equipment"

mcp = FastMCP(
    SERVER,
    instructions=(
        "Read-only access to equipment temperature traces (data/equipment_traces.csv) and "
        "maintenance/calibration history (data/maintenance.csv). Every response carries a "
        "source block per CLAUDE.md Section 6. Returns raw readings only — no excursion or "
        "breach computation happens here (Rule 2)."
    ),
)


@mcp.tool()
def get_temperature_trace(batch_id: str) -> dict:
    """Fetch every temperature-trace reading recorded for one batch_id, in file order."""
    rows = [r for r in common.read_csv(TRACE_FILE) if r["batch_id"] == batch_id]
    return common.with_source(rows, SERVER, "get_temperature_trace", batch_id, TRACE_FILE)


@mcp.tool()
def get_maintenance_history(equipment_id: str) -> dict:
    """Fetch every maintenance/calibration record for one equipment_id (e.g. 'Oven-04')."""
    rows = [r for r in common.read_csv(MAINT_FILE) if r["equipment_id"] == equipment_id]
    return common.with_source(rows, SERVER, "get_maintenance_history", equipment_id, MAINT_FILE)


if __name__ == "__main__":
    mcp.run()
