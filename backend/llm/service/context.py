_FILE_OP_KEYWORDS = frozenset({
    "read", "write", "edit", "update", "create", "append", "patch",
    "search", "find", "fix", "change", "modify", "file", "document",
    "documents", "content", "add", "remove", "delete", "replace",
    "rewrite", "summarize", "analyse", "analyze", "open", "insert",
    "correct", "improve", "refactor", "rename", "review", "check",
})


def _needs_file_tools(message: str) -> bool:
    tokens = set(message.lower().split())
    return bool(tokens & _FILE_OP_KEYWORDS)


def build_context_messages(
    memory_sheet:     str,
    project_summary:  str,
    retrieved_chunks: list[str],
    history_summary:  str,
    history:          list[dict],
    memory_enabled:   bool,
    system_prompt:    str | None = None,
    file_chunks:      list[str]  = (),
    file_names:       list[str]  = (),
    file_ids:         list       = (),
    workspace_memory: str        = "",
    graph_context:    str        = "",
) -> list[dict]:
    messages = []

    if file_names:
        if file_ids:
            files_list  = "\n".join(f"  - {name} (id={fid})" for name, fid in zip(file_names, file_ids))
            file_notice = (
                f"The user has attached these files:\n{files_list}\n"
                "Rules for file tools:\n"
                "- ONLY use tools when the user explicitly asks to read, edit, write, search, or create files.\n"
                "- For conversational messages, acknowledgments, or questions not about file content: respond normally with NO tool calls.\n"
                "- To ADD content (new paragraph, section, notes): use append_to_file — safest, never loses existing content\n"
                "- To EDIT a specific passage: use read_file first, then patch_file(old_text=<exact passage>, new_text=<replacement>)\n"
                "- To REWRITE the whole file: use write_file with the COMPLETE new content\n"
                "- To CREATE a new file: use create_file\n"
                "- After any write/append/patch/create succeeds, respond to the user immediately — do NOT read the file back to verify\n"
                "- Never call the same tool more than twice in a single turn"
            )
        else:
            file_notice = f"The user has attached these files: {', '.join(file_names)}. Use file tools to read or edit them."
        base = system_prompt.rstrip() + "\n\n" + file_notice if system_prompt else file_notice
        messages.append({"role": "system", "content": base})
    elif system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if memory_enabled:
        if graph_context:
            messages.append({"role": "user",      "content": f"[GRAPH CONTEXT]\n{graph_context}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if memory_sheet:
            messages.append({"role": "system",    "content": f"[USER STATE]\n{memory_sheet}"})
        if workspace_memory:
            messages.append({"role": "user",      "content": f"[WORKSPACE STATE]\n{workspace_memory}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if project_summary:
            messages.append({"role": "user",      "content": f"[PROJECT STATE]\n{project_summary}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if retrieved_chunks:
            chunks_text = "\n\n".join(retrieved_chunks)
            messages.append({"role": "user",      "content": f"[RELEVANT CONTEXT FROM EARLIER]\n{chunks_text}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if history_summary:
            messages.append({"role": "user",      "content": f"[EARLIER IN THIS CONVERSATION]\n{history_summary}"})
            messages.append({"role": "assistant", "content": "Understood."})

    messages += history

    if file_chunks:
        joined = "\n\n---\n\n".join(file_chunks)
        messages.append({"role": "user",      "content": f"[FILE CONTEXT]\n{joined}"})
        messages.append({"role": "assistant", "content": "Understood, I will reference these documents in my response."})

    return messages
