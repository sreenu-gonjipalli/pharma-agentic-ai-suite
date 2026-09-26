# CLAUDE.md — Agentic AI for Pharmacovigilance Case Intake & Triage

Binding instruction set for this repo: architecture, business rules, coding standards, hard
constraints. Grounded in `docs/literature_survey.md`.

## 1. Business Problem & Scope

**Function:** Pharmacovigilance — Adverse Event (AE) / ICSR case processing.
**Problem:** Intake, MedDRA coding, triage, duplicate-check, and narrative drafting consume most PV
capacity today and are manual, unstructured, time-critical.

**Does:** Takes a raw AE report (call-center text, email, literature excerpt) → structured fields →
advisory MedDRA codes → advisory seriousness/expectedness → duplicate check → draft narrative →
mandatory human approval before anything is `FINAL`.

**Is NOT:** a validated clinical/regulatory system; connected to a live safety DB or E2B gateway;
authorized to submit a real ICSR; a replacement for PV/medical-review judgment. Every clinical or
regulatory output is a draft pending human sign-off.

## 2. Architecture

```
User Input → Orchestrator (plans, delegates, owns case state)
   ├─ pv-intake     (extract fields)
   ├─ pv-coding     (MedDRA candidates)
   ├─ pv-triage     (seriousness/expectedness)
   ├─ pv-duplicate  (duplicate search)
   └─ pv-narrative  (draft narrative)
        → Guardrail Check (hooks) → Evidence Bundle → Human Approval Gate → Final Case + Audit Log
```

- **Orchestrator**: plans/delegates/tracks state only — never extracts, codes, or drafts itself.
- **Sub-agents**: narrow scope, own tools/skills, called only by the orchestrator (no peer-to-peer
  calls).
- **Shared case state**: one JSON object per case, threaded through every agent (§5).

## 3. Business Rules & Constraints

1. Seriousness/expectedness labels are advisory: tag `SUGGESTED — PENDING HUMAN REVIEW`, never final.
2. MedDRA coding is advisory: return top-N candidates with confidence, never one silent choice.
3. No autonomous submission — no tool may transmit/file a case to any external system. None should
   be added without a separate, explicit human decision outside this codebase.
4. No fabrication — missing fields are `NOT REPORTED`, never inferred.
5. PHI handling — treat all input as PHI; audit log (§7) stores structured metadata, not full
   free-text narratives.
6. Every suggested code/flag/match carries a pointer to its source text span for reviewer verification.
7. Context of use per agent is fixed by §4 below; expanding an agent's scope requires editing this
   file first, not ad hoc prompting.

## 4. Sub-Agents (`.claude/agents/`)

| Agent | Responsibility | Output |
|---|---|---|
| `pv-intake` | Parse raw text → patient/drug/event/dates/reporter | fields + `NOT REPORTED` flags |
| `pv-coding` | MedDRA PT/LLT candidates per event | ranked candidates + confidence + source span |
| `pv-triage` | Seriousness (ICH E2A) + expectedness | advisory label + rationale |
| `pv-duplicate` | Search local case store | match list + similarity score |
| `pv-narrative` | Draft plain-language narrative | draft text |

## 5. State / Context / Memory

- Case state: `cases/<case_id>.json`, holds every agent's fields + `history[]` (who wrote what, when).
- Cross-case learnings (naming conventions, recurring duplicate clusters) → `memory/` project
  memory only; never patient-identifying detail.
- Agents read current state before acting, append — never overwrite another agent's fields.

## 6. Guardrails (hooks — Phase 4)

- Pre-tool-call hook blocks any external-submission-like call and file writes outside `cases/`/`logs/`.
- Post-agent-output hook rejects seriousness/coding output missing the advisory tag or source span.
- No case reaches `FINAL` without a logged human approval event (§8).

## 7. Observability & Traceability

```
User Request → Orchestrator Plan → Sub-agent → Skill/Tool → Evidence →
Guardrail Check → Human Approval → Final Output
```

Append-only `logs/traceability.jsonl`: one JSON line per step (agent, action, tool/skill, redacted
input, output, guardrail result, timestamp). Evaluated in Phase 6.

## 8. Human-in-the-Loop

Before `FINAL`, a reviewer sees an **evidence bundle**: source excerpt, extracted fields, MedDRA
candidates + source spans, seriousness rationale, duplicate results, draft narrative. Reviewer
chooses `APPROVE` / `EDIT` / `REJECT`; only `APPROVE` reaches `FINAL`. Never reduce this to a bare
yes/no button — that reintroduces automation bias (literature survey §2.4).

## 9. Coding Standards

- Python, stdlib-first, no unnecessary dependencies.
- Comments explain *why*, never *what*; skip if not non-obvious.
- One module/prompt per sub-agent — no monolithic "do everything" agent.
- No speculative config, retries, or fallbacks beyond current scope.

## 10. AI Governance Summary

- **Privacy**: PHI-aware; logs hold metadata, not raw narratives.
- **Access control**: only the reviewer role can mark `FINAL` (simulated via CLI/UI prompt).
- **Accountability**: every `FINAL` case links to its specific human approval log entry.
- **Responsible AI**: outputs advisory by construction, per FDA/EMA human-centric principles
  (literature survey §2.3).

## 11. Evaluation

Metrics (detail in `docs/evaluation.md`): MedDRA coding precision/recall, seriousness-flag
agreement, duplicate-detection precision/recall, guardrail-violation catch rate on adversarial
input, end-to-end latency per case.
