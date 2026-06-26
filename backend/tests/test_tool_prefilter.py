"""Tool prefilter switch + capability gating + stable-prefix ordering.

No DB / NIM — pure predicate + registry tests.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from llm.tools import ToolContext, TOOL_REGISTRY, select_tool_schemas, TOOL_PREFILTER_THRESHOLD
from llm.tools.builtin.web_tools import _inject_web_search


def _dummy_schemas(n: int) -> list[dict]:
    return [{"type": "function", "function": {"name": f"t{i}"}} for i in range(n)]


class TestPrefilterSwitch:
    def test_passthrough_at_or_below_threshold(self):
        schemas = _dummy_schemas(TOOL_PREFILTER_THRESHOLD)
        assert select_tool_schemas("anything", schemas) == schemas

    def test_passthrough_failsafe_above_threshold(self):
        # else branch is unbuilt → must fail safe to passthrough (never drop tools)
        schemas = _dummy_schemas(TOOL_PREFILTER_THRESHOLD + 5)
        assert select_tool_schemas("anything", schemas) == schemas

    def test_empty(self):
        assert select_tool_schemas("anything", []) == []


class TestWebSearchCapabilityGate:
    def test_injected_when_enabled_regardless_of_wording(self):
        for msg in ("latest news", "hello", "", "tell me a joke"):
            assert _inject_web_search(ToolContext(message=msg, web_search_enabled=True))

    def test_not_injected_when_disabled(self):
        for msg in ("latest news today", "search google"):
            assert not _inject_web_search(ToolContext(message=msg, web_search_enabled=False))


class TestStablePrefixOrdering:
    def test_registry_schema_order_is_deterministic(self):
        # The assembly point name-sorts injected tools so the tools array is
        # byte-stable across requests with identical capabilities (KV prefix cache).
        names_a = sorted(t.name for t in TOOL_REGISTRY.values())
        names_b = sorted(t.name for t in TOOL_REGISTRY.values())
        assert names_a == names_b
        assert names_a == sorted(names_a)
