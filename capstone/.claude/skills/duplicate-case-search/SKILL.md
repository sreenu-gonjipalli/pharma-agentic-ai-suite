---
name: duplicate-case-search
description: Search the local cases/ store for likely duplicates of a given case by patient/drug/event field overlap. Use in pv-duplicate only.
---

# Duplicate Case Search

## Usage

**Preferred:** the `pv-tools` MCP server's `duplicate_search_case(case_id)` tool (implemented in
`mcp/pv_tools_server.py`, same overlap logic as the script below).

**Fallback:**

```bash
python3 .claude/skills/duplicate-case-search/scripts/duplicate_search.py --case-id CASE-20260926120000
```

Returns `{"matches": [{"case_id", "similarity", "status"}, ...]}`, sorted by similarity, for every
other case in `cases/` scoring at or above the similarity threshold (0.4) baked into the script.

## Rules

- Never treat a match as confirmed — every match is tagged `SUGGESTED — PENDING HUMAN REVIEW`.
- An empty `matches` list (including when `cases/` has only the current case) is a valid, honest
  result — do not fabricate a match to seem thorough.
- The calling agent (`pv-duplicate`) must surface every returned match to the evidence bundle,
  not filter any out — the human reviewer decides what counts as a true duplicate.
