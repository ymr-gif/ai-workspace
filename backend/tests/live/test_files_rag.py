"""Live: file upload → dedup → embed → RAG tool loop → delete.

Exercises the real extract/chunk/embed pipeline and grounded retrieval. Marker: live_nim.
"""
import time
import uuid

import pytest

pytestmark = pytest.mark.live_nim


def _file_id(resp_json):
    return resp_json.get("id") or resp_json.get("file_id") or (resp_json.get("file") or {}).get("id")


def _upload(client, headers, name, content: bytes):
    r = client.post(
        "/files/upload",
        headers=headers,
        files={"file": (name, content, "text/plain")},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def _wait_ready(client, headers, fid, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        files = client.get("/files", headers=headers).json()
        row = next((f for f in files if str(f.get("id")) == str(fid)), None)
        status = (row or {}).get("status")
        if status in ("ready", "partial"):
            return row
        if status in ("error", "failed"):
            pytest.fail(f"file processing failed: {row}")
        time.sleep(1.0)
    pytest.fail(f"file {fid} not ready within {timeout}s")


@pytest.fixture
def secret_file(client, user_headers):
    token = uuid.uuid4().hex[:8].upper()
    content = (
        f"INTERNAL VERIFICATION NOTE\n"
        f"The project codeword for this run is {token}.\n"
        f"Remember: the codeword is {token}.\n"
    ).encode()
    up = _upload(client, user_headers, f"verify_{token}.txt", content)
    fid = _file_id(up)
    assert fid, up
    yield fid, token
    client.delete(f"/files/{fid}", headers=user_headers)


def test_upload_dedup(client, user_headers):
    content = f"dedup check {uuid.uuid4().hex}".encode()
    a = _upload(client, user_headers, "dedup.txt", content)
    b = _upload(client, user_headers, "dedup.txt", content)
    # same (user, sha256) → server returns the existing file, flagged duplicate
    assert _file_id(a) == _file_id(b) or b.get("duplicate") is True
    client.delete(f"/files/{_file_id(a)}", headers=user_headers)


def test_upload_lists_and_deletes(client, user_headers):
    up = _upload(client, user_headers, f"tmp_{uuid.uuid4().hex[:6]}.txt", b"hello world")
    fid = _file_id(up)
    listing = client.get("/files", headers=user_headers).json()
    assert any(str(f.get("id")) == str(fid) for f in listing)
    assert client.delete(f"/files/{fid}", headers=user_headers).status_code in (200, 204)
    after = client.get("/files", headers=user_headers).json()
    assert not any(str(f.get("id")) == str(fid) for f in after)


def test_rag_tool_loop_grounds_on_file(sse_post, client, user_headers, secret_file):
    fid, token = secret_file
    _wait_ready(client, user_headers, fid)

    events = sse_post(
        "/chat/stream",
        user_headers,
        {"message": "What is the project codeword in the attached note?", "file_ids": [str(fid)]},
        timeout=120,
    )
    done = next((e for e in events if e.get("type") == "done"), None)
    assert done is not None
    tokens = "".join(e.get("content", "") for e in events if e.get("type") == "token")

    # file_ids forces the 70B reasoning model
    assert "70b" in done["model"].lower() or "reasoning" in done["model"].lower()
    # retrieval actually happened against the file
    assert done["src_count"] >= 1 or done["grounding"]["level"] != "none", done
    # and the model surfaced the grounded fact
    assert token in tokens, f"codeword {token} not in answer: {tokens[:200]}"
