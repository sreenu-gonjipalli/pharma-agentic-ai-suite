#!/usr/bin/env python3
"""Shared guardrail logic for CLAUDE.md Business Rules 1/2/6: seriousness and MedDRA-coding
output must be tagged advisory and carry a source-span pointer. Imported by posttool_guard.py
(and reusable from anywhere else that needs the same check) so the rule lives in one place.
"""
import json

ADVISORY_TAG = "SUGGESTED — PENDING HUMAN REVIEW"
SPAN_KEYS = ("source_span", "span", "quote")
CONFIDENCE_KEYS = ("confidence",)
RATIONALE_KEYS = ("rationale",)


def _contains_key(obj, key_names) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in key_names and v not in (None, ""):
                return True
            if _contains_key(v, key_names):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if _contains_key(item, key_names):
                return True
    return False


def validate_coding(data) -> list:
    """Business Rule 2 (top-N candidates, never a single silent choice) and Rule 6
    (source-span pointer on every suggested code)."""
    violations = []
    blob = json.dumps(data, ensure_ascii=False)
    if ADVISORY_TAG not in blob:
        violations.append(f"missing advisory tag '{ADVISORY_TAG}'")
    if not _contains_key(data, SPAN_KEYS):
        violations.append("no candidate carries a source text span")
    if not _contains_key(data, CONFIDENCE_KEYS):
        violations.append("no candidate carries a confidence score")
    return violations


def validate_triage(data) -> list:
    """Business Rule 1 (advisory only) and Rule 6 (source-span pointer per criterion). A
    criterion marked NOT SUPPORTED legitimately has no span to cite -- absence of detail is
    not evidence either way (CLAUDE.md, ich-e2a-seriousness skill) -- so only a criterion
    actually marked SUPPORTED is required to carry the span backing it up."""
    violations = []
    blob = json.dumps(data, ensure_ascii=False)
    if ADVISORY_TAG not in blob:
        violations.append(f"missing advisory tag '{ADVISORY_TAG}'")
    criteria = data.get("criteria", {}) if isinstance(data, dict) else {}
    for name, crit in criteria.items():
        if isinstance(crit, dict) and crit.get("result") == "SUPPORTED" and not crit.get("source_span"):
            violations.append(f"criterion '{name}' marked SUPPORTED with no source_span")
    if not _contains_key(data, RATIONALE_KEYS):
        violations.append("no rationale provided")
    return violations


NOT_REPORTED = "NOT REPORTED"
NARRATIVE_DISCLAIMER = "DRAFT NARRATIVE — PENDING HUMAN REVIEW, NOT A FINAL CASE RECORD."


def validate_intake(data) -> list:
    """Business Rule 4 (no fabrication): any field whose value is not `NOT REPORTED` must carry
    the source_span it was extracted from, or it's a fabrication risk."""
    violations = []

    def walk(node):
        if isinstance(node, dict):
            if "value" in node:
                val = node.get("value")
                span = node.get("source_span")
                if val not in (None, "", NOT_REPORTED) and not span:
                    violations.append(f"field with value '{val}' has no source_span (possible fabrication)")
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return violations


def validate_narrative(data) -> list:
    """The draft narrative must open with the mandated disclaimer line (CLAUDE.md Section 8)."""
    violations = []
    text = data.get("text", "") if isinstance(data, dict) else str(data)
    if not text.startswith(NARRATIVE_DISCLAIMER):
        violations.append("narrative missing mandated opening disclaimer line")
    return violations


def validate_case_sections(case: dict) -> list:
    """Run every applicable check against a full case dict; returns a flat list of
    'section: violation' strings (empty means compliant)."""
    violations = []
    if "intake" in case:
        violations += [f"intake: {v}" for v in validate_intake(case["intake"])]
    if "coding" in case:
        violations += [f"coding: {v}" for v in validate_coding(case["coding"])]
    if "triage" in case:
        violations += [f"triage: {v}" for v in validate_triage(case["triage"])]
    if "narrative" in case:
        violations += [f"narrative: {v}" for v in validate_narrative(case["narrative"])]
    return violations
