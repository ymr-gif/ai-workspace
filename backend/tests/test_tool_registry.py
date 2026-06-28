"""Tool registry invariants + injection-parity net for the registry refactor."""

import uuid

from llm.tools import TOOL_REGISTRY, ToolContext
from llm.tools.schemas import SCHEMA_BY_NAME

EXPECTED = {
    "list_files", "read_file", "write_file", "create_file", "append_to_file",
    "patch_file", "search_in_file", "search_across_files", "query_graph",
    "ask_user", "write_memory", "web_search", "fetch_url",
    "drive_list_files", "drive_read_file", "drive_search",
    "calendar_list_events", "calendar_get_event", "calendar_search_events",
    "calendar_create_event", "calendar_update_event", "calendar_delete_event",
    "gmail_list_messages", "gmail_get_message", "gmail_search_messages",
}

_DB = object()   # sentinel: predicates only check `db is not None`
_CID = uuid.uuid4()


def _inject(**kw) -> set[str]:
    ctx = ToolContext(**kw)
    return {t.name for t in TOOL_REGISTRY.values() if t.should_inject(ctx)}


def test_all_expected_tools_registered():
    assert set(TOOL_REGISTRY) == EXPECTED


def test_schema_matches_source_no_drift():
    for name, tool in TOOL_REGISTRY.items():
        assert tool.schema is SCHEMA_BY_NAME[name]
        assert tool.schema["function"]["name"] == name


def test_list_tools_have_single_call_limit():
    for name in ("list_files", "drive_list_files", "drive_search"):
        t = TOOL_REGISTRY[name]
        assert t.is_list_tool and t.max_identical_calls == 1


def test_inject_file_group_when_files_attached():
    assert _inject(message="edit my file", db=_DB, user_id=1, conv_id=_CID, file_ids=("f",)) == {
        "list_files", "read_file", "write_file", "create_file", "append_to_file",
        "patch_file", "search_in_file", "search_across_files", "query_graph", "ask_user",
    }


# --- Capability gating (keyword pre-filter removed; model decides via schemas) ---

def test_inject_write_memory_on_reasoning_with_explicit_intent():
    # Gate = reasoning model + db + explicit memory-write keyword in message.
    assert _inject(message="remember that I like tea", db=_DB, user_id=1, is_reasoning=True) == {"write_memory"}
    assert _inject(message="hi", db=_DB, user_id=1, is_reasoning=True) == set()
    assert _inject(message="remember that I like tea", db=_DB, user_id=1, is_reasoning=False) == set()


def test_inject_fetch_url_on_url():
    # URL presence is a capability (nothing to fetch otherwise) — preserved.
    assert _inject(message="summarize https://example.com", db=_DB, user_id=1) == {"fetch_url"}
    assert _inject(message="summarize this for me", db=_DB, user_id=1) == set()


def test_inject_fetch_url_from_history():
    # fetch_url offered when a URL appeared in recent conversation (not just current message).
    history_with_url = [
        {"role": "user", "content": "check out https://example.com"},
        {"role": "assistant", "content": "Sure, let me fetch that."},
    ]
    assert _inject(message="now summarize it", db=_DB, user_id=1, history=history_with_url) == {"fetch_url"}
    # No URL anywhere → not offered
    assert _inject(message="now summarize it", db=_DB, user_id=1, history=[]) == set()


def test_inject_web_search_on_flag_regardless_of_wording():
    assert _inject(message="hello", db=_DB, user_id=1, web_search_enabled=True) == {"web_search"}
    assert _inject(message="latest news today", db=_DB, user_id=1, web_search_enabled=False) == set()


def test_inject_drive_all_tools_when_active_and_latched():
    # Q3 Task B: drive_active alone is not enough — session must also be latched.
    expected = {"drive_list_files", "drive_read_file", "drive_search"}
    assert _inject(message="hello there", db=_DB, user_id=1, drive_active=True, drive_latched=True) == expected
    assert _inject(message="hello there", db=_DB, user_id=1, drive_active=True, drive_latched=False) == set()


def test_inject_nothing_when_drive_inactive():
    assert _inject(message="check my drive", db=_DB, user_id=1, drive_active=False) == set()
