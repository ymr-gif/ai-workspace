"""Live: /chat/stream end-to-end against a real model. The headline gap-fill.

Verifies SSE token streaming, the terminal `done` event payload, and that the
assistant message + grounding metadata persist. Marker: live_nim.
"""
import pytest

pytestmark = pytest.mark.live_nim

_DONE_KEYS = {
    "model", "cache_hit", "fallback_used", "query_type", "intent",
    "src_count", "total_tokens", "prompt_tokens", "completion_tokens",
    "cost_usd", "conversation_id", "grounding", "activity",
    "web_searched", "url_fetched",
}
_QUERY_TYPES = {"factual", "relational", "temporal", "broad"}
_INTENTS = {"task", "question", "exploration"}


def _stream_one(sse_post, user_headers, message, **extra):
    events = sse_post("/chat/stream", user_headers, {"message": message, **extra})
    assert events, "no SSE events received"
    done = next((e for e in events if e.get("type") == "done"), None)
    assert done is not None, "no terminal done event"
    return events, done


def test_stream_tokens_and_done(sse_post, user_headers):
    events, done = _stream_one(sse_post, user_headers, "Reply with exactly one word: ping", temperature=0.9)

    tokens = [e["content"] for e in events if e.get("type") == "token"]
    assert tokens, "no token events streamed"
    assert "".join(tokens).strip(), "streamed reply was empty"

    # status (activity) events precede the answer
    assert any(e.get("type") == "status" for e in events)


def test_done_event_contract(sse_post, user_headers):
    _, done = _stream_one(sse_post, user_headers, "What is 2 plus 2? One number only.", temperature=0.9)

    missing = _DONE_KEYS - set(done)
    assert not missing, f"done event missing keys: {missing}"

    assert isinstance(done["model"], str) and done["model"]
    assert done["query_type"] in _QUERY_TYPES
    assert done["intent"] in _INTENTS
    assert isinstance(done["cost_usd"], (int, float)) and done["cost_usd"] >= 0
    assert done["total_tokens"] >= done["completion_tokens"] >= 0
    assert isinstance(done["cache_hit"], bool)

    grounding = done["grounding"]
    assert set(grounding) >= {"level", "score", "sources"}
    assert grounding["level"] in {"high", "medium", "low", "none"}
    assert isinstance(done["activity"], list) and done["activity"]


def test_assistant_message_persists_with_grounding(sse_post, client, user_headers):
    _, done = _stream_one(sse_post, user_headers, "Name one primary color. One word.", temperature=0.9)
    conv_id = done["conversation_id"]
    assert conv_id

    msgs = client.get(f"/conversations/{conv_id}/messages", headers=user_headers).json()
    assert len(msgs) >= 2
    assistant = [m for m in msgs if m["role"] == "assistant"]
    assert assistant, "assistant message not persisted"
    last = assistant[-1]
    # render_meta-derived fields survive the refetch
    for k in ("grounding", "query_type", "src_count"):
        assert k in last


def test_conversation_continuity(sse_post, user_headers):
    """Second turn reuses the same conversation_id when passed back."""
    _, first = _stream_one(sse_post, user_headers, "Remember the number 7. Acknowledge briefly.", temperature=0.9)
    conv_id = first["conversation_id"]
    _, second = _stream_one(
        sse_post, user_headers, "What number did I ask you to remember?",
        conversation_id=conv_id, temperature=0.9,
    )
    assert second["conversation_id"] == conv_id
