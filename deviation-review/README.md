# DevGuard

Governed agentic deviation review for pharma manufacturing and clinical trials. One engine,
two domain packs. **Prototype only** -- synthetic data, no real patient/product data, no
connection to a live quality or clinical system (`CLAUDE.md` Section 1).

## What this is

A protocol deviation (clinical) or a batch deviation (manufacturing) normally requires a
reviewer to manually gather evidence from several systems, judge severity/impact, draft a
CAPA, and produce an audit-defensible record. DevGuard automates the evidence-gathering,
deterministic-number-crunching, and first-draft-writing steps, and stops at a mandatory human
approval gate before anything is finalized -- the human is always the last word (Rule 3).

## Architecture

```
User request (a deviation_id)
        |
        v
  Supervisor (src/supervisor.py) -- plans, delegates, re-plans, assembles
        | loads the domain pack (packs/manufacturing/ | packs/clinical/)
        v
  +------------+   +-----------+   +------------+   +-------------+
  | Retrieval  |-->| DataCheck |-->| Classifier |-->| CAPADrafter |
  +------------+   +-----------+   +------------+   +-------------+
        |                |               |                 |
        v                v               v                 v
   MCP servers      src/checks/     packs/*/rules.yaml   packs/*/prompts.yaml
   (documents,      (pure Python,   (deterministic       + `analysis_drafting`
   plantdata,        no LLM --      rules engine --       route (prose only)
   equipment,        Rule 2)        severity/impact
   deviations --                   decision, never
   read-only, MCP                  an LLM call)
   Section 6)
        |
        v
  Guardrail hooks (.claude/hooks/, src/guardrails.py) -- Rule 1/3, Section 1 out-of-scope
        |
        v
  HITL approval gate (src/hitl.py) -- the ONLY path to logs/approved/<id>.json
        |
        v
  Trace log (logs/traces/<id>.jsonl, src/trace.py) -- model/tool/evidence/tokens/latency/cost
```

Two parallel front ends drive the same engine:

- **Claude Code**: `.claude/agents/*.md` sub-agents call the MCP servers directly; Claude
  Code's own model *is* the LLM turn, so no separate API call happens on this path.
- **Standalone Python**: `src/agents/*.py` + `src/supervisor.py` call OpenRouter directly via
  `src/llm.py` for the three prose/reasoning steps (retrieval summary, classification
  rationale, CAPA draft) -- the numeric/deterministic steps are identical Python either way.

### Domain packs

| | Clinical | Manufacturing |
|---|---|---|
| Governing doc | Study protocol (`data/Protocol-CT-2026-07.pdf`) | SOP + BMR (`data/SOP-Drying-001.pdf`) |
| Evidence | Subject visits, deviation log | Temp trace, calibration, maintenance, lab results |
| Classify | Major/Minor . Reportable? | Critical/Major/Minor . Product impact? |
| Approver | CTM | QA Head |
| Pack files | `packs/clinical/{rules.yaml,prompts.yaml}` | `packs/manufacturing/{rules.yaml,prompts.yaml}` |

Adding a third domain pack requires **no** change to `src/agents/`, `src/supervisor.py`, or
`.claude/hooks/` -- only a new `packs/<domain>/{rules.yaml,prompts.yaml}` with matching flag
names, and MCP tools that return the same `{value, source}` shape (Section 6).

## Setup

```bash
pip install -r requirements.txt        # openai, pyyaml, pydantic, pypdf, rank_bm25, mcp
cp .env.example .env                   # then fill in OPENROUTER_API_KEY
export OPENROUTER_API_KEY="sk-or-..."
```

