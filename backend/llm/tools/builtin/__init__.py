"""Built-in tools — imported for side-effect registration into TOOL_REGISTRY.

Each submodule calls `register_tool(...)` at import time (same pattern as the
integrations connectors). `llm/tools/__init__.py` imports this package so the
registry is populated whenever the tools package is used.

Modules are added here as tool groups are ported into the registry.
"""

from . import file_tools      # noqa: F401
from . import memory_tools    # noqa: F401
from . import web_tools       # noqa: F401
from . import drive_tools     # noqa: F401
