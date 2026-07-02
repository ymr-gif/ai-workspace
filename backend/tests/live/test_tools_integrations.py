"""Live: every agent tool + set-up integrations driven through real NIM.

The companion to ``test_files_rag.py``. Where that file proves the RAG loop, this
suite proves the **tool surface itself**: each tool family is steered to fire by a
real model, then asserted three ways —

  1. the ``tool_call`` SSE event names the tool,
  2. ``GET /tool-calls?conversation_id=`` shows the ``ToolCallLog`` row persisted,
  3. flag-bearing tools set their ``done`` flag (``web_searched`` / ``url_fetched``).

Confirm-gated tools (``write_memory``, calendar writes) are asserted at their **safe
boundary** — the confirm sentinel SSE event — and never executed against the real
backend, so the suite never mutates user memory or a live Google Calendar.

Markers:
  * core tool tests → ``live_nim`` (need only the stack + a model)
  * integration tests → ``optional`` (additionally need an active OAuth connector;
    self-skip when the connector is absent — e.g. Gmail is not connected here)

Gating reference (backend/CLAUDE.md "AI Agent Tool Loop") — capability-only now;
the model decides when to call via native function calling (no keyword pre-filter):
  * ``web_search``  → WEB_SEARCH_ENABLED=true
  * ``fetch_url``   → message contains an http(s):// URL
  * file tools      → offered once ``file_ids`` is non-empty
  * drive/calendar/gmail → an active connector
"""
import time
import uuid

import pytest

pytestmark = pytest.mark.live_nim


# ── SSE helpers ─────────────────────────────────────────────────────────────────
def _fire(sse_post, headers, message, *, timeout=150, **payload):
    payload["message"] = message
    payload.setdefault("stream", True)
    return sse_post("/chat/stream", headers, payload, timeout=timeout)


def _tool_calls(events):
    """List of (name, args) from ``tool_call`` SSE events."""
    return [(e.get("name"), e.get("args") or {}) for e in events if e.get("type") == "tool_call"]


def _tool_names(events):
    return [n for n, _ in _tool_calls(events)]


def _done(events):
    return next((e for e in events if e.get("type") == "done"), None)


def _event_types(events):
    return {e.get("type") for e in events}


def _tool_result_for(events, *names):
    """The first ``tool_result`` content for any of ``names`` (or None)."""
    return next(
        (e.get("content", "") for e in events
         if e.get("type") == "tool_result" and e.get("name") in names),
        None,
    )


def _persisted_tools(client, headers, conv_id):
    """Tool names recorded as ToolCallLog rows for a conversation."""
    r = client.get(f"/tool-calls?conversation_id={conv_id}", headers=headers)
    assert r.status_code == 200, r.text
    return [row.get("tool_name") for row in r.json()]


def _skip_if_connector_error(events, *names):
    """A live connector returning an API error (e.g. Calendar 403) is an
    environment/cloud-console issue, not an app bug — surface it as a skip with
    the real reason rather than a red failure. Gating + dispatch already proven
    by the ``tool_call`` event before this is reached."""
    res = _tool_result_for(events, *names) or ""
    if res.startswith("Error:") or "403" in res or "Forbidden" in res or "needs_reauth" in res:
        pytest.skip(f"{names[0]} fired but the live API errored: {res[:160]}")


def _assert_fired(events, *names):
    """At least one of ``names`` was invoked in the stream. Returns the one seen.

    Proves gating + the model dispatching the tool. Does NOT require a ``done``
    event — the loop can legitimately end in an ``error`` (loop-guard abort,
    upstream tool error) after the tool has already fired."""
    fired = _tool_names(events)
    hit = next((n for n in names if n in fired), None)
    assert hit is not None, f"none of {names} fired; saw {fired}; types={_event_types(events)}"
    return hit


def _assert_completed(events, client, headers, *names):
    """Tool fired, the loop reached ``done``, and the row persisted to ToolCallLog.

    For tools whose result feeds a clean final answer (search/read/web/drive)."""
    hit = _assert_fired(events, *names)
    done = _done(events)
    assert done is not None, f"no done event; types={_event_types(events)}"
    conv_id = done.get("conversation_id")
    assert conv_id, "done event missing conversation_id"
    persisted = _persisted_tools(client, headers, conv_id)
    assert hit in persisted, f"{hit} not persisted; saw {persisted}"
    return done