Every route in `config/models.yaml` is pinned to a specific model ID (Rule 5); this account's
OpenRouter workspace guardrail policy currently allows only the `analysis_drafting` route
(`anthropic/claude-sonnet-5`) through -- every other route (`triage_guardrail`, `retrieval`,
`extraction`, `supervisor_planning`, `eval_judge`) returns a 404 until that policy is relaxed at
[openrouter.ai/workspaces/default/guardrails](https://openrouter.ai/workspaces/default/guardrails).
This is an account setting, not a code bug: every LLM call in this repo degrades gracefully
(returns `None` + the captured error) rather than crashing when a route is blocked, so the
demo below still runs end to end -- CAPA/narrative drafting (the one route that works) is also
the one step Rule 2 requires to be prose, so the deterministic parts of the pipeline are
entirely unaffected either way.

## Demo script (reproduces the fixed case from `PROGRESS.md`)

The fixed manufacturing case: batch B-2291, drying step spec 60C +/-5C for 4h, actual peak 72C
for 20 minutes, on Oven-04 (14 months since its last service against a 12-month schedule), with
a failing moisture-content lab result -- and two other batches (B-2293, B-2296) that share the
overdue equipment window but pass their own lab tests.

```bash
# 1. Deterministic checks in isolation
python3 -m unittest src.checks.test_checks -v

# 2. Full pipeline: retrieval -> data check -> re-plan -> classify -> draft, with a trace
python3 -m src.supervisor DEV-2026-0091 --save --trace

# 3. Render the trace table for that run
python3 -m src.trace DEV-2026-0091

# 4. Human approval gate -- this is the ONLY way anything reaches logs/approved/
python3 -m src.hitl DEV-2026-0091 --approver "J. Alvarez" --decision APPROVE --notes "confirmed"
cat logs/approved/DEV-2026-0091.json   # status: FINAL, with the approval record attached
```

The same commands work on the fixed clinical case (subject S-1042's Visit 3, 9 days outside a
5-day window) by swapping the deviation id:

```bash
python3 -m src.supervisor DEV-2026-0034 --save --trace
python3 -m src.trace DEV-2026-0034
python3 -m src.hitl DEV-2026-0034 --approver "R. Patel" --decision APPROVE
```

Try `--decision REJECT` instead of `APPROVE` and note that `logs/approved/` is never written --
finalisation stays blocked (Rule 3).

### Evaluation

```bash
python3 -m eval.run_eval --sample 6
```

Reports accuracy (Classifier decision vs. `eval/golden_set.json`, generated from all 28 real
deviations in `data/deviations.csv`), citation-rate (how much of a case's evidence a live CAPA
draft actually cites), and refusal-rate (`eval/redteam.py`'s 5 adversarial prompts trying to
get the drafter to make an out-of-scope release/rejection or causality call).

### Individual sub-agents (standalone)

```bash
python3 -m src.agents.retrieval DEV-2026-0091
python3 -m src.agents.data_check DEV-2026-0091
python3 -m src.agents.classifier DEV-2026-0091
python3 -m src.agents.capa_drafter DEV-2026-0091
```

### Inside Claude Code

Open this repo as a Claude Code project (`.mcp.json` registers the 4 read-only MCP servers,
`.claude/settings.json` wires the guardrail hooks) and invoke the `retrieval`, `datacheck`,
`classifier`, and `capadrafter` sub-agents (`.claude/agents/*.md`) in that order for a
`deviation_id`. No separate API key is needed on this path -- Claude Code's own model runs the
prose steps directly.

## Repo layout

| Path | What |
|---|---|
| `CLAUDE.md` | Binding architecture/rules for this project |
| `PROGRESS.md` | Phase-by-phase build log (read this first after any `/clear`) |
| `config/models.yaml` | Pinned OpenRouter model routing (Rule 5) |
| `data/` | Synthetic CSVs + 2 PDFs (Rule 4: synthetic data only) |
| `mcp_servers/` | 4 read-only MCP servers (documents/plantdata/equipment/deviations) |
| `src/checks/` | Deterministic excursion/service-breach/visit-window logic, no LLM |
| `src/agents/` | Standalone Python versions of Retrieval/DataCheck/Classifier/CAPADrafter |
| `src/supervisor.py` | Plan/delegate/re-plan/assemble over one threaded case state |
| `src/guardrails.py` | Rule 1/3 + Section 1 out-of-scope checks |
| `src/hitl.py` | The only code path that can finalize a case |
| `src/trace.py` | Per-step observability (model/tool/evidence/tokens/latency/cost) |
| `packs/` | Domain-specific rules.yaml + prompts.yaml (clinical, manufacturing) |
| `.claude/agents/` | Claude-Code-path sub-agent definitions with tool allowlists |
| `.claude/hooks/` | PreToolUse/PostToolUse guardrail hooks |
| `eval/` | Golden set, redteam prompts, evaluation harness |
| `logs/cases/`, `logs/approved/`, `logs/traces/` | Working cases, finalized cases, trace JSONL |

## Production swap-in table

Everything below is a deliberate prototype shortcut (per `CLAUDE.md`'s "Out of scope" /
"Deferred" sections) -- this table is the map from what exists today to what a real deployment
would need instead. None of this is implemented here.

| Component | This prototype | Production swap-in |
|---|---|---|
| Data sources | 5 synthetic CSVs + 2 synthetic PDFs (`data/`, `scripts/gen_data.py`) | Real LIMS/MES/EDC/CTMS connectors behind the same MCP tool interface (`{value, source}`) |
| Retrieval | BM25 over 2 short PDFs (`rank_bm25`) | Hybrid (BM25 + vector) retrieval over the full SOP/protocol corpus, per the deferred open item |
| MCP servers | 4 local stdio servers reading flat files | Same tool contract, backed by authenticated connectors to the real systems above |
| Auth | None (local dev, no external auth) | Real connector auth (documented in `PROGRESS.md`'s Deferred section as swap-in only) |
| Model routing | OpenRouter, one account, guardrail-restricted in this environment | Direct-to-provider or an enterprise OpenRouter workspace with the full route table unblocked |
| Case storage | `logs/cases/`, `logs/approved/` (flat JSON files) | A real case-management/QMS or eTMF system as the system of record |
| Approval identity | `--approver` is a free-text CLI argument | SSO-backed reviewer identity, tied to an actual QA Head / CTM role |
| Audit trail | `logs/traces/*.jsonl`, local, unsigned | Centralized, tamper-evident audit log (e.g. WORM storage), per Section 7-equivalent audit needs |
| Scale | Single-case CLI invocations | A queue/worker model processing deviations as they're filed |

## Status

All 11 phases in `PROGRESS.md` are complete.
