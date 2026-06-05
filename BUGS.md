# Known Bugs & Issues

Tracker for all confirmed bugs across the stack. Check off when fixed.

Legend: `[x]` = fixed · `[~]` = partially fixed · `[ ]` = open

> History note: closed batches were removed once shipped — see git log.
> Backend Audit B1–B8 (`fde4b53`), JARVIS Fallback F1–F5 (`3e27456`),
> Core-Node Protection G1–G2 (`e7839ba`), Canvas hardening I1–I3 (`41174a3`),
> create_conversation auto-wiring regression fix (`abc70af`). All fixed.

---

## Fixed — Tool-loop errors + false creation framing (2026-06-04)

### J1 · [x] Model calls canvas tools repeatedly on benign messages, hits tool-loop abort

- **Symptom:** 70B reasoning model produced tool-loop errors on *benign* messages ("hello how are you", "suggest a new topic", "interesting topic?") — calling `create_conversation` / `get_canvas_graph` / `create_canvas_node` until the >3-same-tool abort or the 20-iteration `MAX_TOOL_ITERATIONS` cap. Visible to the user as "Tool loop detected".

- **Actual root cause (verified live, not what we first thought):** The model treats **every** turn in the JARVIS session as a canvas task and will spin on *whatever* canvas tool is offered. Prompt priming (naming `create_conversation`, the CONFIRMATION/SESSION blocks) was a *contributor*, not the cause — removing all of it did **not** stop the loop. Live proof:
  - Removed all creation priming + hardened rejection strings → model still called `create_conversation` 4× → abort. (cause 5, "learned/contaminated behavior", was the real driver.)
  - Gated `create_conversation` only → model switched to `create_canvas_node`/`wire_nodes` and looped on those.
  - Gated all canvas *write* tools, leaving read-only → model spun on `get_canvas_graph`/`query_canvas` ×20 → "Tool loop limit reached", 0 text.
  - **Only** withholding *all* canvas tools on benign turns made it answer in plain text.

- **Fix (live, verified):**

  | Change | File |
  |--------|------|
  | **`canvas_context_active(message, conv_id)`** — canvas tools offered only when the message names a canvas object (`_CANVAS_INTENT_RE`: canvas/node/session/conversation/wire/graph…) OR a creation flow is mid-confirmation (Redis state set) | `llm/tools/executor.py` |
  | Service layer drops **all** canvas tools when `canvas_context_active` is false — if none are offered, the model can't loop and must answer in text | `llm/service/stream.py` |
  | **Layer 3 confirm-turn regression fix** — the uncommitted "stale cross-check" had gated the `pending_specs` branch on re-detecting creation intent in the *latest* message; the confirm turn's message is "yes" (no intent) so it cleared the flow and rejected → creation could never complete. Reverted to gate on `_user_replied_after_ask` (affirmative reply after the ask). Canvas tool gating now covers the stale-leak case the cross-check was trying to handle. | `llm/tools/executor.py` |
  | Anti-priming cleanup (kept, defense-in-depth): RULES no longer name `create_conversation`; `create_conversation` schema drops the wrong manual create+wire procedure (auto-wiring owns it); `create_canvas_node` schema lists session as managed; rejection strings tell the model to stop retrying | `api/chat/stream.py`, `llm/tools/schemas.py`, `llm/tools/executor.py` |

- **Follow-up fix (2026-06-05) — confirm-turn looped on a bare title:** the ask says "provide a title", but Layer 3 (`_user_replied_after_ask`) required a `_CONFIRMATION_RE` yes-word. A user replying with a plain title ("ProjectPhoenix") never matched → reject → model retried → abort. (The earlier verify passed only because "yes, please create it" happened to match.) Fixed: after the ask, any non-empty, non-negation, non-question reply counts as confirmation (the title *is* the confirmation); `?`-ending replies stay pending so unrelated questions don't auto-confirm. Verified live: "can you make a new session?" → "ProjectPhoenix" creates once (10→11), no loop.

- **Verification (live, 70B forced, JARVIS session):**
  - Benign: "hello how are you" / "suggest a new topic" / "interesting topic?" → **0 tool calls**, real text answers, no loop.
  - Creation: "create a new session called Demo" → ask_user confirmation (flow=pending_specs) → "yes, please create it" → creates **exactly once** (conversations 9→10, "Demo"), session canvas node auto-created (`kind=user`) + wired, flow state cleared, model confirms in text.
  - Read intent: "what is on my canvas?" → `get_canvas_graph` offered + answered, no loop.
  - `pytest tests/retrieval/` 26/26 pass.

- **Ruled out:** `_CREATION_RE` catch-all (suspect 4) — gated behind a "session"/"conversation" token; "new topic"/"a story"/"hello" return no creation intent. Governs the guard's verdict, not whether the model calls the tool.

- **Residual fix (2026-06-05) — all canvas injection now intent-gated:** a single `canvas_active = canvas_context_active(message, conv_id)` flag in `api/chat/stream.py` now gates *every* canvas-flavored prompt block on benign turns: the boot `> CANVAS:` line (`format_boot_log(report, include_canvas=canvas_active)` in `agent/boot.py`), `last_session`, node inventory, and `[CANVAS STATE]`. Model-health + scratchpad boot lines are kept (not canvas). Verified live (70B): "hello?" / "how are you?" → clean text, **no canvas narration, 0 tools**; "how many nodes on my canvas?" → `get_canvas_graph` → "You have 8 nodes." Old node-ID echoes ("the No name session a644dbbd…") came from the JARVIS session's own *conversation history* (176 dev/test turns, 2026-06-01→05), not a fresh injection — backed up to `backend/storage/backups/jarvis_msgs_*.csv` and pending a history clear.

