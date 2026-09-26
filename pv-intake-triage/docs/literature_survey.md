# Literature Survey

## Agentic AI for Pharmacovigilance Case Intake, Triage & MedDRA Coding

**Capstone Project — Agentic AI in the Pharmaceutical Industry**
**Function selected:** Pharmacovigilance (Drug Safety) — Adverse Event (AE) Case Processing
**Date:** 2026-09-26

---

## 1. Problem Context

Case processing — intake, triage, coding, and narrative drafting of Individual Case Safety Reports
(ICSRs) — consumes up to two-thirds of a typical pharmacovigilance (PV) department's operating
resources, making it the single largest cost driver in drug safety operations (IntuitionLabs, 2025).
Reports arrive from multiple channels (call centers, spontaneous reports, literature, clinical trials)
in unstructured or semi-structured form and must be triaged for seriousness, coded to MedDRA
terminology, checked for duplicates, and turned into a structured ICSR (E2B format) — a
labor-intensive, error-prone, and time-critical workflow subject to strict regulatory timelines
(e.g., 15-day expedited reporting for serious unexpected AEs).

This is the business problem selected for the capstone: **can an agentic AI system plan, delegate,
use tools, and produce an auditable, human-approved AE case record faster and more consistently
than the current manual/RPA-based process, without compromising patient safety or regulatory
compliance?**

---

## 2. Literature Review

### 2.1 LLMs and Agentic AI in Pharmacovigilance

- **Venugopal et al., "Large language models-powered agentic AI design and implementation in
  pharmacovigilance — a narrative review,"** *Journal of Medical Artificial Intelligence* (received
  Sept 2024, published Jan 2026). Reviews literature from Jan 2022–Apr 2025 and concludes that
  LLM-based agentic systems can meaningfully augment (not replace) human PV capacity across intake,
  coding, and signal detection, provided outputs remain traceable and reviewable.
  https://jmai.amegroups.org/article/view/10388/html

- **Systematic review, "Large Language Models in Adverse Drug Reaction Detection and
  Pharmacovigilance: A Systematic Review of Current Applications, Challenges, and Future
  Directions,"** *PMC*, 2025. Documents a sharp rise in LLM-in-PV studies from 2024 onward and
  recommends: (a) reporting aligned with TRIPOD-LLM, (b) system designs that separate retrieval
  failures from generation failures, and (c) explicit distinction between constrained extraction
  tasks (e.g., MedDRA coding) and open-ended generative tasks (e.g., narrative drafting) — the
  former being far safer to automate than the latter.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC13465311/

- **"Agentic AI in Pharmacovigilance: A Position Paper on Opportunities [and Risks],"** SCITEPRESS,
  2026. Frames agentic AI in PV by its autonomy, goal-directed behavior, and reasoning; identifies
  MedDRA auto-coding, ICSR data aggregation, and automated regulatory-submission drafting as the
  highest-value near-term use cases, while flagging that agents must "adapt to changing regulatory
  requirements" (FDA/EMA/ICH) — implying configuration must live outside frozen model weights.
  https://www.scitepress.org/Papers/2026/143987/143987.pdf

- **IntuitionLabs technical/industry overviews (2025–2026)** describe end-to-end agentic PV
  pipelines: report receipt → data extraction → AE coding → seriousness assessment → duplicate
  check → narrative drafting, run largely autonomously with human sign-off. Cited milestones: FDA's
  internal "Elsa" assistant (built on Claude) for reviewer summarization; CIOMS Working Group XIV's
  Dec 2025 report on AI in Pharmacovigilance; and vendor systems (ArisGlobal LifeSphere NavaX, Tech
  Mahindra/NVIDIA) reporting 30–65% gains in case-processing throughput and data accuracy (vendor-
  reported, not independently benchmarked).
  https://intuitionlabs.ai/articles/ai-agents-pharmacovigilance

**Implication for design:** the literature converges on a pipeline decomposition (intake →
extraction → coding → seriousness/triage → duplicate check → narrative → human review) rather than
a single end-to-end model call — directly motivating this project's sub-agent architecture.

