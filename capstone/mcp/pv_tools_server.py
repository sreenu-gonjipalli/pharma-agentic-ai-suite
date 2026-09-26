#!/usr/bin/env python3
"""MCP server exposing the PV case-processing tools (CLAUDE.md Phase 5: MCP/tool wiring).

Wraps the same skill-script functions the Bash fallback path uses (case_store, meddra_lookup,
duplicate_search) as schema-validated MCP tools, so sub-agents get structured arguments/results
instead of hand-built shell commands. Deliberately exposes no submission/transmission tool of any
kind — Business Rule 3 ("no autonomous submission") is enforced structurally here, not just by a
hook, because the capability simply does not exist on this server. The human-approval action
(`case_store.approve_case`) is likewise not exposed here — CLAUDE.md §10 reserves it for a human
running the CLI directly, never something an agent can call as a tool.
"""
import os
import sys

SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills")
sys.path.insert(0, os.path.join(SKILLS_DIR, "case-state-io", "scripts"))
sys.path.insert(0, os.path.join(SKILLS_DIR, "meddra-coding-lookup", "scripts"))
sys.path.insert(0, os.path.join(SKILLS_DIR, "duplicate-case-search", "scripts"))

import case_store  # noqa: E402
import meddra_lookup  # noqa: E402
import duplicate_search  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP(
    "pv-tools",
    instructions=(
        "Pharmacovigilance case-processing tools for this capstone prototype. All outputs are "
        "advisory pending human review (CLAUDE.md). No tool here can submit or transmit a case "
        "anywhere; that capability does not exist by design."
    ),
)


@mcp.tool()
def case_init(case_id: str) -> dict:
    """Create a new case file at cases/<case_id>.json with empty history. Fails if it exists."""
    return case_store.init_case(case_id)


@mcp.tool()
def case_read(case_id: str) -> dict:
    """Read the full current state of cases/<case_id>.json."""
    return case_store.load_case(case_id)


@mcp.tool()
def case_update(case_id: str, section: str, data: dict, agent: str, action: str) -> dict:
    """Write one section (intake|coding|triage|duplicate_check|narrative) of a case and append
    a history[] entry. Never overwrites another agent's section — only the named one."""
    return case_store.update_case(case_id, section, data, agent, action)


@mcp.tool()
def meddra_lookup_terms(text: str, top: int = 3) -> list:
    """Suggest up to `top` MedDRA-style candidate terms for a free-text adverse-event
    description, each with a confidence score and the source_span it was derived from. Uses the
    local sample terminology only — never the licensed MedDRA dictionary."""
    terms = meddra_lookup.load_terms()
    scored = [(meddra_lookup.score(text, t), t) for t in terms]
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for s, t in scored[:top]:
        results.append({
            "term": t["pt"] if s > 0 else "NO MATCH FOUND",
            "soc": t["soc"] if s > 0 else None,
            "confidence": s,
            "source_span": text,
        })
    if not any(r["confidence"] > 0 for r in results):
        results = [{"term": "NO MATCH FOUND", "soc": None, "confidence": 0.0, "source_span": text}]
    return results


@mcp.tool()
def duplicate_search_case(case_id: str) -> dict:
    """Search cases/ for likely duplicates of case_id by patient/drug/event field overlap.
    Returns every match at or above the similarity threshold, tagged advisory — never a
    definitive duplicate determination."""
    target_path = os.path.join(duplicate_search.CASES_DIR, f"{case_id}.json")
    if not os.path.exists(target_path):
        return {"matches": [], "error": f"case {case_id} not found"}

    import json
    with open(target_path) as f:
        target = json.load(f)
    target_text = duplicate_search.flat_text(target)

    matches = []
    import glob
    for path in glob.glob(os.path.join(duplicate_search.CASES_DIR, "*.json")):
        other_id = os.path.splitext(os.path.basename(path))[0]
        if other_id == case_id:
            continue
        with open(path) as f:
            other = json.load(f)
        sim = duplicate_search.similarity(target_text, duplicate_search.flat_text(other))
        if sim >= duplicate_search.THRESHOLD:
            matches.append({
                "case_id": other_id,
                "similarity": sim,
                "status": "SUGGESTED — PENDING HUMAN REVIEW",
            })
    matches.sort(key=lambda m: m["similarity"], reverse=True)
    return {"matches": matches}


if __name__ == "__main__":
    mcp.run(transport="stdio")
