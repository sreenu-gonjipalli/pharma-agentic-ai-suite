#!/usr/bin/env python3
"""Retrieval sub-agent (CLAUDE.md Phase 4). Gathers every piece of evidence relevant to one
deviation from the read-only MCP servers and assembles it into a single evidence bundle, each
item carrying its Section-6 source block. Runnable standalone: `python -m src.agents.retrieval
DEV-2026-0091`.

The model-routing table (Section 5) assigns this step the `retrieval` route for a long-context
evidence summary. Gathering the evidence itself is deterministic (Rule 2 spirit -- which MCP
calls to make is a fixed lookup by domain, not a judgment call), so the summary call is optional
best-effort: if the route is unavailable (as of Phase 0's log, this account's OpenRouter
guardrail policy blocks every route except analysis_drafting), the bundle is still returned in
full with `summary` set to None and the error recorded, rather than failing the whole retrieval.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mcp_servers"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import deviation_server  # noqa: E402
import equipment_server  # noqa: E402
import plantdata_server  # noqa: E402
import doc_server  # noqa: E402
from llm import call_route_with_retry, load_config  # noqa: E402


def gather_evidence(deviation_id: str) -> dict:
    deviation = deviation_server.get_deviation(deviation_id)
    if deviation["value"] is None:
        raise ValueError(f"No deviation record for '{deviation_id}'")

    record = deviation["value"]
    domain = record["domain"]
    evidence = [deviation]

    if domain == "manufacturing":
        evidence.append(equipment_server.get_temperature_trace(record["batch_id"]))
        evidence.append(equipment_server.get_maintenance_history(record["equipment_id"]))
        evidence.append(plantdata_server.get_lab_results(record["batch_id"]))
    elif domain == "clinical":
        evidence.append(plantdata_server.get_subject_visits(record["subject_id"]))
    else:
        raise ValueError(f"Unknown domain '{domain}' for deviation '{deviation_id}'")

    evidence.append(doc_server.search_documents(record["description"], top_k=2))

    return {"deviation_id": deviation_id, "domain": domain, "evidence": evidence}


def summarize(bundle: dict) -> tuple[str | None, str | None, dict]:
    """Best-effort one-paragraph evidence summary via the `retrieval` route. Returns
    (summary_text, error, meta) -- exactly one of summary_text/error is None. `meta` carries
    the route/model attempted and, on success, the RouteCallResult (Phase 8 trace needs this
    regardless of whether the call succeeded)."""
    evidence_lines = []
    for item in bundle["evidence"]:
        if "source" in item:
            src, value = item["source"], item["value"]
            evidence_lines.append(f"- {src['record_id']} ({src['file']}): {json.dumps(value)[:300]}")
        else:  # doc_server.search_documents: {"query", "results": [{"value","source"},...]}
            for r in item.get("results", []):
                src, value = r["source"], r["value"]
                evidence_lines.append(f"- {src['record_id']} ({src['file']}): {json.dumps(value)[:300]}")

    prompt = (
        "Summarize the following pharmacovigilance/deviation evidence in one paragraph, citing "
        "each record_id you rely on. Do not state anything not present below.\n\n"
        + "\n".join(evidence_lines)
    )
    meta = {"route": "retrieval", "model": load_config()["routes"]["retrieval"]["model"], "route_result": None}
    try:
        content, result = call_route_with_retry("retrieval", [{"role": "user", "content": prompt}])
        meta["route_result"] = result.model_dump()
        return content, None, meta
    except Exception as exc:  # OpenRouter guardrail/model errors are expected in this account
        return None, str(exc), meta


def main():
    parser = argparse.ArgumentParser(description="Retrieval sub-agent (standalone).")
    parser.add_argument("deviation_id")
    parser.add_argument("--no-summary", action="store_true", help="skip the LLM summary call")
    args = parser.parse_args()

    bundle = gather_evidence(args.deviation_id)
    if not args.no_summary:
        summary, error, meta = summarize(bundle)
        bundle["summary"] = summary
        bundle["summary_error"] = error
        bundle["summary_meta"] = meta

    print(json.dumps(bundle, indent=2, default=str))


if __name__ == "__main__":
    main()
