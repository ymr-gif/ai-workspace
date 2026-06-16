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

- `[ ]` **`POST /admin/memory/restore` endpoint** — safe-reset rollback is currently manual (restore
  `user_memory.content` from a `user_memory_versions` snapshot). Backup-on-reset works; only the
  one-click restore is missing.
- `[~]` **Cross-conversation RAG scoping** — archived conversations are excluded from the global
  embedding pool (O2), but active conversations still share one pool with no recency-decay /
  similarity-threshold weighting. Low impact for single-thread use; revisit if multi-thread bleed appears.
- `[ ]` **Embedding hygiene** — 9 canvas-tainted `message_embeddings` remain in active convs
  (18 more in archived = already filtered). Low impact; left as-is.
- `[ ]` **Test-mock tidy** — `test_drive.py::test_drive_read_file_resolves_name_from_cache` emits a
  benign `AsyncMock never awaited` RuntimeWarning; production code awaits correctly.
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
