# Build Progress — Agentic AI PV Case Processing Capstone

Read this file first after any `/clear`. It is the single source of truth for what's built and
what's next. Also read `CLAUDE.md` for architecture/rules before implementing any phase.

| Phase | Deliverable | Status | Files |
|---|---|---|---|
| 1 | Literature survey | ✅ Done | `docs/literature_survey.md` |
| 2 | CLAUDE.md | ✅ Done | `CLAUDE.md` |
| 3 | Sub-agents + Skills | ✅ Done | `.claude/agents/*` (pv-intake, pv-coding, pv-triage, pv-duplicate, pv-narrative), `.claude/skills/*` (case-state-io, meddra-coding-lookup, ich-e2a-seriousness, duplicate-case-search) |
| 4 | Hooks + guardrails | ✅ Done | `.claude/settings.json`, `hooks/pretool_guard.py`, `hooks/posttool_guard.py`, `hooks/advisory_check.py`, `case_store.py` `approve` subcommand |
| 5 | MCP/tool wiring + state/memory | ✅ Done | `mcp/pv_tools_server.py`, `cases/`, `memory/`, updated `.claude/agents/*` + `.claude/skills/*/SKILL.md` |
| 6 | Evaluation + Observability/Traceability + README | ✅ Done | `docs/evaluation.md`, `logs/`, `README.md` |
| 7 | Standalone app + Streamlit UI (outside Claude Code) | ✅ Done | `app/pipeline.py`, `app/llm_client.py`, `app/trace_logger.py`, `app/streamlit_app.py`, `requirements.txt` |

### Phase 4 notes

- `hooks/pretool_guard.py` (PreToolUse, matches `Bash|Write`): blocks any Bash command that looks
  like an external-submission/transmission call (Business Rule 3) and any tool name matching the
  same pattern; blocks `Write` outside `cases/`/`logs/`/`memory/`; blocks `Write` to
  `logs/traceability.jsonl` (must stay append-only, §7).
- `hooks/posttool_guard.py` (PostToolUse, matches `Bash|Write|mcp__pv-tools__case_update|mcp__pv-tools__case_init`):
  after any tool call that could have written a case file, re-reads that case off disk and
  rejects (exit 2) if `coding`/`triage` is missing the advisory tag, a source_span, confidence, or
  rationale (Business Rules 1/2/6). Shared check logic lives in `hooks/advisory_check.py`.
- Human approval gate (§8/§10): `case_store.py approve --case-id … --reviewer … --decision
  APPROVE|EDIT|REJECT` is the *only* code path that can set `status: FINAL`. It is not registered
  as an MCP tool and is not in any sub-agent's tool list — it's a human-run CLI command.
- All hooks tested manually with compliant/non-compliant payloads — see conversation for cases.

### Phase 5 notes

- `mcp/pv_tools_server.py` (FastMCP, stdio transport, registered in `.claude/settings.json` as
  the `pv-tools` server) wraps the existing skill scripts as structured tools: `case_init`,
  `case_read`, `case_update`, `meddra_lookup_terms`, `duplicate_search_case`. It imports the same
  Python functions the Bash fallback path uses (`case_store.py`, `meddra_lookup.py`,
  `duplicate_search.py`) — one implementation, two call paths.
- No submission/transmission tool exists on this server, by design — Business Rule 3 is enforced
  structurally, not just by a hook.
- Updated every `.claude/agents/*.md` to list the relevant `mcp__pv-tools__*` tools and call them
  as the preferred path (Bash + the underlying scripts kept as fallback).
- Created `cases/` and `memory/` with short READMEs describing what belongs in each (§5).
- Requires `pip install "mcp<2"` (FastMCP API) — installed in the active venv.

Update the Status column (⬜ → 🔄 → ✅) and the Files column as each phase completes.

### Phase 6 notes

- `docs/evaluation.md` documents the 5 Section-11 metrics and how `eval/run_eval.py` computes
  them against `eval/fixtures.json` (4 hand-written cases). Guardrail catch rate needs no LLM;
  the other 4 metrics run `app/pipeline.py` end-to-end.
- Found and fixed a real guardrail bug via this harness: `validate_triage` originally required
  *any* source_span anywhere in the output, which incorrectly rejected legitimate non-serious
  cases where every ICH E2A criterion is `NOT SUPPORTED` (nothing to cite). Now only a criterion
  actually marked `SUPPORTED` must carry the span backing it up (`hooks/advisory_check.py`).
  Also added `validate_intake` (Business Rule 4 fabrication check: any non-`NOT REPORTED` value
  needs a source_span) and `validate_narrative` (mandated disclaimer line) to the same shared
  module, wired into `validate_case_sections` so the existing `posttool_guard` hook enforces them
  too.
- `logs/traceability.jsonl` (append-only, created on first pipeline run) is written by
  `app/trace_logger.py` -- one line per step, metadata only (redacted/length-only for raw report
  text and narrative text, never the full PHI-bearing content), per Section 5/7.
- Top-level `README.md` added, covering both run paths (Claude Code sub-agents vs. the
  standalone Streamlit app added in Phase 7) and repo layout.

### Phase 7 notes (standalone app, added beyond the original 6-phase plan at user request)

- The Claude-Code sub-agent pipeline has no standalone entry point outside a Claude Code session.
  Phase 7 adds one: `app/pipeline.py` is a plain-Python orchestrator that reuses the *same*
  skill scripts (`case_store`, `meddra_lookup`, `duplicate_search`) and the *same*
  `hooks/advisory_check.py` guardrail validators, but is driven by a direct LLM API call
  (`app/llm_client.py`) instead of a Claude Code agent turn -- so it can run headless or behind
  `app/streamlit_app.py`.
- `app/llm_client.py`: tries OpenRouter first (`OPENROUTER_API_KEY`), falls back to Groq
  (`GROQ_API_KEY`) on any error (rate limit, model deprecation, etc.) -- both are OpenAI-API
  compatible, so one thin wrapper covers both. Default models were picked by live-testing which
  free/available models actually return valid JSON in this environment: OpenRouter
  `google/gemma-4-31b-it:free`, Groq `openai/gpt-oss-20b`. Override with `OPENROUTER_MODEL` /
  `GROQ_MODEL` env vars.
- Coding and duplicate-check remain fully deterministic (no LLM) in the standalone path too --
  only intake extraction, triage rationale, and narrative drafting call an LLM, matching the
  literature review's recommendation (Section 2.1) to keep constrained extraction separate from
  open-ended generation.
- Discovered during testing: the fixed intake JSON schema (patient/drugs/events/dates/reporter)
  dropped hospitalization detail that didn't fit any of those fields, which then caused
  `pv-triage` to miss the hospitalization criterion. Fixed by having `run_intake` retain the
  verbatim raw report text as `intake.raw_report_text` (not regenerated by the LLM) so triage and
  narrative always have the full source text, not just the fixed-schema fields -- also directly
  supports Business Rule 6 (source-span verifiability).
- `app/streamlit_app.py`: paste raw report text -> run pipeline -> evidence bundle (source
  excerpt, extracted fields, coding candidates, triage criteria, duplicate matches, draft
  narrative) -> human approval form (reviewer name + APPROVE/EDIT/REJECT radio + notes, never a
  bare yes/no per Section 8) that calls `case_store.approve_case` directly -- the only path to
  `FINAL`, exactly as in the Claude-Code path, and still not exposed as anything an agent/LLM can
  call.
- Run: `pip install -r requirements.txt`, set `OPENROUTER_API_KEY` and/or `GROQ_API_KEY`, then
  `streamlit run app/streamlit_app.py`.
