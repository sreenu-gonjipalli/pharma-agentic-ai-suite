#!/usr/bin/env python3
"""Standalone orchestrator for the PV case pipeline (intake -> coding -> triage ->
duplicate-check -> narrative), reusing the exact same skill scripts and guardrail logic as the
Claude-Code sub-agent pipeline described in CLAUDE.md, but driven by a direct LLM API call
(app/llm_client.py) instead of running inside a Claude Code session. This lets the Streamlit UI
(app/streamlit_app.py) run end-to-end outside Claude Code.

Coding and duplicate-check stay fully deterministic/local (no LLM) -- only intake extraction,
triage rationale, and narrative drafting call an LLM, and every LLM output is re-validated by
hooks/advisory_check.py before it is written to case state, exactly like the hook-enforced path.
No function here can move a case to FINAL or send it anywhere -- that stays a human-only action
(case_store.approve_case), never called from this module.
"""
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")
HOOKS_DIR = os.path.join(PROJECT_ROOT, "hooks")

for p in (
    os.path.join(SKILLS_DIR, "case-state-io", "scripts"),
    os.path.join(SKILLS_DIR, "meddra-coding-lookup", "scripts"),
    os.path.join(SKILLS_DIR, "duplicate-case-search", "scripts"),
    HOOKS_DIR,
):
    if p not in sys.path:
        sys.path.insert(0, p)

import case_store  # noqa: E402
import meddra_lookup  # noqa: E402
import duplicate_search  # noqa: E402
import advisory_check  # noqa: E402

import llm_client  # noqa: E402
import trace_logger  # noqa: E402

ADVISORY_TAG = advisory_check.ADVISORY_TAG
NARRATIVE_DISCLAIMER = advisory_check.NARRATIVE_DISCLAIMER


class GuardrailViolation(RuntimeError):
    """Raised when an agent step's output fails hooks/advisory_check.py -- mirrors the
    PostToolUse hook's exit-2 behavior for the Claude-Code path."""


def new_case_id() -> str:
    return "CASE-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


INTAKE_SYSTEM_PROMPT = """You are an information-extraction assistant for a pharmacovigilance \
case-intake prototype. You extract ONLY facts explicitly present in the given adverse-event \
report text. You never infer, guess, or fill in facts from general drug knowledge. For any field \
not explicitly present in the text, set "value" to the literal string "NOT REPORTED" and \
"source_span" to null. For any field you DO report, "source_span" must be an exact quote copied \
from the input text supporting that value -- never paraphrase the span.

Return ONLY a JSON object with exactly this shape:
{
  "patient": {"value": "...", "source_span": "..." or null},
  "drugs": [{"value": "...", "source_span": "..."}],
  "events": [{"description": "...", "source_span": "..."}],
  "onset_date": {"value": "...", "source_span": "..." or null},
  "report_date": {"value": "...", "source_span": "..." or null},
  "reporter": {"value": "...", "source_span": "..." or null}
}
If there are no drugs or events mentioned, return an empty list for that key -- never invent one."""

TRIAGE_SYSTEM_PROMPT = """You are a pharmacovigilance triage assistant applying the ICH E2A \
seriousness checklist to a structured case. You are advisory only -- a human reviewer makes the \
final call. Walk EVERY criterion below against the case text and mark it SUPPORTED (with the \
exact source text span that supports it) or NOT SUPPORTED. Absence of detail is NOT SUPPORTED, \
never treated as evidence of seriousness either way. Mark overall "SERIOUS" only if at least one \
criterion is SUPPORTED with an actual source span from the case text.

Criteria: death, life_threatening, hospitalization, disability, congenital_anomaly, \
other_medically_important.

Expectedness: only assess it if the case text itself states the drug's known/labeled effects; \
otherwise set expectedness to the literal string "NOT ASSESSABLE — NO REFERENCE LABEL PROVIDED". \
Never use outside knowledge of the drug to fabricate a reference label.

Return ONLY a JSON object with exactly this shape:
{
  "status": "SUGGESTED — PENDING HUMAN REVIEW",
  "overall": "SERIOUS" or "NON-SERIOUS",
  "criteria": {
    "death": {"result": "SUPPORTED"|"NOT SUPPORTED", "source_span": "..." or null},
    "life_threatening": {"result": "...", "source_span": "..." or null},
    "hospitalization": {"result": "...", "source_span": "..." or null},
    "disability": {"result": "...", "source_span": "..." or null},
    "congenital_anomaly": {"result": "...", "source_span": "..." or null},
    "other_medically_important": {"result": "...", "source_span": "..." or null}
  },
  "expectedness": "...",
  "rationale": "one to three sentences citing the specific criterion/source span"
}"""

