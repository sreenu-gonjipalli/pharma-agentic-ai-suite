# Agentic AI for Pharmacovigilance Case Intake & Triage

Capstone prototype. **Not a validated clinical/regulatory system.** Every clinical or regulatory
output is advisory and pending mandatory human sign-off -- see `CLAUDE.md` for the full business
rules and architecture this repo is built against.

## What this is

Takes a raw adverse-event (AE) report (call-center text, email, literature excerpt) through five
stages -- intake extraction, MedDRA coding candidates, seriousness/expectedness triage, duplicate
check, draft narrative -- and stops at a mandatory human approval gate before anything is `FINAL`.
No code path in this repo can send a case to any outside system (Business Rule 3).

## Two ways to run the pipeline

1. **Inside Claude Code** -- the original design (`CLAUDE.md` Sections 2-4): an orchestrator
   session delegates to the `pv-intake` / `pv-coding` / `pv-triage` / `pv-duplicate` /
   `pv-narrative` sub-agents (`.claude/agents/`), which call the `pv-tools` MCP server
   (`mcp/pv_tools_server.py`). Guardrail hooks (`hooks/`) enforce the business rules on every
   write.

2. **Standalone, via Streamlit** (`app/streamlit_app.py`) -- a plain Python orchestrator
   (`app/pipeline.py`) that reuses the exact same skill scripts and the exact same
   `hooks/advisory_check.py` guardrail checks, but runs outside Claude Code entirely, calling an
   LLM API directly for the reasoning steps (intake extraction, triage rationale, narrative
   drafting). Coding and duplicate-check stay fully deterministic/local -- no LLM involved there,
   by design, for auditability.

Both paths write to the same `cases/<case_id>.json` shared state and the same
`logs/traceability.jsonl` audit log, and both are subject to the same guardrails.

## Running the Streamlit demo

```bash
python3 -m venv .venv && source .venv/bin/activate   # or use an existing venv
pip install -r requirements.txt

export OPENROUTER_API_KEY="..."   # primary provider
export GROQ_API_KEY="..."         # fallback if OpenRouter errors/rate-limits

streamlit run app/streamlit_app.py
```

This page also runs, unmodified, as one tab of a small shared shell at `../unified_app/app.py`
(sibling of this repo), which puts this PV pipeline and the separate DevGuard prototype
(`../devguard`) behind one Streamlit process/URL for demo convenience -- see
`../unified_app/PROGRESS.md`. Nothing here changes because of that; this repo has no dependency
on it and runs exactly the same standalone.

Streamlit prints a local URL (default `http://localhost:8501`) -- open it in a browser. Paste a
raw AE report, run the pipeline, review the evidence bundle (source excerpt, extracted fields,
MedDRA candidates + source spans, seriousness rationale, duplicate matches, draft narrative), and
use the approval form (reviewer name + APPROVE/EDIT/REJECT + notes) to log a human decision --
that is the *only* way a case reaches `FINAL` (Section 8/10); it is never a bare yes/no.

If neither `OPENROUTER_API_KEY` nor `GROQ_API_KEY` is set, the sidebar shows an error and the
pipeline refuses to run -- coding and duplicate-check work without any key (they're local), but
intake/triage/narrative need a provider.

## Repo layout

| Path | What |
|---|---|
| `CLAUDE.md` | Binding business rules and architecture |
| `docs/literature_survey.md` | Phase 1 literature review |
| `docs/evaluation.md` | Phase 6 metrics/methodology |
| `.claude/agents/` | Sub-agent definitions (Claude Code path) |
| `.claude/skills/` | Shared skills: case I/O, MedDRA lookup, duplicate search, ICH E2A checklist |
| `mcp/pv_tools_server.py` | MCP tool server wrapping the skill scripts (Claude Code path) |
| `hooks/` | PreToolUse/PostToolUse guardrails, shared by both paths |
| `app/` | Standalone orchestrator + LLM client + Streamlit UI |
| `eval/` | Evaluation harness and fixtures (Section 11) |
| `cases/` | Per-case JSON state -- contains PHI, never commit real case files |
| `logs/traceability.jsonl` | Append-only audit trail (Section 7) -- metadata only, no raw narratives |
| `memory/` | Cross-case learnings only -- never patient-identifying detail |

## Evaluation

See `docs/evaluation.md`. Quick run:

```bash
python3 eval/run_eval.py
```

## Status

All 6 planned phases are complete -- see `docs/PROGRESS.md` for the phase-by-phase build log.
