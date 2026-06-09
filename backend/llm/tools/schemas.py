def _tool(
    name: str,
    description: str,
    properties: dict | None = None,
    required: list[str] | None = None,
) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


TOOL_SCHEMAS = [
    _tool("list_files", "List all files attached to the current conversation with their IDs."),
    _tool("read_file", "Read the full text content of a file by its ID.",
          {"file_id": {"type": "string", "description": "UUID of the file to read."}},
          ["file_id"]),
    _tool("write_file", (
        "Overwrite a file with COMPLETE new content. "
        "WARNING: this replaces the ENTIRE file — any content not included is permanently lost. "
        "NEVER use this for partial updates or section edits — use patch_file instead. "
        "ALWAYS call read_file first to get the full current content, then rewrite it in full. "
        "Only use write_file when you intend to replace everything."
    ), {
        "file_id": {"type": "string", "description": "UUID of the file to update."},
        "content": {"type": "string", "description": "New full text content of the file."},
    }, ["file_id", "content"]),
    _tool("create_file", "Create a new text file and attach it to the conversation.",
          {"name": {"type": "string", "description": "Filename (e.g. notes.txt)."},
           "content": {"type": "string", "description": "Text content of the new file."}},
          ["name", "content"]),
    _tool("append_to_file", (
        "Append text to the end of a file without touching existing content. "
        "ONLY use when the user explicitly asks to add, append, or write something INTO the file. "
        "NEVER use to answer questions — if asked to 'list', 'show', 'explain', 'summarize', or 'describe' content, respond in chat text instead."
    ), {
        "file_id": {"type": "string", "description": "UUID of the file to append to."},
        "content": {"type": "string", "description": "Text to append at the end of the file."},
    }, ["file_id", "content"]),
    _tool("patch_file", "Replace a specific passage in a file with new text. Safer than write_file — only changes the matched section, preserves everything else. Use when editing or rewriting a specific part.",
          {"file_id": {"type": "string", "description": "UUID of the file to patch."},
           "old_text": {"type": "string", "description": "Exact text to find and replace (must match the file exactly)."},
           "new_text": {"type": "string", "description": "Replacement text."}},
          ["file_id", "old_text", "new_text"]),
    _tool("search_in_file", "Semantic search within a specific file. Returns top matching passages.",
          {"file_id": {"type": "string", "description": "UUID of the file to search."},
           "query": {"type": "string", "description": "Search query."}},
          ["file_id", "query"]),
    _tool("search_across_files", "Semantic search across ALL files attached to the conversation at once. Use when you don't know which file contains the information, or when synthesizing across multiple files.",
          {"query": {"type": "string", "description": "Search query."}},
          ["query"]),
    _tool("ask_user", (
        "Ask the user a clarifying question before proceeding with a destructive operation "
        "(write_file, patch_file, create_file). Use when the user's intent is ambiguous or "
        "the edit could cause irreversible data loss. Calling this tool ends the current "
        "operation — the user's reply will be the next message."
    ), {
        "question": {"type": "string", "description": "The clarifying question to ask the user."},
    }, ["question"]),
    _tool("query_graph", "Search the user's knowledge graph for entities and relationships related to a topic, person, or concept.",
          {"query": {"type": "string", "description": "Topic, person, or concept to search for."}},
          ["query"]),
]

FILE_TOOL_SCHEMAS = TOOL_SCHEMAS

WRITE_MEMORY_SCHEMA = _tool("write_memory", (
    "Propose saving a significant, durable fact about the user to long-term memory. "
    "ONLY call this when the user explicitly says 'remember', 'save', 'store', 'keep in memory', or similar direct instructions. "
    "NEVER call this when answering a question, reading a file, summarizing content, or when the user simply states a fact mid-conversation. "
    "The user must be directly instructing you to save something — inference is not enough."
), {
    "fact": {"type": "string", "description": "The fact about the user to record."},
}, ["fact"])
