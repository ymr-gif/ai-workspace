"""MCP extension point (DESIGN STUB — not implemented).

The tool registry is the seam where MCP plugs in. Stable contract:
    "to add any tool — local or remote — build a `Tool` and `register_tool` it."

Two future directions, both leave `generate_stream`'s loop untouched:

1. EXPOSE our tools AS an MCP server (`server.py`):
   one adapter iterates `TOOL_REGISTRY` →
     - list_tools  → `Tool.schema["function"]` (already JSON-Schema) per tool
     - call_tool(name, args) → build a server-side `ToolContext` from the MCP
       session's auth, then `run_tool(name, args, ctx)`.

2. CONSUME external MCP tools (`client.py`):
   connect to a remote MCP server, and for each remote tool build a `Tool` whose
   `schema` wraps the remote inputSchema and whose `execute = lambda args, ctx:
   <jsonrpc call>`, then `register_tool(...)` it into the SAME `TOOL_REGISTRY`.
   The chat loop can't tell remote tools from in-process ones.

Nothing here is wired yet — this package documents the contract so the registry
stays MCP-ready without paying the protocol/ops cost today.
"""