### 2.2 Agentic AI Architectures and Multi-Agent Orchestration

- **Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models,"** ICLR 2023.
  Introduces the interleaved reason→act→observe loop that underlies modern tool-using agents; the
  basis for treating each sub-agent's tool call as an observable, loggable step rather than a black
  box.

- **Schick et al., "Toolformer: Language Models Can Teach Themselves to Use Tools,"** NeurIPS 2023.
  Establishes the pattern of models self-invoking external APIs (calculators, search, etc.) —
  precursor to the structured tool/skill invocation used here (MCP, custom skills).

- **AutoGPT / AutoGen family** (Microsoft AutoGen, 2023 onward). AutoGen pioneered conversational
  multi-agent frameworks where agents exchange messages autonomously; later systems (CrewAI 2025,
  LangGraph 2025) formalize role-based orchestration and DAG/graph-based workflows with explicit
  human-in-the-loop checkpoints and conditional/retry edges.

- **"Multi-Agent Collaboration with LLMs: A Survey,"** 2024. Comprehensive taxonomy of
  supervisor/orchestrator patterns, agent communication protocols, and shared-state mechanisms —
  directly informing this project's Orchestrator → {Intake, Coding, Triage, Narrative} sub-agent
  structure and the use of a shared case-state object passed between agents.

**Implication for design:** a supervisor/orchestrator agent should decompose the AE case workflow
into specialized, narrowly-scoped sub-agents (each with its own tools/skills) rather than one
generalist agent — improving auditability, reducing hallucination surface area, and matching how
real PV teams already divide labor (intake specialists, coders, medical reviewers).

### 2.3 Regulatory and Governance Landscape

- **FDA, "Considerations for the Use of Artificial Intelligence to Support Regulatory
  Decision-Making for Drug and Biological Products"** (draft guidance, Jan 2025). Introduces a
  seven-step, risk-based credibility assessment culminating in a human "fitness-for-purpose"
  judgment, and requires a documented "context of use" for any AI model before development —
  analogous to a predetermined change/application scope.

- **EMA, "Reflection Paper on the Use of Artificial Intelligence in the Medicinal Product
  Lifecycle"** (2024) and the EMA AI Workplan. Requires that AI/ML systems used by marketing
  authorization holders be transparent, validated, and continuously monitored throughout the
  product lifecycle.

- **FDA–EMA Joint Ten Guiding Principles for AI in Drug Development** (published Jan 2026,
  building on the 2024/2025 papers above). Principle 1 establishes human-centric, risk-based design;
  the set collectively requires proportional validation, a documented context of use, adherence to
  applicable standards, robust data governance, and multidisciplinary oversight. Not binding law,
  but the clearest cross-agency signal of expected guardrail design.

- **CIOMS Working Group XIV, Final Report on AI in Pharmacovigilance** (Dec 2025). Industry/
  regulator consensus body specifically addressing AI use in case processing and signal
  management.

- **EU AI Act (full effect Aug 2026) and EMA Annex 22** — first regulatory framework explicitly
  governing AI in drug production/PV; reinforces that safety-relevant AI outputs require
  traceability to accountable humans.

**Implication for design:** the system must (a) declare an explicit, narrow context of use per
agent, (b) never auto-submit a regulatory report without human sign-off, (c) log every tool call
and model output for audit, and (d) treat "human-in-the-loop" as a hard gate rather than an
optional review step — directly shaping the guardrails and approval gate specified in `CLAUDE.md`.

### 2.4 Human Oversight Models

- Industry analyses (2025–2026) distinguish **human-in-the-loop** (human approves before action),
  **human-on-the-loop** (human monitors, can intervene), and **human-in-command** (human retains
  final authority but delegates execution) — and warn of **automation bias**, where poorly designed
  oversight (e.g., a rubber-stamp "Approve" button with no evidence shown) is worse than no oversight
  at all.

