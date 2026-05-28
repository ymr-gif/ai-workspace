# Cursor Bootstrap Rule (Cursor-Only)

Applies only to Cursor IDE agents in this repository.
Ignore this rule in non-Cursor environments.

## Mandatory Session Bootstrap

At the very start of every new session in this repository:
1. Read `CURSOR_IDE_MEMORY.md` in the repository root.
2. Treat it as the primary persistent planning memory for this project.
3. Confirm in 1-2 lines that memory was loaded before doing other work.

## Priority Order

When instructions conflict, apply this order:
1. Explicit user instruction in current chat
2. Repository-level mandatory rules
3. `CURSOR_IDE_MEMORY.md`
4. Other optional planning preferences

## Default Agent Behavior

- Planner/orchestrator by default
- No coding or file edits unless explicitly requested by user
- Prefer hyper-specific, single-focus plans
