"""write_memory injection gate (over-fire fix) — pure unit, no NIM/DB.

write_memory must be offered only on a reasoning turn that shows explicit
memory-write intent (`_needs_memory_tool`). Greetings / questions / coding must
NOT inject it (they were causing junk memory writes + empty replies).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from llm.tools import ToolContext
from llm.tools.builtin.memory_tools import _inject_write_memory

_DB = object()  # any non-None stands in for a DB session


def test_not_injected_on_greetings_and_trivial_turns():
    for msg in ("hello?", "ehllo", "thanks", "what is up?", "good morning"):
        assert not _inject_write_memory(ToolContext(message=msg, db=_DB, is_reasoning=True))


def test_not_injected_on_substantive_non_memory_turns():
    # The exact turns the embedding mis-scored high (summarize 0.75 etc.) — keyword gate blocks them.
    for msg in ("summarize the paragraph I just pasted", "help me debug this stack trace",
                "can you refactor this function", "what files do I have in my drive"):
        assert not _inject_write_memory(ToolContext(message=msg, db=_DB, is_reasoning=True))


def test_injected_on_explicit_memory_intent():
    for msg in ("remember I prefer metric units", "please memorize my timezone",
                "remember that I'm vegetarian"):
        assert _inject_write_memory(ToolContext(message=msg, db=_DB, is_reasoning=True))


def test_requires_reasoning_model():
    # Even an explicit memory request: 8B can't reliably use tools, so don't inject.
    assert not _inject_write_memory(ToolContext(message="remember I like tabs", db=_DB, is_reasoning=False))


def test_requires_db():
    assert not _inject_write_memory(ToolContext(message="remember I like tabs", db=None, is_reasoning=True))
