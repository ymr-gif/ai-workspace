import re

_FILE_OP_KEYWORDS = frozenset({
    "read", "write", "edit", "update", "create", "append", "patch",
    "search", "find", "fix", "change", "modify", "file", "document",
    "documents", "content", "add", "remove", "delete", "replace",
    "rewrite", "summarize", "analyse", "analyze", "open", "insert",
    "correct", "improve", "refactor", "rename", "review", "check",
})

_MEMORY_WRITE_VERBS = frozenset({
    "save", "add", "store", "write", "put", "keep", "insert",
    "remember", "memorize", "record",
})

_MEMORY_WRITE_TARGETS = frozenset({
    "memory", "memories",
})


def _needs_file_tools(message: str) -> bool:
    tokens = set(message.lower().split())
    return bool(tokens & _FILE_OP_KEYWORDS)


_MEMORY_STANDALONE_TRIGGERS = frozenset({"remember", "memorize"})


def _needs_memory_tool(message: str) -> bool:
    tokens = set(message.lower().split())
    if tokens & _MEMORY_STANDALONE_TRIGGERS:
        return True
    return bool(tokens & _MEMORY_WRITE_VERBS) and bool(tokens & _MEMORY_WRITE_TARGETS)


def build_context_messages(
    memory_sheet:     str,
    project_summary:  str,
    retrieved_chunks: list[str],
    history_summary:  str,
    history:          list[dict],
    memory_enabled:   bool,
    system_prompt:    str | None      = None,
    file_chunks:      list[str]       = (),
    file_names:       list[str]       = (),
    file_ids:         list            = (),
    workspace_memory: str             = "",
    graph_context:    str             = "",
    graph_facts:      str             = "",
    conflicted_facts: frozenset[str]  = frozenset(),
    last_session:     str             = "",
) -> list[dict]:
    messages = []

    if file_names:
        if file_ids:
            files_list  = "\n".join(f"  - {name} (id={fid})" for name, fid in zip(file_names, file_ids))
            file_notice = (
                f"The user has attached these files:\n{files_list}\n"
                "Rules for file tools:\n"
                "- To ANSWER a question about file content: use read_file or search_in_file, then reply in chat. For specific sections of large files, prefer search_in_file over read_file.\n"
                "- NEVER use write tools (write_file, append_to_file, patch_file) to answer questions. If asked to 'list', 'show', 'explain', 'display', 'summarize', or 'describe' — respond in chat text, not by writing to the file.\n"
                "- To ADD new content to a file: use append_to_file — ONLY when user explicitly asks to add/write/append to the file.\n"
                "- To EDIT a specific passage: use read_file first, then patch_file(old_text=<exact passage>, new_text=<replacement>)\n"
                "- To REWRITE the whole file: use read_file first, then write_file with the COMPLETE rewritten content — never write_file without reading first\n"
                "- NEVER use write_file for partial updates — it permanently deletes everything not included. Use patch_file.\n"
                "- To CREATE a new file: use create_file — only for genuinely new files, never to reconstruct missing context\n"
                "- After any write/append/patch/create succeeds, respond to the user immediately — do NOT read the file back to verify\n"
                "- Never call the same tool more than twice in a single turn\n"
                "- If information is not in your current context: say so directly. Never fabricate content, invent logs, or create files to substitute for missing context.\n"
                "- NEVER say 'Memory updated', 'Saved to memory', or any variant. Memory is only saved when the system shows a green confirmation card with Accept/Dismiss buttons. Without that card, nothing is saved — do not pretend otherwise."
            )
        else:
            file_notice = f"The user has attached these files: {', '.join(file_names)}. Use file tools to read or edit them."
        base = system_prompt.rstrip() + "\n\n" + file_notice if system_prompt else file_notice
        messages.append({"role": "system", "content": base})
    elif system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    else:
        messages.append({"role": "system", "content": (
            "If information is not present in your current context (not in memory, not in conversation history): "
            "say so directly and concisely. Never fabricate answers, invent logs, or guess at content that should come from files or prior sessions. "
            "NEVER say 'Memory updated', 'Saved to memory', or any variant. "
            "Memory is only saved when the system displays a green confirmation card with Accept/Dismiss buttons — that is the only real memory save path. "
            "Without that card, nothing is persisted. Do not simulate or pretend to save memory."
        )})

    if memory_enabled:
        if last_session:
            messages.append({"role": "user",      "content": f"[LAST SESSION]\n{last_session}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if graph_context:
            messages.append({"role": "user",      "content": f"[GRAPH CONTEXT]\n{graph_context}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if graph_facts:
            messages.append({"role": "user",      "content": f"[GRAPH FACTS]\n{graph_facts}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if memory_sheet:
            # conflicted facts suppressed until resolved
            if conflicted_facts:
                filtered = "\n".join(
                    l for l in memory_sheet.split("\n")
                    if l.strip() not in conflicted_facts
                )
            else:
                filtered = memory_sheet
            if filtered.strip():
                messages.append({"role": "system", "content": f"[USER STATE]\n{filtered}"})
        if workspace_memory:
            messages.append({"role": "user",      "content": f"[WORKSPACE STATE]\n{workspace_memory}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if project_summary:
            messages.append({"role": "user",      "content": f"[PROJECT STATE]\n{project_summary}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if retrieved_chunks:
            chunks_text = "\n\n".join(
                c["content"] if isinstance(c, dict) else c for c in retrieved_chunks
            )
            messages.append({"role": "user",      "content": f"[RELEVANT CONTEXT FROM EARLIER]\n{chunks_text}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if history_summary:
            messages.append({"role": "user",      "content": f"[EARLIER IN THIS CONVERSATION]\n{history_summary}"})
            messages.append({"role": "assistant", "content": "Understood."})

    messages += history

    if file_chunks:
        joined = "\n\n---\n\n".join(
            c["content"] if isinstance(c, dict) else c for c in file_chunks
        )
        messages.append({"role": "user",      "content": f"[FILE CONTEXT]\n{joined}"})
        messages.append({"role": "assistant", "content": "Understood, I will reference these documents in my response."})

    return messages


# ── Context Budget Allocator ─────────────────────────────────────────────────

_TIER_PREFIXES = [
    (8, re.compile(r'^\[LAST SESSION\]')),                            # drop first
    (7, re.compile(r'^\[FILE CONTEXT\]')),                            # drop second
    (6, re.compile(r'^\[RELEVANT CONTEXT')),                          # history / RAG
    (5, re.compile(r'^\[EARLIER IN THIS CONVERSATION\]')),            # conv summary
    (4, re.compile(r'^\[GRAPH (?:CONTEXT|FACTS)\]')),                 # graph
    (3, re.compile(r'^\[WORKSPACE STATE\]')),                         # workspace
    (2, re.compile(r'^\[PROJECT STATE\]')),                           # project
    (1, re.compile(r'^\[USER STATE\]')),                              # user state (keep)
]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _message_tier(msg: dict, is_last: bool) -> int:
    if is_last:
        return 0
    content = msg.get("content", "")
    if isinstance(content, list):
        return 0
    if msg["role"] == "system":
        return 0
    for tier, pattern in _TIER_PREFIXES:
        if pattern.match(content):
            return tier
    return 6


def _ack_idx(messages: list[dict], start: int) -> int | None:
    for i in range(start + 1, len(messages)):
        m = messages[i]
        if m["role"] == "assistant" and isinstance(m.get("content"), str) and m["content"].startswith("Understood"):
            return i
        if m["role"] != "assistant":
            return None
    return None


def _rebuild_user_state(content: str, fact_saliences: dict) -> str | None:
    """Keep only high-salience (>=0.5) facts from [USER STATE] block.
    Returns updated content or None if nothing changed."""
    lines = content.split("\n")
    header = lines[0] if lines else ""
    facts = lines[1:]
    high = []
    changed = False
    for l in facts:
        stripped = l.strip()
        if not stripped:
            high.append(l)
            continue
        score = fact_saliences.get(stripped, 1.0)
        if score >= 0.5:
            high.append(l)
        else:
            changed = True
    if not changed:
        return None
    rebuilt = "\n".join([header] + high) if header else "\n".join(high)
    return rebuilt.strip()


def apply_context_budget(
    messages: list[dict],
    context_window: int,
    max_output_tokens: int = 4096,
    fact_saliences: dict | None = None,
) -> list[dict]:
    if not messages:
        return messages

    reserve = max_output_tokens + int(context_window * 0.1)
    budget = context_window - reserve

    total = sum(_estimate_tokens(str(m.get("content", ""))) for m in messages)
    if total <= budget:
        return messages

    keep = [True] * len(messages)
    tiers: dict[int, list[int]] = {}
    for i, m in enumerate(messages):
        t = _message_tier(m, i == len(messages) - 1)
        tiers.setdefault(t, []).append(i)

    for tier in sorted(tiers.keys(), reverse=True):
        if tier == 0:
            break

        drop = set(tiers[tier])
        for idx in list(drop):
            ack = _ack_idx(messages, idx)
            if ack is not None:
                drop.add(ack)

        # Partial drop for [USER STATE] — keep high-salience facts
        if tier == 1 and fact_saliences:
            for idx in list(drop):
                content = messages[idx].get("content", "")
                rebuilt = _rebuild_user_state(content, fact_saliences)
                if rebuilt is not None and rebuilt:
                    keep[idx] = True
                    drop.discard(idx)
                    messages[idx] = {**messages[idx], "content": rebuilt}
                elif rebuilt is not None and not rebuilt:
                    keep[idx] = False
            if not drop:
                new_total = sum(
                    _estimate_tokens(str(messages[i].get("content", "")))
                    for i, k in enumerate(keep) if k
                )
                if new_total <= budget:
                    return [m for i, m in enumerate(messages) if keep[i]]

        new_keep = list(keep)
        for idx in drop:
            new_keep[idx] = False

        new_total = sum(
            _estimate_tokens(str(messages[i].get("content", "")))
            for i, k in enumerate(new_keep) if k
        )
        if new_total <= budget:
            return [m for m, k in zip(messages, new_keep) if k]

        keep = new_keep

    return [m for m, k in zip(messages, keep) if k]
