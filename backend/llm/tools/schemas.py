TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files attached to the current conversation with their IDs.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full text content of a file by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "UUID of the file to read."},
                },
                "required": ["file_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Overwrite a file with COMPLETE new content. "
                "WARNING: this replaces the ENTIRE file — any content not included is permanently lost. "
                "NEVER use this for partial updates or section edits — use patch_file instead. "
                "ALWAYS call read_file first to get the full current content, then rewrite it in full. "
                "Only use write_file when you intend to replace everything."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "UUID of the file to update."},
                    "content": {"type": "string", "description": "New full text content of the file."},
                },
                "required": ["file_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new text file and attach it to the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":    {"type": "string", "description": "Filename (e.g. notes.txt)."},
                    "content": {"type": "string", "description": "Text content of the new file."},
                },
                "required": ["name", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_file",
            "description": "Append text to the end of a file without touching existing content. Use this instead of write_file when adding new content (paragraphs, sections, notes).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "UUID of the file to append to."},
                    "content": {"type": "string", "description": "Text to append at the end of the file."},
                },
                "required": ["file_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Replace a specific passage in a file with new text. Safer than write_file — only changes the matched section, preserves everything else. Use when editing or rewriting a specific part.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id":  {"type": "string", "description": "UUID of the file to patch."},
                    "old_text": {"type": "string", "description": "Exact text to find and replace (must match the file exactly)."},
                    "new_text": {"type": "string", "description": "Replacement text."},
                },
                "required": ["file_id", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_file",
            "description": "Semantic search within a specific file. Returns top matching passages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "UUID of the file to search."},
                    "query":   {"type": "string", "description": "Search query."},
                },
                "required": ["file_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_across_files",
            "description": "Semantic search across ALL files attached to the conversation at once. Use when you don't know which file contains the information, or when synthesizing across multiple files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "Ask the user a clarifying question before proceeding with a destructive operation "
                "(write_file, patch_file, create_file). Use when the user's intent is ambiguous or "
                "the edit could cause irreversible data loss. Calling this tool ends the current "
                "operation — the user's reply will be the next message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The clarifying question to ask the user."},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_graph",
            "description": "Search the user's knowledge graph for entities and relationships related to a topic, person, or concept.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic, person, or concept to search for."},
                },
                "required": ["query"],
            },
        },
    },
]

WRITE_MEMORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_memory",
        "description": (
            "Propose saving a significant, durable fact about the user to long-term memory. "
            "ONLY call this when the user has explicitly shared something that would be valuable "
            "across many future conversations — e.g. a stated preference, personal background, "
            "professional context, or explicit goal. "
            "Do NOT call this for greetings, single-use context, transient questions, or anything "
            "that would not be useful to recall in a completely different future conversation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "The fact about the user to record."},
            },
            "required": ["fact"],
        },
    },
}
