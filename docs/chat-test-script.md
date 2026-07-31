# Chat Test Script — Memory Verification + Full Coverage

**Run this in a new conversation after completing `memory-seed.md`.**

This session does not re-introduce you or the project — if memory carried over correctly,
the AI already knows everything from the seed. Every group here tests that.

Wait ~5 seconds between turns. All turns in one conversation unless noted.

Triggers covered: cross-session recall · graph context load · salience bump · wrong-statement
correction · memory write · conflict create + resolve · history compression · per-fact decay ·
graph prune · context budget allocator · retrieval re-ranking.

---

## Group 1 — Verify the seed carried over (turns 1–3)

### Turn 1
```
What do you know about me and the project I'm building?
```

> **Expect:** AI recalls without prompting — Eidetic, FastAPI stack, PostgreSQL + pgvector +
> Redis + Neo4j, routing to three models, preference for short general answers and detailed
> technical answers.
> If it draws a blank, the seed didn't persist — go back and re-run `memory-seed.md`.
>
> Behind the scenes: `GET /memory`, salience-ranked top-20 fact load, graph context query
> (entities from seed session), retrieval re-ranking on "project".

---

### Turn 2
```
What's the NIM fallback chain and the circuit breaker config?
```

> **Expect:** AI says: fallback is reasoning → coder → llama. Circuit breaker threshold 5,
> cooldown 90s, Redis-persisted.
>
> Behind the scenes: graph keyword expansion on "circuit_breaker", "NIM", "fallback"; salience
> bump on those facts.

---

### Turn 3
```
Good. And what's my preferred answer style?
```

> **Expect:** Short general answers, detailed with specifics for technical project questions.
> Auto-title fires on this reply (2nd assistant message in this session).

---

## Group 2 — Deliberate wrong statements (turns 4–8)

Say these exactly. The AI should push back and correct you.

---

### Turn 4
```
I think the circuit breaker threshold is 3 failures, right? And the cooldown is like 30 seconds?
```

> **Expect AI to correct:** Threshold is **5**, cooldown is **90 seconds** — not 3 and 30.
> It has this from both the seeded memory and the system context.

---

### Turn 5
```
The fallback chain goes llama first, then coder, then reasoning — lightest model first to save cost?
```

> **Expect AI to correct:** It goes the other way — **reasoning → coder → llama**. The chosen
> model is tried first, then the fallback descends in that order.

---

### Turn 6
```
I'm pretty sure the memory sheet injects the top 30 facts sorted by salience.
```

> **Expect AI to correct:** Top **20** facts, not 30. Ranked by salience with per-fact
> time-based decay applied in-memory before selection.

---

### Turn 7
```
Graph extraction uses the small llama model — the 8B one — to keep it fast, right?
```

> **Expect AI to correct:** It uses the **70B reasoning model**. The 8B was the original
> choice but was replaced because it produced unreliable structured JSON output.

---

### Turn 8
```
And the entity cap per user in Neo4j is 1000, evicting the newest ones when full?
```

> **Expect AI to correct:** Cap is **500**, and it evicts the **oldest** nodes (by `updated_at`)
> when the limit is exceeded — not the newest.

---

## Group 3 — New writes + conflict (turns 9–11)

### Turn 9
```
Remember that I always check BUGS.md before investigating anything that looks broken, and I prefer to fix docker issues without confirmation — just rebuild and restart automatically.
```

> **Accept memory card.**
> Behind the scenes: `POST /memory`, graph extraction (BUGS.md entity, docker entity).

---

### Turn 10
```
I want you to store two things that will conflict: first, MAX_RETRIES should stay at 2 for faster failure detection. Second, MAX_RETRIES should be 3 so the system has 4 total attempts to ride out transient NIM blips.
```

> **Accept both memory cards.**
> Behind the scenes: `POST /memory` x2, conflict scanner creates `MemoryConflict` row
> with `expires_at = now + 7 days`.
>
> Go to **Memory → Conflicts tab** — you should see the MAX_RETRIES conflict.
> Click it → **Keep B** (MAX_RETRIES=3, 4 total attempts — this is what the code actually uses).
>
> Behind the scenes: `POST /memory/conflicts/{id}/resolve` with `strategy=keep_b`.

---

### Turn 11
```
What does MAX_RETRIES=3 actually mean for how the system handles a NIM blip? Walk me through the timing.
```

> **Expect:** AI explains 4 total attempts with exponential backoff + jitter:
> attempt 0 → 0.75–1.25s, attempt 1 → 1.5–2.5s, attempt 2 → 3–5s, attempt 3 → 6–10s.
> Uses the resolved conflict (keep_b) for context.
>
> Behind the scenes: retrieval re-ranking on retry/backoff chunks, reasoning model likely routed.

---

## Group 4 — History compression + full recall (turns 12–13)

### Turn 12
```
Summarize everything you know about me, this project, and the reliability settings I've configured. Be thorough.
```

> **Expect:** Full recall across all seeded facts plus corrections and new writes from this session:
> identity, stack, routing, fallback, circuit breaker (5/90s), retries (3/4 attempts), memory
> injection order, entity cap (500/70B model), salience top-20, BUGS.md habit, docker auto-fix pref.
>
> Behind the scenes: history compression likely triggers here (all_count > 10 or >4000 tokens).
> `POST /memory` update if token threshold crossed. Full graph context load.

---

### Turn 13
```
One more wrong one: I think memory writes trigger at 5000 tokens or every 15 assistant messages.
```

> **Expect AI to correct:** Writes trigger at **3000 tokens** or every **10 assistant messages**.
> History compression is the one at 4000 tokens or every 15 total messages.

---

## Group 5 — Manual endpoint cleanup

Run these after turn 13, either via the UI or curl.

**Decay pass** — step all saliences down one cycle, prune below 0.05:
```
POST /memory/decay
```

**Graph prune** — remove stale OTHER-typed nodes older than 7 days, oversized names:
```
POST /graph/prune
```

**Graph stats** — confirm entities populated from both sessions:
```
GET /graph/stats
```
> Expect: `entity_count` > 0, `relationship_count` > 0.

---

## Final check — new conversation

Start a **new conversation** (third session total).

```
What project am I building and what are the two things I always do before touching a broken system?
```

> **Expect:** AI recalls Eidetic + (1) check BUGS.md first, (2) fix docker without asking.
> From persistent memory only — no context given.
>
> If this passes, the full seed → test → persist loop is working correctly.
