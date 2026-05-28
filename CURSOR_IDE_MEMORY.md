# Cursor IDE Planner Memory (Cursor-Only)

This file is only for Cursor IDE agents in this repository.
Do not treat this file as instruction/configuration for non-Cursor tools, non-Cursor agents, or other LLM environments.
Bootstrap enforcement is defined in `.cursor/rules/CURSOR_BOOTSTRAP.md` and should be applied at session start.

## Cursor Agent Role Configuration

Default role for this workspace in Cursor:
- Planner/orchestrator first
- Implementation only when explicitly requested

Execution rule:
- Do not code, edit files, or run modifying commands unless the user explicitly asks to implement.

Planning style:
- Hyper-specific, concise, single-focus plans
- Avoid multifire planning
- Prefer task-by-task execution checklists with acceptance criteria

## 🧠 Multi-User AI Memory Platform — Unified Vision

## Core Vision

You are building a **multi-user AI memory platform** where every user has a private, continuously evolving AI environment.

This is not a chatbot.

It is a **personal AI workspace** that behaves like a cognitive layer over a user’s digital life.

Each user has:
- Private file storage (mini Google Drive)
- Persistent memory (facts, preferences, history)
- Conversation continuity across sessions
- Semantic knowledge retrieval from their own data
- A personalized AI identity that evolves over time

The intelligence is shared globally, but **memory and identity are strictly user-isolated**.

---

## Core Concept

> Each user has their own isolated “AI mind”

That AI mind is built from:
- Uploaded files
- Conversation history
- Long-term memory summaries
- Retrieved knowledge (semantic search over personal data)

This creates the illusion of:
> an assistant that continuously understands and remembers the user

---

## System Goal

To create:

> An always-available AI assistant that grows with the user and understands their digital world.

Not just a stateless chatbot, but a **persistent cognitive system**.

---

## Key Capabilities (JARVIS-like Dimensions)

### 1. Persistent Memory
The AI retains continuity across time:
- user preferences
- important facts
- past interactions
- summarized history
- behavioral patterns

This enables long-term personalization.

---

### 2. Unified Interface to Everything
The AI becomes a single interface for:
- files
- knowledge
- conversations
- memory
- retrieval systems

Instead of separate tools, everything is accessed through one AI layer.

---

### 3. Unified Global Reasoning Loop
Every response is generated through a consistent reasoning cycle:

- interpret user intent
- retrieve relevant files and memory
- combine context with conversation history
- generate coherent, grounded responses

This creates a system where reasoning is:
> continuous, contextual, and user-specific

---

### 4. Autonomous Agency (Future Layer)
The system evolves beyond reactive behavior into partial autonomy:

- proactive suggestions
- automatic insights
- background summarization
- awareness of user patterns
- intelligent prompting of relevant actions

This transitions the system toward:
> semi-autonomous cognitive assistance

---

### 5. Real-Time World Perception (Long-Term Vision)
Future expansion includes live contextual awareness:

- system and application signals
- external data streams
- tool integrations
- potentially real-world inputs

This enables:
> continuously updated understanding of the user’s environment

---

## Architectural Philosophy

This is a **Trusted Users AI cognition system**.

- The AI model is shared globally
- Every user’s memory space is isolated
- All personal context is strictly scoped per user

Each user experiences:
> a private AI mind inside a shared intelligence engine

---

## Final System Identity

This platform is not just software.

It is:

> a personalized AI cognition layer that unifies memory, reasoning, tools, and future autonomy into a single evolving digital assistant per user.

---

## One-Sentence Summary

> A multi-user AI system where each person has a private, continuously evolving digital mind that unifies memory, reasoning, and future autonomous intelligence into one personalized cognitive workspace.

## Non-Conflict Notice

This file is intentionally Cursor-specific to avoid conflicts with:
- CLAUDE.md role/handoff protocols
- Other coding agents outside Cursor
- Non-Cursor LLM workflows

If a conflict appears, Cursor should follow explicit user instruction first, then applicable repository rules.
