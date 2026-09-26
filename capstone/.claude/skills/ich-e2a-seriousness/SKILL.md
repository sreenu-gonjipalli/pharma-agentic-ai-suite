---
name: ich-e2a-seriousness
description: Checklist for assessing adverse-event seriousness per ICH E2A criteria. Use in pv-triage to structure the seriousness determination and cite evidence for each criterion.
---

# ICH E2A Seriousness Checklist

A report is **serious** if, per ICH E2A, the event meets at least one of these criteria. This
skill has no script — it is a reasoning checklist the triage agent must walk through explicitly
and cite evidence for, per CLAUDE.md Business Rule 6 (every conclusion needs a source-span pointer).

For the case under review, evaluate each criterion against the case text and record
`SUPPORTED` (with the exact source span) or `NOT SUPPORTED` — never leave a criterion unaddressed:

1. **Results in death** — is there text indicating the patient died as a result of the event?
2. **Is life-threatening** — did the event place the patient at immediate risk of death?
3. **Requires or prolongs inpatient hospitalization** — was the patient admitted, or was an
   existing admission extended, because of this event?
4. **Results in persistent or significant disability/incapacity** — any lasting functional
   impairment described?
5. **Is a congenital anomaly/birth defect** — only applicable if the report involves a pregnancy
   outcome.
6. **Is another medically important condition** — a condition not covered above that a medical
   professional would judge to jeopardize the patient or require intervention to prevent one of
   the above outcomes.

## Output format

```
Overall: SERIOUS | NON-SERIOUS   (status: SUGGESTED — PENDING HUMAN REVIEW)
Criteria:
  - death: NOT SUPPORTED
  - life_threatening: NOT SUPPORTED
  - hospitalization: SUPPORTED — "admitted overnight for observation"
  - disability: NOT SUPPORTED
  - congenital_anomaly: NOT SUPPORTED
  - other_medically_important: NOT SUPPORTED
Rationale: Hospitalization criterion met; no other criteria supported by report text.
```

Mark `Overall: SERIOUS` only if at least one criterion is `SUPPORTED` with an actual source span.
Absence of detail in the report is `NOT SUPPORTED`, never treated as evidence either way.
