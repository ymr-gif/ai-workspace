# HANDOFF Protocol — Full Workflow

## Starting a feature
1. `find . -name HANDOFF.md`
2. Set Active Feature, write task lists per agent, set execution order
3. `mv HANDOFF.md backend/HANDOFF.md` (or whichever dir executes first)
4. Append a History row

## Returning to in-flight feature
1. Find file → read Recorded sections from prior agents
2. Amend next agent's task list if addenda needed
3. Leave file in place — owning agent moves it when done

## Task format
One checkbox = one concrete action (small and specific)

## Execution order
`backdir → frontdir → dockdir` · adjust per feature · skip unused dirs · return to root when all done (status: done)

## Files
| File | Purpose |
|------|---------|
| `HANDOFF.md` | Active feature + last 5 History rows |
| `HANDOFF_ARCHIVE.md` | All completed features, full detail |

One physical `HANDOFF.md` exists at any time. Its location = current owner.

## Archive rules
When History in `HANDOFF.md` reaches **5 rows**:
1. Move oldest rows to `HANDOFF_ARCHIVE.md` (keep last 5 in HANDOFF.md)
2. In archive, preserve full feature detail

When `HANDOFF_ARCHIVE.md` reaches **~20 entries**:
1. Collapse entries older than 6 months into a summary block:
   `## Pre-YYYY-QN: N features completed (see git log for detail)`
2. Delete those individual entries

## Updating subdir CLAUDE.md (workers)
- **Append only** — add new entries to existing sections; never rewrite or truncate the file
- Never touch root `CLAUDE.md` — it is root-owned; deleting or replacing it breaks all future sessions
- If a CLAUDE.md update requires removing stale info, note it in `### Recorded` and let root decide

## Multi-agent (future)
Extract shared rules into `AGENTS.md`; slim `CLAUDE.md` to root-only concerns; add `.cursorrules` pointing to `AGENTS.md` for Cursor workers.
