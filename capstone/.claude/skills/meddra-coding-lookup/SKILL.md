---
name: meddra-coding-lookup
description: Suggest MedDRA-style candidate terms for a free-text adverse-event description, using a small local sample terminology (not the licensed MedDRA dictionary). Use in pv-coding, never to produce a single final code.
---

# MedDRA Coding Lookup (Prototype)

This skill is a **stand-in** for a real MedDRA dictionary lookup/API — this capstone does not have
a MedDRA license. It demonstrates the tool-use pattern the real integration would follow.

## Usage

**Preferred:** the `pv-tools` MCP server's `meddra_lookup_terms(text, top=3)` tool (implemented in
`mcp/pv_tools_server.py`, same matching logic as the script below).

**Fallback:**

```bash
python3 .claude/skills/meddra-coding-lookup/scripts/meddra_lookup.py --text "patient reported severe headache and nausea" --top 3
```

Returns a JSON list of up to `--top` candidates, each with `term`, `soc` (System Organ Class),
`confidence` (0-1), and `source_span` (the input text, so the reviewer can trace it).

## Rules (per CLAUDE.md Business Rule 2)

- Always request `--top 3` or more — never treat the first result as a final code.
- If every candidate has `confidence == 0.0`, report `"NO MATCH FOUND"` rather than picking the
  closest-sounding term.
- Every result must be tagged `SUGGESTED — PENDING HUMAN REVIEW` by the calling agent before it is
  written to case state — `hooks/posttool_guard.py` rejects the write otherwise.
- Swapping this script (and its MCP wrapper) for a real MedDRA API/MCP tool later should not
  require changing the calling agent's instructions — only `mcp/pv_tools_server.py`'s
  `meddra_lookup_terms` implementation.
