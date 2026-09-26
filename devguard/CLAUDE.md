# CLAUDE.md — DevGuard

Governed agentic deviation review for pharma. One engine, two domain packs.

> **Read this file + `PROGRESS.md` only. Do not read other files unless the current phase names them.**

---

## 1. Project

**Problem.** A protocol deviation (Clinical) or a batch deviation (Manufacturing) requires a reviewer to manually gather evidence from several systems, judge severity/impact, draft a CAPA, and produce an audit-defensible record. Slow, inconsistent, and the reasoning is rarely captured.

**Solution.** A Supervisor plans the review, sub-agents retrieve evidence via MCP, deterministic code computes facts, an LLM drafts narrative, hooks enforce guardrails, and a qualified human approves before anything is finalised.

**Users.** Clinical Data Reviewer / QA Investigator (primary) . CTM or QA Head (approver) . Auditor (consumes trace).

**Out of scope.** Batch release/rejection. Causality or medical judgment. Any real patient or personal data.

---

## 2. Non-negotiable rules

1. **No unsupported claims.** Every factual statement in output must carry an evidence ID from an MCP call. If evidence is missing -> **escalate, never infer**.
2. **Numbers from code, prose from LLM.** Never let the model compute an excursion, a visit window or a duration.
3. **Human approval is blocking.** No final output without a recorded approver identity + timestamp.
4. **Synthetic data only.**
5. **Pin model IDs.** Exact OpenRouter IDs in config; never `:free` in the demo path; prompt logging disabled.
6. **Agent is read-only over evidence.** MCP servers expose no write tools.

---

## 3. Architecture

```
User request
     |
Supervisor (plan -> delegate -> re-plan)
     | loads domain pack (clinical | manufacturing)
[ Retrieval | DataCheck | Classifier | CAPADrafter ]   <- sub-agents
     | MCP: documents . plantdata . equipment . deviations
Deterministic checks -> Guardrail hooks -> HITL gate -> Trace log
```

### Domain packs

| | Clinical | Manufacturing |
|---|---|---|
| Governing doc | Study protocol | BMR + SOP |
| Evidence | Subject visits, deviation log | Temp trace, calibration, maintenance, lab results |
| Classify | Major/Minor . Reportable? | Critical/Major/Minor . Product impact? |
| Approver | CTM | QA Head |

---

## 4. Layout

```
devguard/
├── CLAUDE.md  PROGRESS.md  README.md  .mcp.json  .env.example
├── config/models.yaml            # OpenRouter routing
├── data/                         # synthetic CSV/PDF
├── mcp_servers/                  # doc, data, equipment, deviation
├── packs/clinical/ manufacturing/  # rules.yaml + prompts
├── src/  supervisor.py  agents/  skills/  checks/  guardrails.py
│         hitl.py  trace.py  llm.py
├── .claude/agents/  skills/  hooks/  settings.json
├── eval/golden_set.json  run_eval.py  redteam.py
└── logs/traces/
```

---

## 5. Model routing (OpenRouter)

| Step | Model | $/1M in-out |
|---|---|---|
| Triage, guardrail check | openai/gpt-5.6-luna | 0.20 / 1.20 |
| **Supervisor planning** | anthropic/claude-opus-5 | 5 / 25 |
| Retrieval (long ctx) | z-ai/glm-5.3-flash | 0.15 / 0.50 |
| Extraction, tool exec | deepseek/deepseek-v4.1-flash | 0.10 / 0.50 |
| Analysis, drafting | anthropic/claude-sonnet-5 | 2 / 10 |
| Eval judge (cross-family) | openai/gpt-6-astra | 10 / 50 |

Rule: spend on the plan, save on the pass-through.

---

## 6. Standards

Python 3.11 . type hints on public functions . ruff clean . Pydantic models for all agent I/O . structured JSON logs . no secrets in code . no network calls outside OpenRouter + local MCP.

**Every MCP response must include:**
```json
{"value": "...", "source": {"server": "...", "tool": "...", "record_id": "...", "file": "...", "retrieved_at": "..."}}
```

---

## 7. Token discipline -- read this before every phase

- Work **one phase at a time**. Do not look ahead.
- Read only files listed in that phase's Touches.
- Do not re-read files already summarised in PROGRESS.md.
- Do not refactor earlier phases unless the phase says so.
- After each phase: update PROGRESS.md, then **stop and wait**.
- Keep PROGRESS.md under 150 lines -- compress old entries to one line each.

---

## 8. Definition of done (per phase)

Code runs . phase test passes . PROGRESS.md updated . no rule in Section 2 violated.
