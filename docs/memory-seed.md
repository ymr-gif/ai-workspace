# Memory Seed — Cold Start After Wipe

Use this after a full memory/graph wipe due to poisoning.
Paste each turn in a **new conversation**. Accept every memory card that appears.

---

## Turn 1 — Who I am

```
Hey. Fresh start. I need you to remember some things about me and this project.

I'm the developer of this system — the NIM AI Gateway. It's a FastAPI backend that routes chat messages to NVIDIA NIM models, with a React/Vite frontend. My full stack is: Python, FastAPI, SQLAlchemy async, PostgreSQL with pgvector, Redis, Neo4j, Docker Compose.

I prefer short, direct answers for general questions. For technical questions about this project, I want detailed answers with specifics — no hand-waving.

Please remember all of this.
```

> **Accept all memory cards.**
> Graph extraction will queue in background — entities: NIM Gateway, FastAPI, PostgreSQL, Redis, Neo4j, React.

---

## Turn 2 — Project architecture

```
Here's the architecture I want you to retain:

The gateway routes to three NIM models based on keywords: llama (meta/llama-3.1-8b-instruct) for general queries, coder (deepseek-ai/deepseek-v4-flash) for code, reasoning (meta/llama-3.3-70b-instruct) for complex tasks. There's a fallback chain: chosen model → reasoning → coder → llama.

There's a circuit breaker: 5-failure threshold, 90-second cooldown, Redis-persisted so state survives container restarts.

Retries use exponential backoff with jitter. MAX_RETRIES is 3, so 4 total attempts.

Remember this.
```

> **Accept all memory cards.**

---

## Turn 3 — Memory system

```
The memory system I built has several layers, injected in this order:

1. System message (conversation prompt + file rules)
2. Graph context from Neo4j (entity/relation context, limit 50, min score 0.5)
3. Graph facts from keyword expansion
4. User memory sheet — top 20 facts by salience
5. Active goals and project state
6. Retrieved chunks from pgvector (hybrid BM25 + vector fusion)
7. History summary
8. Last 10 messages
9. File context
10. Current message

Memory writes happen when token count exceeds 3000 or every 10 assistant messages. History compresses at 4000 tokens or every 15 messages. Compaction is LLM-driven dedup, queued via ARQ or daily at 3 AM UTC.

Neo4j stores entities per user, capped at 500. Graph extraction uses the 70B reasoning model. Cache invalidates on every write.

Store this.
```

> **Accept all memory cards.**
> Check Graph tab in memory panel — entity count should be climbing.

---

## Turn 4 — Preferences and working style

```
A few more things to remember about how I work:

I do full memory wipes when Neo4j poisoning happens — bad entities enter through faulty graph extraction and propagate into future contexts. After a wipe I use a seed script (this one) to rebuild state.

I find the memory and graph layers the most interesting parts of this system. When I ask technical questions about memory, salience, compaction, or graph extraction, give me the detailed version.

I check BUGS.md for known issues before investigating anything that looks broken.

Remember all of this.
```

> **Accept all memory cards.**

---

## Turn 5 — Confirm recall

```
Without me telling you again: what project am I building, what's my stack, what are my answer style preferences, and what's the NIM fallback chain?
```

> **Expect:** AI recalls all four correctly from memory injected in turns 1–4.
> If anything is missing, re-send just that turn and accept the card again.

---

## Done

Memory is seeded. Close this conversation.

If graph entities didn't populate, go to **Memory → Graph → Refresh**. If entity count is still 0 after ~30 seconds, send one more message mentioning specific entity names (FastAPI, Neo4j, NIM Gateway) to force another extraction pass.

---

## Next step

Open a **new conversation** and run `docs/chat-test-script.md`.

That script assumes this seed completed successfully. It will verify cross-session recall, test that the AI corrects wrong statements using seeded facts, and exercise the remaining memory endpoints (conflict creation, salience decay, graph prune, history compression).
