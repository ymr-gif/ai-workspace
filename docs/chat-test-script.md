# Chat Test Script — Memory System Full Coverage

All messages go in **one conversation** unless noted. Paste each block exactly.
Wait ~5 seconds between turns to avoid rate limit (15 req/60s).

Triggers covered: auto-title · graph extraction · memory write · salience bump ·
per-fact decay · history compression · conflict creation + resolution · graph prune ·
context budget · retrieval re-ranking · compaction queue.

---

## Group 1 — Establish identity (turns 1–3)

### Turn 1
```
What routing system did I give you? I added a keyword classifier to your config that routes messages to three NIM models: llama for general, coder for coding, reasoning for complex tasks. Can you confirm you have that context?
```
> Expect: AI references the routing logic. Salience bump fires on memory load.
> Behind the scenes: `GET /memory`, graph context query, retrieval re-ranking.

---

### Turn 2
```
Good. I'm the developer of this gateway. I build backend systems in Python. My main stack for this project is FastAPI, SQLAlchemy async, PostgreSQL with pgvector, Redis, and Neo4j. I want you to remember that.
```
> Expect: Memory card appears — click **Accept**.
> Behind the scenes: `POST /memory` (new fact), graph extraction queued (entities: FastAPI, SQLAlchemy, PostgreSQL, Redis, Neo4j, user node).
> Auto-title fires after this reply (2nd assistant message).

---

### Turn 3
```
I also added the fallback chain to your system context: if the chosen model fails, you fall back to reasoning, then coder, then llama. There's a circuit breaker with a threshold of 5 failures and a 90-second cooldown, persisted in Redis. What does that mean if the reasoning model goes down?
```
> Expect: AI explains the fallback behavior using the system context you injected.
> Behind the scenes: graph keyword expansion on "circuit_breaker", retrieval on circuit breaker chunks, `[reasoning]` label likely.

---

## Group 2 — Project depth + graph population (turns 4–7)

### Turn 4
```
Remember that I care most about the memory system in this project. Specifically, I find the Neo4j graph layer the most interesting part — it extracts entities and relationships from every conversation and stores them per user with a 500-entity cap.
```
> Expect: Memory card — click **Accept**.
> Behind the scenes: `POST /memory`, graph extraction (entities: Neo4j, graph layer, entity cap). Check Graph tab in memory panel after this turn — you should see new nodes.

---

### Turn 5
```
I added the full memory injection order to your system prompt. It goes: system message, then graph context from Neo4j, then graph facts from keyword expansion, then user memory sheet top-20 facts, then workspace state, then retrieved chunks, then history summary, then last 10 messages, then file context, then your current message. Does that match what you see in your context?
```
> Expect: AI confirms the injection order. All memory tiers are exercised on this load.
> Behind the scenes: `GET /memory`, graph context (limit=50, min_score=0.5), keyword expansion, salience-ranked fact selection, context budget allocator.

---

### Turn 6
```
I want you to remember two things that might conflict: first, I prefer extremely short responses with no explanation. Second, for this project specifically, I want detailed technical answers with examples.
```
> Expect: Memory card — click **Accept** on both. This creates a style conflict.
> Behind the scenes: `POST /memory` x2, conflict scanner runs, `MemoryConflict` row created with `expires_at = now + 7 days`.

---

### Turn 7
```
Now go to the Memory panel → Conflicts tab. You should see an active conflict between response style preferences. Resolve it by keeping the second fact (detailed technical answers). Then come back and tell me what you know about my preferences.
```
> Instruction: In the UI, click the conflict → **Keep B** → confirm.
> Behind the scenes: `POST /memory/conflicts/{id}/resolve` with `strategy=keep_b`.
> Expect: AI confirms the resolved preference on next load.

---

## Group 3 — History compression threshold (turns 8–11)

### Turn 8
```
What's the salience decay formula in this system? I added it to your context. Facts decay at 0.95 per compaction cycle, and per-fact scores also decay in-memory at 0.95 to the power of hours-since-last-compaction divided by 24, before the top-20 selection. Facts below 0.05 get pruned from the JSONB column entirely.
```
> Expect: AI confirms the formula. Salience-ranked facts now include this topic.
> Behind the scenes: retrieval re-ranking (`final_score * (1 + memory_salience * 0.05)`), per-fact bump on accessed facts.

---

### Turn 9
```
How does the context budget allocator decide what to drop when a message is too long for the model's context window? I configured it to drop lowest-tier sources first — file context drops before history, history before graph facts, graph facts before the memory sheet.
```
> Expect: AI explains tier-based dropping using the system context.
> Behind the scenes: context budget logic exercised on build.

---

### Turn 10
```
What are all the ARQ background jobs in this system? I set max tries to 4 with delays of 5s, 30s, 120s. There are four job types: process_file, generate_insight, re_embed_batch, and compact_memory. Each increments ARQ_JOB_FAILED on final failure.
```
> Expect: AI lists all 4 job types correctly.
> Behind the scenes: graph extraction for new entities (ARQ, job types), retrieval.

---

### Turn 11
```
Summarize everything you know about me and this project. Include my stack, my preferences, the models I configured, the memory system architecture, and anything else you've retained.
```
> Expect: Full memory recall — stack, preferences, routing, circuit breaker, memory injection order, salience, ARQ.
> Behind the scenes: history compression likely triggers here (all_count > 10), `POST /memory` update if token threshold crossed (>3000 tok exchanged). Graph context full load.

---

## Group 4 — Cleanup + endpoint verification (manual steps)

### After turn 11 — run these manually in the UI or curl:

**Decay pass:**
```
POST /memory/decay
```
> Expect: All fact saliences step down by one decay cycle. Facts below 0.05 pruned.

**Graph prune:**
```
POST /graph/prune
```
> Expect: Any oversized entity names (>200 chars) or stale OTHER-typed nodes older than 7 days removed.

**Graph stats check:**
```
GET /graph/stats
```
> Expect: `entity_count` > 0, `relationship_count` > 0. Should reflect entities from turns 1–10.

---

### Turn 12 — final recall check (new conversation)

> Start a **new conversation** for this turn.

```
What project am I working on and what's my preferred answer style?
```
> Expect: AI recalls FastAPI/Neo4j gateway + detailed technical answers — from persistent memory, no context given.
> Behind the scenes: fresh `GET /memory` load, graph context query, salience-ranked top-20 facts injected — confirms cross-session persistence.
