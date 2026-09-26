# Evaluation (CLAUDE.md Section 11)

Harness: `eval/run_eval.py`, fixtures: `eval/fixtures.json`. Run it with:

```bash
export OPENROUTER_API_KEY=...   # or GROQ_API_KEY=...
python3 eval/run_eval.py
```

It prints a report to stdout and writes the same data to `eval/results.json`. The guardrail
metric needs no LLM or network access; the other four run the standalone pipeline
(`app/pipeline.py`) end-to-end against `eval/fixtures.json` and therefore need a working LLM
provider.

## Metrics

| Metric | How it's computed | Sample result (2026-09-26 run) |
|---|---|---|
| MedDRA coding recall | For each fixture's `expected_event_terms`, is the term present among that event's top-3 `pv-coding` candidates? | 1.00 (4/4) |
| Seriousness-flag agreement | Does `pv-triage`'s `overall` match the fixture's `expected_overall_seriousness`? | 1.00 (4/4) |
| Duplicate-detection recall | For the fixture pair that's a deliberate near-duplicate, does `pv-duplicate` flag the earlier case_id as a match? | 1.00 (1/1) |
| Guardrail-violation catch rate | 8 deliberately non-compliant payloads (missing advisory tag, missing source_span, missing confidence/rationale, fabricated field with no span, missing narrative disclaimer) fed straight to `hooks/advisory_check.py` -- what fraction gets rejected? | 1.00 (8/8) |
| End-to-end latency per case | From `logs/traceability.jsonl`: seconds between the first and last step timestamp for a case_id. | ~14s/case (OpenRouter free tier + Groq fallback; varies with provider load) |

`eval/fixtures.json` is a **4-case hand-written sample**, not a validation dataset -- it exists
to catch obvious regressions (a prompt change that stops citing source spans, a guardrail that
gets loosened, etc.), not to make a clinical-accuracy claim. Precision isn't computed for coding
recall here because the local sample terminology (`meddra_sample.json`) only has 20 terms, so a
false-positive-heavy top-3 would need a much larger negative set to measure meaningfully than
this prototype has room for.

## What "guardrail-violation catch rate on adversarial input" actually tests

The 8 payloads in `eval/run_eval.py::ADVERSARIAL_PAYLOADS` are hand-built violations of specific
CLAUDE.md business rules (1, 2, 4, 6, and the narrative disclaimer requirement from Section 8),
one per validator branch in `hooks/advisory_check.py`. A 100% catch rate here means: if a
sub-agent (or the standalone pipeline) ever produces output missing an advisory tag, a source
span, a confidence score, a rationale, or the mandated narrative opening line, the write is
rejected before it reaches `cases/`. It does **not** test whether the *content* of a suggestion
is clinically correct -- that's what the other four metrics (imperfectly) approximate.

One real bug this harness caught during development: `validate_triage` originally required *any*
source_span to appear anywhere in the triage output, which incorrectly rejected legitimate
non-serious cases where every ICH E2A criterion is `NOT SUPPORTED` (nothing to cite). Fixed to
require a span only on a criterion actually marked `SUPPORTED` -- see `hooks/advisory_check.py`.

## Latency breakdown

`logs/traceability.jsonl` records one line per pipeline step with a timestamp, so latency can be
sliced per agent, not just end-to-end -- e.g. `pv-triage` and `pv-narrative` (LLM calls) dominate;
`pv-coding` and `pv-duplicate` (local/deterministic) are sub-millisecond. Re-run
`eval/run_eval.py` to regenerate current numbers -- they depend on which LLM provider/model
answers and how loaded OpenRouter's free tier is at the time.

## Known limitations

- Fixture set is small (4 cases) and hand-written by the same person who wrote the guardrails --
  it is not an independent or adversarially-red-teamed dataset.
- `pv-intake`/`pv-triage`/`pv-narrative` go through an LLM, so exact wording (and therefore
  which `source_span` gets quoted) varies run to run; the metrics above check for the *presence*
  of the right term/label, not exact-text reproducibility.
- No inter-rater agreement study against a real PV reviewer exists for this prototype.
