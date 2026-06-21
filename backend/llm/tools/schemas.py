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

WEB_SEARCH_TOOL_SCHEMA = [_tool(
    "web_search",
    (
        "Search the web for current, live information. Use when the user asks about "
        "recent events, news, current prices, weather, scores, or anything that may "
        "have changed after your training cutoff."
    ),
    {"query": {"type": "string", "description": "Search query"}},
    ["query"],
)]

FETCH_URL_TOOL_SCHEMA = [_tool(
    "fetch_url",
    (
        "Fetch and read the full text content of a web page at a given URL. "
        "Use when the user provides a URL to read, summarize, or analyze."
    ),
    {"url": {"type": "string", "description": "The full URL to fetch (must start with http:// or https://)."}},
    ["url"],
)]

DRIVE_TOOL_SCHEMAS = [
    _tool("drive_list_files",
          "List files in the user's Google Drive. The optional query filters by file NAME or type "
          "(e.g. 'name contains goal') — it is NOT a content search. For content search use drive_search. "
          "After listing, call drive_read_file ONLY for files directly relevant to the user's request — "
          "do NOT read every file in the list.",
          {"query": {"type": "string", "description": "Optional Drive API name/type filter (e.g. \"name contains 'goal'\")"}},
          []),
    _tool("drive_read_file",
          "Read the full content of a Google Drive file. Accepts the file's Drive ID, OR — if files were "
          "already listed or searched earlier in this conversation — the exact file NAME (the system resolves "
          "the name to its ID). When the user names a file to read, call this DIRECTLY with that name; do NOT "
          "call drive_list_files again just to obtain an ID you can already resolve. "
          "ONLY call this when the user explicitly names or requests a specific file to read.",
          {"file_id": {"type": "string", "description": "The Drive file ID, or the exact file name from a prior listing/search in this conversation"}},
          ["file_id"]),
    _tool("drive_search",
          "Search Google Drive for files containing specific content or matching a name. "
          "Use this when you need to find files by what they contain. "
          "After searching, call drive_read_file ONLY for files directly relevant to the user's request.",
          {"query": {"type": "string", "description": "What to search for in file content or names"}},
          ["query"]),
]

WRITE_MEMORY_SCHEMA = _tool("write_memory", (
    "Propose saving a significant, durable fact about the user to long-term memory. "
    "ONLY call this when the user explicitly says 'remember', 'save', 'store', 'keep in memory', or similar direct instructions. "
    "NEVER call this when answering a question, reading a file, summarizing content, or when the user simply states a fact mid-conversation. "
    "The user must be directly instructing you to save something — inference is not enough."
), {
    "fact": {"type": "string", "description": "The fact about the user to record."},
}, ["fact"])


# name → schema dict, for the tool registry (builtin tools reference these; zero retyping/drift).
CALENDAR_TOOL_SCHEMAS = [
    _tool("calendar_list_events",
          "List upcoming events from the user's primary Google Calendar. "
          "Optional timeMin/timeMax filter by ISO 8601 timestamp. "
          "Defaults to showing events from now onwards.",
          {"time_min": {"type": "string", "description": "Optional ISO 8601 start of range (default: now)"},
           "time_max": {"type": "string", "description": "Optional ISO 8601 end of range"},
           "max_results": {"type": "integer", "description": "Max events to return (default 20)"}},
          []),
    _tool("calendar_get_event",
          "Get full details of a specific calendar event by its ID.",
          {"event_id": {"type": "string", "description": "The event ID to fetch"}},
          ["event_id"]),
    _tool("calendar_search_events",
          "Search the user's primary calendar events by keyword. Matches summary, description, location, and attendees.",
          {"query": {"type": "string", "description": "Search terms"}},
          ["query"]),
    _tool("calendar_create_event",
          "Create a new event on the user's primary calendar.",
          {"summary": {"type": "string", "description": "Event title"},
           "start": {"type": "string", "description": "ISO 8601 start datetime"},
           "end": {"type": "string", "description": "ISO 8601 end datetime"},
           "description": {"type": "string", "description": "Optional event description"},
           "location": {"type": "string", "description": "Optional event location"}},
          ["summary", "start", "end"]),
    _tool("calendar_update_event",
          "Update an existing calendar event. Only provided fields are changed.",
          {"event_id": {"type": "string", "description": "The event ID to update"},
           "summary": {"type": "string", "description": "Optional new title"},
           "start": {"type": "string", "description": "Optional ISO 8601 start datetime"},
           "end": {"type": "string", "description": "Optional ISO 8601 end datetime"},
           "description": {"type": "string", "description": "Optional new description"},
           "location": {"type": "string", "description": "Optional new location"}},
          ["event_id"]),
    _tool("calendar_delete_event",
          "Delete an event from the user's primary calendar.",
          {"event_id": {"type": "string", "description": "The event ID to delete"}},
          ["event_id"]),
]

GMAIL_TOOL_SCHEMAS = [
    _tool("gmail_list_messages",
          "List recent messages from the user's Gmail inbox. "
          "Returns message previews (subject, sender, date, snippet). "
          "To read the full content of a specific message, use gmail_get_message with its ID.",
          {"max_results": {"type": "integer", "description": "Max messages to list (default 20)"}},
          []),
    _tool("gmail_get_message",
          "Read the full content of a specific Gmail message by its ID. "
          "Returns the complete email body (subject, from, date, and text content).",
          {"message_id": {"type": "string", "description": "The Gmail message ID to retrieve"}},
          ["message_id"]),
    _tool("gmail_search_messages",
          "Search the user's Gmail inbox for messages matching a query. "
          "Supports Gmail search operators (e.g. 'from:user@example.com', 'subject:meeting', 'has:attachment'). "
          "Returns matching message previews. Use gmail_get_message to read the full content.",
          {"query": {"type": "string", "description": "Search query (supports Gmail operators)"},
           "max_results": {"type": "integer", "description": "Max results to return (default 10)"}},
          ["query"]),
]

SCHEMA_BY_NAME = {
    s["function"]["name"]: s
    for s in [
        *TOOL_SCHEMAS,
        *WEB_SEARCH_TOOL_SCHEMA,
        *FETCH_URL_TOOL_SCHEMA,
        *DRIVE_TOOL_SCHEMAS,
        *CALENDAR_TOOL_SCHEMAS,
        *GMAIL_TOOL_SCHEMAS,
        WRITE_MEMORY_SCHEMA,
    ]
}