# ── fixtures ────────────────────────────────────────────────────────────────────
@pytest.fixture
def kb_file(client, user_headers):
    """A small knowledge file so file tools (and query_graph) are offered."""
    token = uuid.uuid4().hex[:8].upper()
    content = (
        f"PROJECT LEDGER {token}\n"
        f"Project Apollo uses Postgres and Redis.\n"
        f"The owner of Project Apollo is Alice.\n"
        f"The deadline marker is {token}.\n"
    ).encode()
    up = client.post(
        "/files/upload",
        headers=user_headers,
        files={"file": (f"ledger_{token}.txt", content, "text/plain")},
    )
    assert up.status_code in (200, 201), up.text
    fid = up.json().get("id") or up.json().get("file_id")
    assert fid, up.text

    # wait until ready so retrieval has chunks
    deadline = time.time() + 60
    while time.time() < deadline:
        row = next((f for f in client.get("/files", headers=user_headers).json()
                    if str(f.get("id")) == str(fid)), None)
        if (row or {}).get("status") in ("ready", "partial"):
            break
        if (row or {}).get("status") in ("error", "failed"):
            pytest.fail(f"file processing failed: {row}")
        time.sleep(1.0)

    yield str(fid), token
    client.delete(f"/files/{fid}", headers=user_headers)


def _connector_active(client, headers, connector_type):
    r = client.get("/integrations", headers=headers)
    if r.status_code != 200:
        return False
    return any(
        c.get("connector_type") == connector_type and c.get("status") == "active"
        for c in r.json()
    )


# ══════════════════════════════════════════════════════════════════════════════
# Web search — the headline path (offered whenever WEB_SEARCH_ENABLED)
# ══════════════════════════════════════════════════════════════════════════════
def test_web_search_fires_and_flags(sse_post, client, user_headers):
    # Strong steer: under capability-gated function calling the full tool menu is
    # always offered, so the weak user-account model mis-selects on unsteered
    # prompts (e.g. grabs write_memory). The test proves web_search *dispatches*,
    # not the model's unsteered judgment — so name the tool explicitly with neutral
    # wording (no file-op verbs, which would pull in file context via the fallback).
    events = _fire(sse_post, user_headers,
                   "What is today's top news headline? Use the web_search tool to look it up.")
    done = _assert_completed(events, client, user_headers, "web_search")
    assert done.get("web_searched") is True, done
    # the search query arg is populated
    args = dict(_tool_calls(events))["web_search"]
    assert args.get("query"), args


def test_web_search_not_used_for_trivial_chat(sse_post, user_headers):
    """Model-restraint proof: web_search is now always *offered* when enabled,
    but the model must not actually search for a trivial greeting."""
    events = _fire(sse_post, user_headers, "Say hello and nothing else.")
    done = _done(events)
    assert done is not None
    assert done.get("web_searched") is not True, done
    assert "web_search" not in _tool_names(events)


def test_fetch_url_fires_and_flags(sse_post, client, user_headers):
    events = _fire(sse_post, user_headers,
                   "Fetch and summarize https://example.com for me.")
    done = _assert_completed(events, client, user_headers, "fetch_url")
    assert done.get("url_fetched") is True, done


# ══════════════════════════════════════════════════════════════════════════════
# File tools (offered whenever file_ids is non-empty)
# ══════════════════════════════════════════════════════════════════════════════
def test_list_files_tool(sse_post, client, user_headers, kb_file):
    fid, _ = kb_file
    # Strong steer with neutral verbs: for a single attached file the model can
    # answer from the injected file name without a tool, so demand the call by name
    # using verbs the attached-file rule doesn't route to chat text.
    events = _fire(sse_post, user_headers,
                   "Use the list_files tool to count my attached files and report the total.",
                   file_ids=[fid])
    _assert_completed(events, client, user_headers, "list_files")


def test_file_search_tool(sse_post, client, user_headers, kb_file):
    """File search family — with a single file the model may legitimately reach
    for ``search_in_file`` (often followed by ``read_file``) instead of
    ``search_across_files``; any of them proves the search surface."""
    fid, _ = kb_file
    events = _fire(sse_post, user_headers,
                   "Search across my files for the word Apollo and name the file.",
                   file_ids=[fid])
    _assert_completed(events, client, user_headers,
                      "search_across_files", "search_in_file", "read_file")


def test_query_graph_tool(sse_post, client, user_headers, kb_file):
    fid, _ = kb_file
    events = _fire(sse_post, user_headers,
                   "Use your query_graph tool to report what entities you have stored about me.",
                   file_ids=[fid])
    _assert_completed(events, client, user_headers, "query_graph")


def test_create_file_tool(sse_post, client, user_headers, kb_file):
    fid, _ = kb_file
    marker = uuid.uuid4().hex[:6]
    events = _fire(sse_post, user_headers,
                   f"Use the create_file tool to make a new note named verify_{marker}.txt "
                   f"containing the text {marker}.",
                   file_ids=[fid])
    # write tools can end the loop without a clean `done`; assert the call fired
    _assert_fired(events, "create_file")
    # best-effort cleanup of whatever file the tool created
    for f in client.get("/files", headers=user_headers).json():
        if marker in (f.get("filename") or ""):
            client.delete(f"/files/{f['id']}", headers=user_headers)


