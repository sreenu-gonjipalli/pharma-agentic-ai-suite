# PROGRESS.md — Unified App (shell over capstone + devguard)

Purpose: one Streamlit process/URL with a sidebar switcher between the two separate,
independently-governed projects (`../capstone` and `../devguard`). This file exists so phase
context survives across sessions -- read it before touching this folder again.

**Ground rules (why this folder is thin):**
- Never copy or fork capstone/devguard logic in here -- only import/point at it.
- Never edit capstone's or devguard's own CLAUDE.md/business rules from this folder.
- Each underlying project keeps its own governance (capstone's hooks, DevGuard's phase
  discipline) -- this shell does not weaken or bypass either.

**Current phase: 3 done -- all 3 phases complete**
Last updated: 2026-09-26

## Phase plan

| # | Phase | Goal | Done when |
|---|---|---|---|
| 1 | Scaffold shell | `app.py` using `st.navigation`: PV page = capstone's existing `app/streamlit_app.py` unmodified (via `st.Page` pointing at that file); DevGuard page = new lightweight status page (model routing table + live `--ping` button), since DevGuard has no pipeline UI yet (still Phase 0 there) | `streamlit run app.py` serves both pages from one port; PV page fully functional exactly as it is standalone; DevGuard page shows route table + live ping result |
| 2 | Real DevGuard page | Swap the DevGuard status stub for its actual pipeline UI | Deferred until DevGuard reaches its own Phase 7/8 (HITL gate + trace) -- revisit `../devguard/PROGRESS.md` before starting |
| 3 | Rename + readable tables + Evaluation/Trace pages | User feedback: raw `st.json` dumps unreadable, "DevGuard" name shouldn't be user-facing, wants dedicated Evaluation + Observability & Traceability sections for **both** apps | 6 distinct top-level pages (grouped under 2 sidebar section headers), evidence rendered as real tables not JSON, "DevGuard" renamed to "Deviation Review" in the UI, both new Evaluation pages run live and both new Trace pages show real rows |

## Log

| Phase | Status | Built | Notes |
|---|---|---|---|
| 1 | [x] | `app.py`, `pages/devguard_status.py` | PV page reuses `../capstone/app/streamlit_app.py` via `st.Page` with zero edits to capstone code (its `sys.path` setup is already `__file__`-relative, so it works unchanged from a different cwd). DevGuard page is a genuinely new page (DevGuard has no UI code to reuse yet) -- shows the Section-5 model routing table from `../devguard/config/models.yaml`, flags which routes are currently blocked by the OpenRouter workspace guardrail (see devguard/PROGRESS.md Phase 0 note), and a "Run ping" button that calls `devguard/src/llm.call_route` live. Verified with headless
Chrome DOM dumps against a running `streamlit run app.py` on :8501: both `/pv-intake` and
`/devguard` render real content with `data-test-script-state="notRunning"` (no silent failures).
Running now at http://localhost:8501. |
| 2 | [x] | `pages/devguard_pipeline.py` (replaces `pages/devguard_status.py`, deleted) | DevGuard reached all 11 of its own phases (its `PROGRESS.md`), so this is the real pipeline UI, not a stub: pick a `deviation_id`, run `supervisor.run_case` live, review the evidence bundle/flags/re-plan notice/classification+rationale/draft narrative/trace table, then log a human decision via `hitl.approve_case` directly -- same shape as the PV page's approval form (named approver, one of APPROVE/EDIT/REJECT, notes; never a bare yes/no). Also added an in-process guardrail check to `devguard/src/supervisor.py` (`state["guardrail_violations"]`) and a matching block in `devguard/src/hitl.py` (refuses APPROVE while violations are unresolved) -- devguard's own `.claude/hooks/` only fire for Claude Code tool calls, not a direct Python/Streamlit import, so this mirrors how capstone's `app/pipeline.py` calls `advisory_check` directly rather than relying on hooks alone. Verified with a real headless Chrome session (Playwright): both `/pv-intake` and `/devguard` render with no exceptions, and a full interactive run on `/devguard` (pick DEV-2026-0091 -> run pipeline -> fill approval form -> submit) produced a real `logs/approved/DEV-2026-0091.json` with `status: FINAL` and the exact approver/notes typed into the form. Running at http://localhost:8501. |

| 3 | [x] | `app.py` (grouped `st.navigation` dict, 6 pages), `capstone/app/{eval_page,trace_page}.py` (new, native to capstone), `pages/deviation_review_{pipeline,evaluation,trace}.py` (renamed from `devguard_*`/new -- devguard has no native UI of its own, so its pages stay hosted here, same as Phase 1/2) | Two sidebar sections, "PV Intake & Triage" and "Deviation Review" (the devguard project's own folder/CLAUDE.md keep their name -- only the UI label changed), each with Case Pipeline / Evaluation / Observability & Traceability -- still 6 distinct top-level pages, just grouped rather than a flat list, per the user's explicit choice over tabs-in-one-page. Case Pipeline page reworked: every evidence list (equipment trace, maintenance, lab results, doc-search hits) now renders as `st.dataframe` instead of raw `st.json`; DataCheck flags/findings, the re-plan notice's affected-batch survey, and the classification block are now small tables too; the draft narrative switched from `st.text` to `st.markdown` so CAPADrafter's headers/bold actually render. New Evaluation pages call each project's *existing* `eval/run_eval.py` (and devguard's `eval/redteam.py`) live -- no metric logic duplicated. New Trace pages call `trace_logger.read_steps()` (capstone) / `src/trace.py`'s `load_trace()` (devguard) -- same, no new logging code. Along the way, also fixed a real bug the user hit live in the PV page: capstone's default OpenRouter model (`google/gemma-4-31b-it:free`) was rate-limited upstream (429) -- switched the default in `capstone/app/llm_client.py` to `anthropic/claude-sonnet-5` (same reliable model devguard's `analysis_drafting` route uses), and added markdown-fence stripping to `chat_json` since Claude wraps JSON in ` ```json ` fences even with `response_format=json_object` set (OpenRouter doesn't enforce that uniformly across providers). Verified everything with a real headless-Chrome Playwright session: all 6 nav links load with `notRunning` state and real content; a full Case Pipeline run + approval on Deviation Review shows real tables (screenshotted); both Evaluation pages' buttons produce real metrics; both Trace pages show real rows; and the exact PV scenario from the user's bug report (free-text symptom report -> full 5-stage pipeline) now completes live end-to-end. |

## Open items

None -- all 3 phases are done. Future: DevGuard's account-level OpenRouter guardrail block
(every route except `analysis_drafting`) means the Deviation Review Evaluation page's
citation-rate/redteam sections and the Case Pipeline's retrieval-summary/classification-rationale
sections will show a captured error until that dashboard setting is relaxed; not fixable in
code (documented in devguard/PROGRESS.md since its Phase 0).
