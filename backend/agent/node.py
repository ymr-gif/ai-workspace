from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    name: str
    label: str
    ports: dict[str, list[str]]
    tools: list[dict]
    default_config: dict | None = None


registry: dict[str, Node] = {
    "input": Node(
        name="input",
        label="Route messages",
        ports={"input": [], "output": ["routed_message"]},
        tools=[
            {"name": "route_message", "description": "Route an incoming message to a target node"},
            {"name": "set_session_target", "description": "Set the default target node for messages"},
        ],
    ),
    "session": Node(
        name="session",
        label="Manage conversations",
        ports={"input": ["message"], "output": ["response", "metadata"]},
        tools=[
            {"name": "create_conversation", "description": "Create a new conversation"},
            {"name": "delete_conversation", "description": "Delete an existing conversation"},
            {"name": "list_conversations", "description": "List all conversations"},
            {"name": "list_messages", "description": "List messages in a conversation"},
            {"name": "get_conversation", "description": "Get a conversation by ID"},
        ],
    ),
    "memory": Node(
        name="memory",
        label="Read/write/search memory",
        ports={"input": ["query"], "output": ["results"]},
        tools=[
            {"name": "read_memory", "description": "Read user memory facts"},
            {"name": "write_memory", "description": "Write a fact to user memory"},
            {"name": "search_memory", "description": "Search memory by keyword"},
            {"name": "query_graph", "description": "Query the Neo4j knowledge graph"},
            {"name": "resolve_conflict", "description": "Resolve a memory conflict"},
        ],
    ),
    "files": Node(
        name="files",
        label="Read/write/search files",
        ports={"input": ["file_id"], "output": ["content", "chunks"]},
        tools=[
            {"name": "list_files", "description": "List uploaded files"},
            {"name": "read_file", "description": "Read file contents"},
            {"name": "write_file", "description": "Write content to a file"},
            {"name": "create_file", "description": "Create a new file"},
            {"name": "append_to_file", "description": "Append content to a file"},
            {"name": "patch_file", "description": "Patch a file with fuzzy matching"},
            {"name": "search_in_file", "description": "Search within a single file"},
            {"name": "search_across_files", "description": "Search across multiple files"},
            {"name": "retrieve_chunks", "description": "Retrieve file chunks by similarity"},
        ],
    ),
    "logs": Node(
        name="logs",
        label="Query tool/audit logs",
        ports={"input": ["filter"], "output": ["entries"]},
        tools=[
            {"name": "query_tool_logs", "description": "Query tool call logs"},
            {"name": "query_audit_log", "description": "Query admin audit log"},
        ],
    ),
    "usage": Node(
        name="usage",
        label="Check cost and usage stats",
        ports={"input": ["query"], "output": ["stats"]},
        tools=[
            {"name": "get_usage_stats", "description": "Get usage statistics"},
            {"name": "get_token_count", "description": "Get token count for a period"},
            {"name": "check_cost", "description": "Check current cost balance"},
        ],
    ),
    "workspace": Node(
        name="workspace",
        label="Manage workspaces",
        ports={"input": ["workspace_id"], "output": ["config", "members"]},
        tools=[
            {"name": "create_workspace", "description": "Create a new workspace"},
            {"name": "update_workspace", "description": "Update workspace settings"},
            {"name": "delete_workspace", "description": "Delete a workspace"},
            {"name": "get_workspace", "description": "Get workspace details"},
            {"name": "set_active_workspace", "description": "Set the active workspace"},
        ],
    ),
    "config": Node(
        name="config",
        label="Change model/params/settings",
        ports={"input": ["request"], "output": ["model_config"]},
        tools=[
            {"name": "set_model", "description": "Set the active model"},
            {"name": "set_params", "description": "Set model parameters"},
            {"name": "get_system_prompt", "description": "Get the system prompt"},
            {"name": "toggle_memory", "description": "Enable or disable memory"},
            {"name": "get_circuit_status", "description": "Get circuit breaker status"},
            {"name": "probe_models", "description": "Probe model health"},
        ],
    ),
    "insights": Node(
        name="insights",
        label="Generate and manage insights",
        ports={"input": ["context"], "output": ["insight"]},
        tools=[
            {"name": "generate_insight", "description": "Generate a user insight"},
            {"name": "dismiss_insight", "description": "Dismiss an insight"},
            {"name": "list_insights", "description": "List all insights"},
        ],
    ),
    "goals": Node(
        name="goals",
        label="Track and manage goals",
        ports={"input": ["action"], "output": ["status"]},
        tools=[
            {"name": "create_goal", "description": "Create a new goal"},
            {"name": "update_goal", "description": "Update a goal"},
            {"name": "complete_goal", "description": "Mark a goal as completed"},
            {"name": "delete_goal", "description": "Delete a goal"},
            {"name": "list_goals", "description": "List all goals"},
            {"name": "link_conversation", "description": "Link a conversation to a goal"},
        ],
    ),
    "automations": Node(
        name="automations",
        label="Manage scheduled prompts",
        ports={"input": ["trigger"], "output": ["result"]},
        tools=[
            {"name": "create_automation", "description": "Create a new automation"},
            {"name": "trigger_automation", "description": "Trigger an automation"},
            {"name": "toggle_automation", "description": "Enable or disable an automation"},
            {"name": "delete_automation", "description": "Delete an automation"},
            {"name": "list_automations", "description": "List all automations"},
        ],
    ),
    "mech": Node(
        name="mech",
        label="Execute custom plugin modules",
        ports={"input": ["module", "data"], "output": ["module_output"]},
        tools=[
            {"name": "execute_module", "description": "Execute a custom module"},
            {"name": "list_modules", "description": "List available modules"},
        ],
    ),
}


def get_node_type(name: str) -> Node | None:
    return registry.get(name)