# ══════════════════════════════════════════════════════════════════════════════
# Pause/confirm tools — asserted at the safe boundary, never executed
# ══════════════════════════════════════════════════════════════════════════════
def test_ask_user_pauses_loop(sse_post, client, user_headers, kb_file):
    fid, _ = kb_file
    events = _fire(sse_post, user_headers,
                   "I want to rename one of my files but I won't say which yet. "
                   "Use the ask_user tool to ask me which file.",
                   file_ids=[fid])
    assert "ask_user" in _tool_names(events), _tool_names(events)
    assert "ask_user" in _event_types(events), _event_types(events)


def test_write_memory_confirm_sentinel(sse_post, client, user_headers):
    events = _fire(sse_post, user_headers,
                   "Please remember that I prefer responses in metric units.")
    assert "write_memory" in _tool_names(events), _tool_names(events)
    # confirm card sentinel — loop pauses, nothing written until POST /api/memory/write
    assert "confirm_write_memory" in _event_types(events), _event_types(events)


# ══════════════════════════════════════════════════════════════════════════════
# Google Drive (read-only connector) — optional, skip if not active
# ══════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def drive_admin(client, admin_headers):
    if not _connector_active(client, admin_headers, "google_drive"):
        pytest.skip("google_drive connector not active for admin")
    return admin_headers


@pytest.mark.optional
def test_drive_list_files(sse_post, client, drive_admin):
    events = _fire(sse_post, drive_admin, "List the files in my Google Drive please.")
    _assert_fired(events, "drive_list_files")
    _skip_if_connector_error(events, "drive_list_files")
    _assert_completed(events, client, drive_admin, "drive_list_files")


@pytest.mark.optional
def test_drive_search(sse_post, client, drive_admin):
    events = _fire(sse_post, drive_admin,
                   "Search my Google Drive for files containing the word report.")
    _assert_fired(events, "drive_search")
    _skip_if_connector_error(events, "drive_search")
    _assert_completed(events, client, drive_admin, "drive_search")


# ══════════════════════════════════════════════════════════════════════════════
# Google Calendar (read-write connector) — optional; writes stop at the sentinel
# ══════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def calendar_admin(client, admin_headers):
    if not _connector_active(client, admin_headers, "google_calendar"):
        pytest.skip("google_calendar connector not active for admin")
    return admin_headers


@pytest.mark.optional
def test_calendar_list_events(sse_post, client, calendar_admin):
    events = _fire(sse_post, calendar_admin,
                   "Show me my calendar events for this week.")
    # gating + dispatch must work; a live Google 403 (Calendar API/scope not
    # enabled in the cloud console) is reported as a skip, not a false failure.
    _assert_fired(events, "calendar_list_events")
    # Regression guard for the empty-reply fix: even when the tool errors, the
    # loop must NOT abort to an empty message — it forces a final tool-free turn
    # that relays the error to the user (a `done` event, not a bare `error`).
    if _tool_result_for(events, "calendar_list_events") and \
            "403" in (_tool_result_for(events, "calendar_list_events") or ""):
        assert _done(events) is not None, \
            f"connector 403 must still yield a graceful reply, not empty; types={_event_types(events)}"
    _skip_if_connector_error(events, "calendar_list_events")
    _assert_completed(events, client, calendar_admin, "calendar_list_events")


@pytest.mark.optional
def test_calendar_create_confirm_sentinel(sse_post, client, calendar_admin):
    """Write tools must pause for confirmation — never hit Google from the loop.

    Latch-first (Q3 Task B): calendar schemas are withheld until embedding-cosine intent
    latches the session — a lone cold create-turn scores below the 0.70 floor (measured
    0.531 on 2026-07-03) so the tool is structurally absent. Lead with a strong read to
    latch, then create on the SAME conversation (the shipped UX; mirrors rich_exercise)."""
    warm = _fire(sse_post, calendar_admin,
                 "Use the calendar tool to show what's on my calendar this week.")
    conv = next((e.get("conversation_id") for e in warm if e.get("type") == "done"), None)
    assert conv, "no conversation_id from the latch turn"
    _skip_if_connector_error(warm, "calendar_list_events")
    events = _fire(sse_post, calendar_admin,
                   "Now use the calendar tool to create an event titled VerifyProbe "
                   "tomorrow at 3pm for 30 minutes.",
                   conversation_id=conv)
    assert "calendar_create_event" in _tool_names(events), _tool_names(events)
    assert "confirm_calendar_write" in _event_types(events), _event_types(events)


# ══════════════════════════════════════════════════════════════════════════════
# Gmail — not connected in this environment; prove the suite self-skips cleanly
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.optional
def test_gmail_when_connected(sse_post, client, admin_headers):
    if not _connector_active(client, admin_headers, "gmail"):
        pytest.skip("gmail connector not active (expected here — Gmail not set up)")
    events = _fire(sse_post, admin_headers, "Show me my latest emails in my inbox.")
    _assert_fired(events, "gmail_list_messages")
    _skip_if_connector_error(events, "gmail_list_messages")
    _assert_completed(events, client, admin_headers, "gmail_list_messages")
