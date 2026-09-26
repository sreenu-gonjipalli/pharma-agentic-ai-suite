#!/usr/bin/env python3
"""Guardrail validators (CLAUDE.md Phase 6, Section 2). Shared by the PostToolUse hook
(.claude/hooks/posttool_guard.py) and available to the standalone pipeline. Checks a fully
assembled case dict (the shape src/supervisor.py produces) for the checkable non-negotiable
rules:

  Rule 1 (no unsupported claims): a product-impact/severity claim, or a "no product impact"
    statement in the draft narrative, must be backed by an actual lab_fail check in findings --
    missing evidence must escalate, never be silently asserted either way.
  Rule 3 (human approval is blocking): no case may carry status=FINAL without an approval record.
  Section 1 out-of-scope: the draft must never make a batch release/rejection call or a
    definitive causality/medical determination -- those are for the human approver, not this
    system.

Rules 2/4/5/6 are enforced structurally elsewhere (src/checks/ owns all computation, no
":free" models in src/llm.py, no write tools on any mcp_servers/* server) and are not
re-checked here.
"""
import re

RELEASE_REJECTION_RE = re.compile(
    r"\b(batch is (approved|cleared) for release|batch should be rejected|"
    r"recommend(?:ed)? (?:for )?release|rejection of (?:the )?batch)\b", re.I
)
DEFINITIVE_CAUSALITY_RE = re.compile(
    r"\b(definitively caused by|confirmed root cause is|proven to be caused)\b", re.I
)
NO_PRODUCT_IMPACT_RE = re.compile(r"no product impact", re.I)


def validate_case(case: dict) -> list[str]:
    violations = []
    domain = case.get("domain")
    decision = case.get("decision") or {}
    findings = case.get("findings") or []
    checks_present = {f.get("check") for f in findings}

    if domain == "manufacturing" and decision.get("product_impact") is not None:
        if "lab_fail" not in checks_present:
            violations.append(
                f"decision.product_impact is asserted ({decision.get('product_impact')!r}) but "
                "no lab_fail check is present in findings -- Rule 1 forbids asserting product "
                "impact either way without lab evidence; escalate as NOT DETERMINED instead."
            )

    draft = case.get("draft") or ""
    if draft:
        if domain == "manufacturing" and NO_PRODUCT_IMPACT_RE.search(draft) and "lab_fail" not in checks_present:
            violations.append(
                "Draft narrative states 'no product impact' but findings contain no lab_fail "
                "check to support that claim (Rule 1)."
            )
        if RELEASE_REJECTION_RE.search(draft):
            violations.append(
                "Draft makes a batch release/rejection determination -- out of scope (Section 1); "
                "must defer to the QA Head approver."
            )
        if DEFINITIVE_CAUSALITY_RE.search(draft):
            violations.append(
                "Draft asserts a definitive causal/medical determination -- out of scope "
                "(Section 1: 'Causality or medical judgment')."
            )

    if case.get("status") == "FINAL" and not case.get("approval"):
        violations.append("status=FINAL without an approval record -- Rule 3 (human approval is blocking).")

    return violations