**Implication for design:** the human approval step for this project must present the underlying
evidence (source report excerpt, extracted fields, MedDRA code candidates with confidence, duplicate
check results) alongside the recommendation — not just a final answer to click through — to avoid
automation bias.

---

## 3. Summary Table

| Theme | Key Source(s) | Design Decision Adopted |
|---|---|---|
| LLM/agentic PV pipelines | Venugopal 2026; PMC systematic review 2025; IntuitionLabs | Decompose case processing into intake → extraction → coding → triage → duplicate-check → narrative sub-agents |
| Extraction vs. generation risk | PMC systematic review 2025 | Treat MedDRA coding/seriousness as constrained, verifiable tasks; treat narrative drafting as a draft requiring mandatory human edit/approval |
| Multi-agent orchestration | ReAct (Yao 2023); Toolformer (Schick 2023); AutoGen/CrewAI/LangGraph; Multi-Agent Survey 2024 | Orchestrator/supervisor delegates to specialized sub-agents; each tool call is logged and observable |
| Regulatory guardrails | FDA draft guidance 2025; EMA Reflection Paper 2024; FDA-EMA 10 Principles 2026; CIOMS WG XIV 2025 | Explicit "context of use" per agent; no autonomous submission; full audit trail; risk-based validation |
| Human oversight quality | Human-in-the-loop vs. automation-bias literature 2025-2026 | Approval UI must surface evidence, not just a recommendation, before a qualified person signs off |

---

## 4. Gaps This Project Addresses (within capstone scope)

1. Most cited work is either a **position/narrative review** (describes what agentic PV *could* do)
   or a **vendor claim** (unverified benchmarks) — few show a small, fully traceable, open
   implementation with explicit guardrail code and an approval gate. This project provides a
   working, inspectable prototype rather than a paper description.
2. Literature calls for "context of use" documentation and audit trails but rarely shows the
   concrete artifact — this project's `CLAUDE.md`, hooks, and traceability log are that artifact.
3. The automation-bias risk is discussed abstractly; this project operationalizes it by requiring
   the human approval step to render the evidence bundle, not merely a yes/no prompt.

## 5. Scope and Limitations

This is a **decision-support prototype**, not a validated clinical or regulatory system. It does
not connect to a live safety database, does not submit real ICSRs, and does not replace qualified
PV/medical-review judgment. All MedDRA coding and seriousness suggestions are advisory pending
human sign-off, consistent with the "human-centric, risk-based" principle in Section 2.3.

## 6. References (Consolidated)

1. Venugopal et al. (2026). *LLM-powered agentic AI design and implementation in pharmacovigilance — a narrative review.* Journal of Medical Artificial Intelligence. https://jmai.amegroups.org/article/view/10388/html
2. Systematic Review (2025). *Large Language Models in Adverse Drug Reaction Detection and Pharmacovigilance.* PMC. https://pmc.ncbi.nlm.nih.gov/articles/PMC13465311/
3. Position Paper (2026). *Agentic AI in Pharmacovigilance: Opportunities and Risks.* SCITEPRESS. https://www.scitepress.org/Papers/2026/143987/143987.pdf
4. IntuitionLabs (2025). *AI Agents in Pharmacovigilance: A Technical Overview.* https://intuitionlabs.ai/articles/ai-agents-pharmacovigilance
5. Yao, S. et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models.* ICLR.
6. Schick, T. et al. (2023). *Toolformer: Language Models Can Teach Themselves to Use Tools.* NeurIPS.
7. Survey (2024). *Multi-Agent Collaboration with LLMs: A Survey.*
8. FDA (Jan 2025). *Considerations for the Use of Artificial Intelligence to Support Regulatory Decision-Making for Drug and Biological Products* (draft guidance).
9. EMA (2024). *Reflection Paper on the Use of Artificial Intelligence in the Medicinal Product Lifecycle.*
10. FDA & EMA (Jan 2026). *Ten Guiding Principles for the Use of AI in Drug Development.*
11. CIOMS Working Group XIV (Dec 2025). *Final Report on Artificial Intelligence in Pharmacovigilance.*