NARRATIVE_SYSTEM_PROMPT = """You draft a plain-language pharmacovigilance case narrative from \
structured case data you are given. You add NO new facts -- use only what is present in the \
case state. Any field whose value is "NOT REPORTED" stays described as not reported. The \
seriousness/expectedness assessment is advisory -- describe it explicitly as such. The narrative \
text MUST start with exactly this line, verbatim, on its own: \
"DRAFT NARRATIVE — PENDING HUMAN REVIEW, NOT A FINAL CASE RECORD."

Return ONLY a JSON object: {"text": "<the full narrative, starting with the mandated line>"}"""


def run_intake(raw_text: str, case_id: str = None) -> dict:
    if case_id is None:
        case_id = new_case_id()
        case_store.init_case(case_id)
    elif not os.path.exists(case_store.case_path(case_id)):
        case_store.init_case(case_id)

    data, provider = llm_client.chat_json(INTAKE_SYSTEM_PROMPT, raw_text)
    # Kept verbatim (not re-generated by the LLM) so every source_span above is checkable
    # against the actual report text, and so triage/narrative can still see context that
    # doesn't fit the fixed intake schema (e.g. hospitalization detail) -- Business Rule 6.
    data["raw_report_text"] = raw_text

    input_summary = f"raw report text ({len(raw_text)} chars) -- not logged verbatim, PHI"
    violations = advisory_check.validate_intake(data)
    if violations:
        trace_logger.log_step(case_id, "pv-intake", "extract_fields", f"llm:{provider}",
                               input_summary, str(violations), guardrail_result="BLOCK")
        raise GuardrailViolation("intake guardrail violations: " + "; ".join(violations))

    case = case_store.update_case(case_id, "intake", data, "pv-intake", "extract_fields")
    trace_logger.log_step(case_id, "pv-intake", "extract_fields", f"llm:{provider}",
                           input_summary, "fields extracted", guardrail_result="PASS")
    return case


def run_coding(case_id: str) -> dict:
    case = case_store.load_case(case_id)
    events = case.get("intake", {}).get("events", [])
    terms = meddra_lookup.load_terms()

    coding = []
    for event in events:
        text = event.get("description", "") if isinstance(event, dict) else str(event)
        scored = sorted(
            ((meddra_lookup.score(text, t), t) for t in terms), key=lambda x: x[0], reverse=True
        )
        candidates = []
        for s, t in scored[:3]:
            candidates.append({
                "term": t["pt"] if s > 0 else "NO MATCH FOUND",
                "soc": t["soc"] if s > 0 else None,
                "confidence": s,
                "source_span": text,
            })
        if not any(c["confidence"] > 0 for c in candidates):
            candidates = [{"term": "NO MATCH FOUND", "soc": None, "confidence": 0.0, "source_span": text}]
        coding.append({"event": text, "status": ADVISORY_TAG, "candidates": candidates})

    violations = advisory_check.validate_coding(coding)
    if violations:
        trace_logger.log_step(case_id, "pv-coding", "suggest_meddra_codes", "meddra_lookup",
                               f"{len(events)} events", str(violations), guardrail_result="BLOCK")
        raise GuardrailViolation("coding guardrail violations: " + "; ".join(violations))

    case = case_store.update_case(case_id, "coding", coding, "pv-coding", "suggest_meddra_codes")
    trace_logger.log_step(case_id, "pv-coding", "suggest_meddra_codes", "meddra_lookup",
                           f"{len(events)} events", f"{len(coding)} event(s) coded", guardrail_result="PASS")
    return case


