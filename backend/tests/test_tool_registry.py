"""Tool registry invariants + injection-parity net for the registry refactor."""

import uuid

from llm.tools import TOOL_REGISTRY, ToolContext
from llm.tools.schemas import SCHEMA_BY_NAME

EXPECTED = {
    "list_files", "read_file", "write_file", "create_file", "append_to_file",
    "patch_file", "search_in_file", "search_across_files", "query_graph",
    "ask_user", "write_memory", "web_search", "fetch_url",
    "drive_list_files", "drive_read_file", "drive_search",
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


def test_inject_write_memory_only_on_reasoning_and_request():
    assert _inject(message="remember that I like tea", db=_DB, user_id=1, is_reasoning=True) == {"write_memory"}
    assert _inject(message="remember that I like tea", db=_DB, user_id=1, is_reasoning=False) == set()


def test_inject_fetch_url_on_url():
    assert _inject(message="summarize https://example.com", db=_DB, user_id=1) == {"fetch_url"}


def test_inject_web_search_needs_flag_and_keyword():
    assert _inject(message="latest news today", db=_DB, user_id=1, web_search_enabled=True) == {"web_search"}
    assert _inject(message="latest news today", db=_DB, user_id=1, web_search_enabled=False) == set()


def test_inject_drive_full_gate_handles_punctuation():
    assert _inject(message="can you check my drive?", db=_DB, user_id=1, drive_active=True) == {
        "drive_list_files", "drive_read_file", "drive_search",
    }


def test_inject_drive_read_only_on_cache_followup():
    # no Drive keyword, but a prior listing (cache) + read intent → read tool only
    assert _inject(message="read JARVIS Test Note", db=_DB, user_id=1,
                   drive_active=True, drive_cache_active=True) == {"drive_read_file"}
    # cache active but no read intent → nothing
    assert _inject(message="thanks", db=_DB, user_id=1,
                   drive_active=True, drive_cache_active=True) == set()


def test_inject_nothing_when_drive_inactive():
    assert _inject(message="check my drive", db=_DB, user_id=1, drive_active=False) == set()
