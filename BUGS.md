# Known Bugs & Issues

Tracker for all confirmed bugs across the stack. Check off when fixed.

Legend: `[x]` = fixed · `[~]` = partially fixed · `[ ]` = open

> History note: closed batches were removed once shipped — see git log.
> Backend Audit B1–B8 (`fde4b53`), JARVIS Fallback F1–F5 (`3e27456`),
> Core-Node Protection G1–G2 (`e7839ba`), Canvas hardening I1–I3 (`41174a3`),
> create_conversation auto-wiring regression fix (`abc70af`),
> Canvas multi-turn confirm + tool-loop fixes J1–J3 (`various`),
> Google Drive integration + file tool loop K1–K10 (`65624d0`, `1a16c84`, `436554a`, `5b29500`, `9d4876b`),
> Drive stale-content + follow-up read L1–L2/M1–M6 (`b28288f`, `8fc337a`),
> Drive listing dumped on non-Drive turns N1 (`91facbe`),
> Drive keyword gate punctuation N2 (`dc18773`),
> Memory hygiene epic + safe reset S1–S4/O1–O6 (`65e8ad5`), prune hardening O7 (`ba17a39`),
> manual verification runbook (`ec5f1d0`). All fixed & verified live.

---

## Open follow-ups

- `[x]` **`POST /admin/memory/restore` endpoint** — FIXED (2026-06-17). `api/admin/memory.py` adds
  `GET /admin/memory/versions?user_id=` (lists snapshots, newest first: id/version/created_at/content_len)
  and `POST /admin/memory/restore {user_id, version_id, confirm:"RESTORE <id>"}`. Restore snapshots the
  current sheet first (itself reversible), then sets `content`/`project_summary` from the chosen
  `user_memory_versions` row, bumps `version`, audits `memory.restore`. Guards verified live (bad confirm
  → 400, missing version → 404).
- `[x]` **Cross-conversation RAG scoping** — FIXED (2026-06-17). `retriever/main.py::retrieve_global` now
  applies a similarity floor (`_GLOBAL_SIM_FLOOR=0.30`) + recency decay (`_RECENCY_HALF_LIFE_DAYS=14`,
  `0.5 ** (age_days/half_life)` on `MessageEmbedding.created_at`) and re-ranks by the weighted score before
  fusion. Cross-conv pool only — within-conv `retrieve()` unchanged. No migration (created_at already exists).
- `[x]` **Embedding hygiene** — FIXED (2026-06-17). The 9 canvas-tainted `message_embeddings` in active
  convs were deleted via live SQL (matched `(canvas|session node|workspace|output node|input node)`, verified
  0 remain). Canvas feature is removed so none regenerate; archived-conv copies stay filtered by retrieval.
- `[x]` **Test-mock tidy** — FIXED (2026-06-17). `test_drive.py` patched `get_redis` (a *sync* fn) with
  `AsyncMock`, leaking an un-awaited coroutine. Swapped to `MagicMock(return_value=mock_redis)` in the
  cache-resolution + search tests. Full suite green under `-W error::RuntimeWarning` (107 passed, 1 skipped).
- `[ ]` **Reasoning trace is pipeline-level, not model chain-of-thought** — the `activity[]` trace in
  the `done` SSE (grounding badge → "Reasoning steps") shows the pipeline (retrieval/intent/route/
  budget/model/tools), not the model's internal deliberation. `meta/llama-3.3-70b-instruct` emits no
  native thinking tokens. Not a defect — closes the practical Dim-3 gap. Real CoT would need either a
  prompt-based `<thinking>` block (cheap, +tokens/latency, narrated not faithful) or a NIM reasoning-tier
  model that emits traces (model/cost change). Revisit only if users ask "why did it answer that."
- `[x]` **Grounding/queryType/src badges wiped on new-conversation refetch** — FIXED via full
  persistence (migration 044). `messages.render_meta` JSONB now stores `{grounding, query_type,
  src_count}`, built once in `api/chat/stream.py` (`_build_provenance` + `_build_render_meta`) before the
  assistant-message persist and reused for the `done` SSE (no double-compute). `GET /conversations/{id}/
  messages` returns those fields; `useConversations.js` maps them + `activity_trace` on refetch. Badge +
  expandable trace now survive the new-conversation refetch, full page reload, and cold history load —
  verified live (badge `Low · 20%` + Intent/Routing/RAG/Loaded trace rows loaded from `GET messages`,
  no live SSE).
