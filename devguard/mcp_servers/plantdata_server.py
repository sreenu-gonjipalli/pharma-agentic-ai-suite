#!/usr/bin/env python3
"""Read-only MCP server over outcome/result data (CLAUDE.md Phase 2: 4 read-only servers).

Wraps data/lab_results.csv (manufacturing batch release tests) and data/subject_visits.csv
(clinical visit schedule adherence) — the per-domain outcome records that DataCheck/Classifier
sub-agents read evidence from. Raw pass/fail and offset values only; no severity or impact
judgment happens here (Rule 2).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

LAB_FILE = "lab_results.csv"
VISIT_FILE = "subject_visits.csv"
SERVER = "plantdata"

mcp = FastMCP(
    SERVER,
    instructions=(
        "Read-only access to manufacturing lab results (data/lab_results.csv) and clinical "
        "subject visit records (data/subject_visits.csv). Every response carries a source "
        "block per CLAUDE.md Section 6. Returns raw recorded values only."
    ),
)


@mcp.tool()
def get_lab_results(batch_id: str) -> dict:
    """Fetch every lab-result record for one batch_id (manufacturing domain)."""
    rows = [r for r in common.read_csv(LAB_FILE) if r["batch_id"] == batch_id]
    return common.with_source(rows, SERVER, "get_lab_results", batch_id, LAB_FILE)


@mcp.tool()
def get_subject_visits(subject_id: str) -> dict:
    """Fetch every visit record for one subject_id (clinical domain)."""
    rows = [r for r in common.read_csv(VISIT_FILE) if r["subject_id"] == subject_id]
    return common.with_source(rows, SERVER, "get_subject_visits", subject_id, VISIT_FILE)


if __name__ == "__main__":
    mcp.run()