def run_triage(case_id: str) -> dict:
    case = case_store.load_case(case_id)
    context = {"intake": case.get("intake", {}), "coding": case.get("coding", [])}

    data, provider = llm_client.chat_json(TRIAGE_SYSTEM_PROMPT, str(context))

    violations = advisory_check.validate_triage(data)
    if violations:
        trace_logger.log_step(case_id, "pv-triage", "assess_seriousness", f"llm:{provider}",
                               "case intake+coding", str(violations), guardrail_result="BLOCK")
        raise GuardrailViolation("triage guardrail violations: " + "; ".join(violations))

    case = case_store.update_case(case_id, "triage", data, "pv-triage", "assess_seriousness")
    trace_logger.log_step(case_id, "pv-triage", "assess_seriousness", f"llm:{provider}",
                           "case intake+coding", data.get("overall", ""), guardrail_result="PASS")
    return case


def run_duplicate(case_id: str) -> dict:
    target_path = case_store.case_path(case_id)
    import json
    import glob
    with open(target_path) as f:
        target = json.load(f)
    target_text = duplicate_search.flat_text(target)

    matches = []
    for path in glob.glob(os.path.join(duplicate_search.CASES_DIR, "*.json")):
        other_id = os.path.splitext(os.path.basename(path))[0]
        if other_id == case_id:
            continue
        with open(path) as f:
            other = json.load(f)
        sim = duplicate_search.similarity(target_text, duplicate_search.flat_text(other))
        if sim >= duplicate_search.THRESHOLD:
            matches.append({"case_id": other_id, "similarity": sim, "status": ADVISORY_TAG})
    matches.sort(key=lambda m: m["similarity"], reverse=True)

    data = {"matches": matches}
    case = case_store.update_case(case_id, "duplicate_check", data, "pv-duplicate", "search_duplicates")
    trace_logger.log_step(case_id, "pv-duplicate", "search_duplicates", "duplicate_search",
                           "case intake fields", f"{len(matches)} match(es)", guardrail_result="PASS")
    return case


def run_narrative(case_id: str) -> dict:
    case = case_store.load_case(case_id)
    context = {k: v for k, v in case.items() if k in ("intake", "coding", "triage", "duplicate_check")}

    data, provider = llm_client.chat_json(NARRATIVE_SYSTEM_PROMPT, str(context))

    violations = advisory_check.validate_narrative(data)
    if violations:
        trace_logger.log_step(case_id, "pv-narrative", "draft_narrative", f"llm:{provider}",
                               "full case state", str(violations), guardrail_result="BLOCK")
        raise GuardrailViolation("narrative guardrail violations: " + "; ".join(violations))

    case = case_store.update_case(case_id, "narrative", data, "pv-narrative", "draft_narrative")
    trace_logger.log_step(case_id, "pv-narrative", "draft_narrative", f"llm:{provider}",
                           "full case state", "narrative drafted (not logged verbatim -- PHI)",
                           guardrail_result="PASS")
    return case


PIPELINE_STEPS = ("intake", "coding", "triage", "duplicate_check", "narrative")


def run_full_pipeline(raw_text: str, case_id: str = None, progress_cb=None):
    """Runs every step in order; progress_cb(step_name, case_dict) is called after each step
    if given, so a UI can render incremental progress."""
    case = run_intake(raw_text, case_id)
    case_id = case["case_id"]
    if progress_cb:
        progress_cb("intake", case)

    case = run_coding(case_id)
    if progress_cb:
        progress_cb("coding", case)

    case = run_triage(case_id)
    if progress_cb:
        progress_cb("triage", case)

    case = run_duplicate(case_id)
    if progress_cb:
        progress_cb("duplicate_check", case)

    case = run_narrative(case_id)
    if progress_cb:
        progress_cb("narrative", case)

    return case
