---
name: case-state-io
description: Read/create/append the shared case JSON state at cases/<case_id>.json, per CLAUDE.md §5. Use this instead of hand-editing case files directly, so history[] stays consistent.
---

# Case State I/O

All pipeline agents (`pv-intake`, `pv-coding`, `pv-triage`, `pv-duplicate`, `pv-narrative`) share
one JSON document per case at `cases/<case_id>.json`. Never overwrite another agent's section —
only add or update your own top-level key, and always append one entry to `history[]`.

## Usage

**Preferred:** call the `pv-tools` MCP server's `case_init` / `case_read` / `case_update` tools
(wired in `.claude/settings.json`, implemented in `mcp/pv_tools_server.py`) — same behavior,
structured arguments instead of a shell command.

**Fallback** (also what the MCP tools call under the hood — one implementation, `scripts/case_store.py`):

```bash
# Create a new case (intake agent only, when no case_id exists yet)
python3 .claude/skills/case-state-io/scripts/case_store.py init --case-id CASE-20260926120000

# Read the current case state
python3 .claude/skills/case-state-io/scripts/case_store.py read --case-id CASE-20260926120000

# Update one section (value is a JSON string) and append a history entry
python3 .claude/skills/case-state-io/scripts/case_store.py update \
  --case-id CASE-20260926120000 \
  --section intake \
  --data '{"patient": "NOT REPORTED", "events": [...]}' \
  --agent pv-intake \
  --action extract_fields
```

## Rules

- `section` must be one of: `intake`, `coding`, `triage`, `duplicate_check`, `narrative`. Any other
  value is rejected — this enforces CLAUDE.md's one-agent-one-section rule.
- `update` merges/replaces only the named top-level section; every other section is preserved.
- Every `update` call appends `{"agent", "action", "timestamp"}` to `history[]` automatically —
  agents do not need to hand-craft this.
- A `posttool_guard` hook (`hooks/posttool_guard.py`) re-checks every case file after a write and
  rejects (exit 2) any `coding`/`triage` section missing the advisory tag or a source span — fix
  and re-write the section if you see that message.
- `status` field defaults to `IN_PROGRESS`. The **only** way to reach `FINAL` is
  `case_store.py approve` (CLAUDE.md §8/§10) — a human-reviewer-only CLI command, not exposed as
  an MCP tool and not part of any pipeline agent's instructions:

```bash
python3 .claude/skills/case-state-io/scripts/case_store.py approve \
  --case-id CASE-20260926120000 --reviewer "<name>" --decision APPROVE|EDIT|REJECT --notes "..."
```
