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
    _tool("create_canvas_node", "Create a new node on your canvas. Node types: input, session, memory, files, logs, usage, workspace, config, insights, goals, automations, mech.",
          {"node_type": {"type": "string", "description": "Type of node to create (see node inventory)."},
           "config": {"type": "object", "description": "Optional config for the node (e.g. workspace_id, conversation_id)."}},
          ["node_type"]),
    _tool("delete_canvas_node", "Permanently remove a node and all its connections from your canvas.",
          {"node_id": {"type": "string", "description": "UUID of the node to delete."}},
          ["node_id"]),
    _tool("update_canvas_node", "Update a node's config or status on your canvas.",
          {"node_id": {"type": "string", "description": "UUID of the node to update."},
           "config": {"type": "object", "description": "New config values to merge."},
           "status": {"type": "string", "description": "New status (active, paused, archived)."}},
          ["node_id"]),
    _tool("wire_nodes", "Connect two nodes. src_port must be an output of the source node, dst_port must be an input of the destination.",
          {"src_id": {"type": "string", "description": "Source node UUID."},
           "dst_id": {"type": "string", "description": "Destination node UUID."},
           "src_port": {"type": "string", "description": "Output port on source (e.g. 'response', 'content')."},
           "dst_port": {"type": "string", "description": "Input port on destination (e.g. 'query', 'filter')."},
           "relation": {"type": "string", "description": "Label for this connection (e.g. 'analyzes', 'contains', 'feeds')."}},
          ["src_id", "dst_id", "src_port", "dst_port", "relation"]),
    _tool("unwire_nodes", "Remove all connections between two nodes.",
          {"src_id": {"type": "string", "description": "Source node UUID."},
           "dst_id": {"type": "string", "description": "Destination node UUID."}},
          ["src_id", "dst_id"]),
    _tool("query_canvas", "Inspect your canvas with a Cypher query. Read-only. Always filter by user_id: MATCH (n:CanvasNode {user_id: $uid}).",
          {"cypher": {"type": "string", "description": "Cypher MATCH/RETURN query. Must include {user_id: $uid}."}},
          ["cypher"]),
    _tool("get_canvas_graph", "Return your full canvas — all active nodes and their connections."),
    _tool("create_conversation",
          "Create a new conversation (session) in the database. Returns the conversation_id. "
          "After creating, call create_canvas_node(type='session', config={'conversation_id': <id>}) to visualize it on the canvas.",
          {"title":        {"type": "string", "description": "Short title for the conversation."},
           "workspace_id": {"type": "string", "description": "Optional workspace UUID to scope the conversation."}},
          ["title"]),
    _tool("create_workspace",
          "Create a new workspace in the database. Returns the workspace_id. "
          "After creating, call create_canvas_node(type='workspace', config={'workspace_id': <id>}) to visualize it on the canvas.",
          {"name":          {"type": "string", "description": "Workspace name."},
           "description":   {"type": "string", "description": "Optional description."},
           "system_prompt": {"type": "string", "description": "Optional system prompt applied to all sessions in this workspace."}},
          ["name"]),
]

WRITE_MEMORY_SCHEMA = _tool("write_memory", (
    "Propose saving a significant, durable fact about the user to long-term memory. "
    "ONLY call this when the user explicitly says 'remember', 'save', 'store', 'keep in memory', or similar direct instructions. "
    "NEVER call this when answering a question, reading a file, summarizing content, or when the user simply states a fact mid-conversation. "
    "The user must be directly instructing you to save something — inference is not enough."
), {
    "fact": {"type": "string", "description": "The fact about the user to record."},
}, ["fact"])
