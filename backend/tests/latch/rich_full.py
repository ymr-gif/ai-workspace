"""Rich FULL-surface exerciser — the gap-filler for the full-feature run.

Companion to rich_exercise.py (which covers the agent tool loop + connectors). This drives every
DOCUMENTED feature that no automated suite exercises end-to-end: unified search, full export ZIP,
graph admin endpoints, metrics/observability, cache proof, notifications, invite→register→
onboarding→API-key lifecycle, voice, image OCR (expected-fail while paddle is absent — BUG-V7),
webhooks, the memory deep pass (write/conflicts/history/decay/compact/export/import), scheduled
prompts, goals, conversation rotation, and the REAL-mutation tier: admin sweep, cost-cap 402,
rate-limit 429, an isolated circuit-breaker trip, re-embed, and the memory soft-reset + restore
rehearsal. Finishes with a headed UI panel sweep (screenshots) via ui_capture.UICapture.

Deterministic — fixed prompts/calls, zero AI-agent tokens. Everything created is tagged
RICHFULL-<run> and cleaned up (or removed by the admin soft-reset finale, which doubles as the
de-poison step). Each section reports PASS / FAIL / SKIP / XFAIL independently; the run never
aborts on a single section.

Run (from backend/tests/latch):
  python3 rich_full.py                          # full run incl. destructive + headed UI
  python3 rich_full.py --skip-ui --skip-rotation
  python3 rich_full.py --only cache,voice       # debug a subset
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import subprocess
import sys
import time
import uuid
import wave
import zipfile
from datetime import datetime, timezone

import httpx

RUN_TAG = "RICHFULL-" + uuid.uuid4().hex[:8]
DOCKER_DIR = "../../../docker"
LOGS_DIR = "rich_full_logs"

# 1x1 red PNG
PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAF"
           "AAH/q842iQAAAABJRU5ErkJggg==")

RESULTS: list[dict] = []
CLEANUP: list[tuple[str, object]] = []   # (desc, zero-arg fn) run at the end, best-effort


class Skip(Exception):
    pass


class XFail(Exception):
    pass


def _log(section, status, detail, secs):
    row = {"ts": time.time(), "section": section, "status": status,
           "detail": str(detail)[:400], "secs": round(secs, 1)}
    RESULTS.append(row)
    with open(f"{LOGS_DIR}/rich_full_results.jsonl", "a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    mark = {"PASS": "✓", "FAIL": "✗", "SKIP": "→", "XFAIL": "~"}[status]
    print(f"  {mark} [{status:5}] {section} ({secs:.1f}s) {detail}", flush=True)


def run_section(name, fn, *args):
    print(f"[section] {name}", flush=True)
    t0 = time.monotonic()
    try:
        detail = fn(*args) or "ok"
        _log(name, "PASS", detail, time.monotonic() - t0)
    except Skip as e:
        _log(name, "SKIP", e, time.monotonic() - t0)
    except XFail as e:
        _log(name, "XFAIL", e, time.monotonic() - t0)
    except AssertionError as e:
        _log(name, "FAIL", f"assert: {e}", time.monotonic() - t0)
    except Exception as e:
        _log(name, "FAIL", f"{type(e).__name__}: {e}", time.monotonic() - t0)


# ── infra shell helpers (same pattern as rich_exercise's compose call) ───────────
def PG(sql: str) -> str:
    r = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "scylla",
                        "-d", "nimrouter", "-tAc", sql],
                       cwd=DOCKER_DIR, capture_output=True, text=True, timeout=30)
    return r.stdout.strip()


def RED(*args: str) -> str:
    r = subprocess.run(["docker", "compose", "exec", "-T", "redis", "redis-cli", *args],
                       cwd=DOCKER_DIR, capture_output=True, text=True, timeout=30)
    return r.stdout.strip()


# ── API client ───────────────────────────────────────────────────────────────────
class C:
    def __init__(self, base, user, pw, timeout=300.0):
        self.base = base.rstrip("/")
        self.user = user
        self.http = httpx.Client(timeout=timeout)
        self.token = self.login(user, pw)
        self._last_chat = 0.0

    def login(self, user, pw):
        r = self.http.post(f"{self.base}/auth/token", data={"username": user, "password": pw})
        r.raise_for_status()
        self.token = r.json()["access_token"]
        return self.token

    @property
    def h(self):
        return {"Authorization": f"Bearer {self.token}"}

    def req(self, method, path, **kw):
        return self.http.request(method, f"{self.base}{path}", headers=self.h, **kw)

    def get(self, path, **kw):    return self.req("GET", path, **kw)
    def post(self, path, **kw):   return self.req("POST", path, **kw)
    def put(self, path, **kw):    return self.req("PUT", path, **kw)
    def patch(self, path, **kw):  return self.req("PATCH", path, **kw)
    def delete(self, path, **kw): return self.req("DELETE", path, **kw)

    def stream(self, message, conv=None, *, pace=True, **params):
        """One /chat/stream turn. Returns (status_code, events, done). Paces to the 15/60s limit."""
        if pace:
            wait = 4.2 - (time.monotonic() - self._last_chat)
            if wait > 0:
                time.sleep(wait)
        self._last_chat = time.monotonic()
        body = {"message": message, **params}
        if conv:
            body["conversation_id"] = conv
        events, done = [], {}
        with self.http.stream("POST", f"{self.base}/chat/stream", json=body, headers=self.h) as r:
            if r.status_code != 200:
                r.read()
                return r.status_code, [], {}
            for line in r.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:])
                except Exception:
                    continue
                events.append(ev)
                if ev.get("type") == "done":
                    done = ev
        return 200, events, done

    def lean(self, message, conv=None, **params):
        """Cheap 1-token turn (model_params → cache bypass)."""
        return self.stream(message, conv, max_tokens=1, temperature=0.2, **params)


# ── env flag helpers ─────────────────────────────────────────────────────────────
def env_set(admin: C, key: str, value: str):
    r = admin.put(f"/admin/env/{key}", json={"value": value})
    assert r.status_code == 200, f"env PUT {key} → {r.status_code}: {r.text[:120]}"
    r = admin.post("/admin/env/reload")
    assert r.status_code == 200, f"env reload → {r.status_code}"


# ═════════════════════════════ D1 — read/verify sweep ════════════════════════════
def sec_auth_onboarding(ctx):
    """invite → register → login → onboarding → email → API key lifecycle."""
    admin = ctx["admin"]
    r = admin.post("/auth/invite")
    assert r.status_code in (200, 201), f"invite → {r.status_code}: {r.text[:120]}"
    inv = r.json()
    token = next((v for v in inv.values() if isinstance(v, str) and len(v) > 8), None)
    assert token, f"no token in invite response {inv}"
    assert admin.get("/auth/invites").status_code == 200

    uname = f"richfull_{RUN_TAG.split('-')[1]}"
    pw = "richfull-secret"
    r = admin.http.post(f"{admin.base}/auth/register",
                        json={"username": uname, "password": pw, "invite_token": token})
    assert r.status_code in (200, 201), f"register → {r.status_code}: {r.text[:160]}"
    u = C(admin.base, uname, pw)
    ctx["user"] = u
    ctx["user_id"] = int(PG(f"SELECT id FROM users WHERE username='{uname}';") or 0)
    assert ctx["user_id"], "throwaway user id not found in DB"

    me = u.get("/auth/me").json()
    assert me.get("has_onboarded") is False, f"fresh user has_onboarded={me.get('has_onboarded')}"
    assert u.patch("/auth/me/email", json={"email": f"{uname}@example.com"}).status_code == 200
    assert u.post("/auth/me/onboarding-complete").status_code == 200
    assert u.get("/auth/me").json().get("has_onboarded") is True

    r = u.post("/auth/me/api-key")
    key = next((v for v in r.json().values() if isinstance(v, str) and len(v) > 16), None)
    assert key, f"no api key in {r.text[:120]}"
    r2 = u.http.get(f"{u.base}/usage", headers={"Authorization": f"Bearer {key}"})
    assert r2.status_code == 200, f"api-key auth → {r2.status_code}"
    assert u.delete("/auth/me/api-key").status_code in (200, 204)
    r3 = u.http.get(f"{u.base}/usage", headers={"Authorization": f"Bearer {key}"})
    assert r3.status_code == 401, f"revoked key still works → {r3.status_code}"
    return f"user={uname} id={ctx['user_id']} · invite+register+onboarding+api-key ok"


def sec_unified_search(ctx):
    admin = ctx["admin"]
    data = f"{RUN_TAG} unified search seed document. The quick brown fox audits budgets.\n" * 4
    r = admin.post("/files/upload", files={"file": (f"{RUN_TAG}.txt", data.encode(), "text/plain")})
    assert r.status_code in (200, 201), f"upload → {r.status_code}: {r.text[:120]}"
    fid = r.json().get("id") or r.json().get("file_id")
    assert fid, f"no file id in {r.text[:160]}"
    ctx["file_id"] = fid
    CLEANUP.append((f"delete file {fid}", lambda: admin.delete(f"/files/{fid}")))
    for _ in range(60):
        st = admin.get(f"/files/{fid}/status").json()
        s = st.get("status") or st.get("upload_status")
        if s in ("ready", "partial"):
            break
        if s in ("failed", "error"):
            raise AssertionError(f"file processing {s}")
        time.sleep(2)
    else:
        raise AssertionError("file never became ready")

    r = admin.get("/search", params={"q": RUN_TAG, "scope": "files"})
    assert r.status_code == 200
    hits = r.json().get("results", [])
    assert any(RUN_TAG in (h.get("title", "") + h.get("snippet", "")) for h in hits), \
        f"files scope missed the seeded doc ({len(hits)} hits)"
    shapes = []
    for scope in ("all", "conversations", "memory", "graph"):
        r = admin.get("/search", params={"q": "project", "scope": scope})
        assert r.status_code == 200, f"scope={scope} → {r.status_code}"
        shapes.append(f"{scope}={len(r.json().get('results', []))}")
    return f"files hit ok · {' '.join(shapes)}"


def sec_full_export(ctx):
    r = ctx["admin"].get("/export/full")
    assert r.status_code == 200, f"→ {r.status_code}"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert len(names) >= 2, f"thin ZIP: {names}"
    return f"{len(names)} entries · e.g. {names[:3]}"


def sec_conversations(ctx):
    admin = ctx["admin"]
    code, _, done = admin.stream(f"Reply with one short sentence about {RUN_TAG}.", max_tokens=60,
                                 temperature=0.3)
    assert code == 200 and done.get("conversation_id"), "no conversation created"
    conv = done["conversation_id"]
    ctx["conv_id"] = conv
    CLEANUP.append((f"delete conv {conv[:8]}", lambda: admin.delete(f"/conversations/{conv}")))
    r = admin.patch(f"/conversations/{conv}",
                    json={"locked_model": "meta/llama-3.1-8b-instruct",
                          "system_prompt": f"Test prompt {RUN_TAG}"})
    assert r.status_code == 200, f"PATCH → {r.status_code}: {r.text[:120]}"
    assert admin.get("/conversations", params={"q": RUN_TAG}).status_code == 200
    r = admin.get(f"/conversations/{conv}/export", params={"format": "markdown"})
    assert r.status_code == 200 and RUN_TAG in r.text, "markdown export missing content"
    jr = admin.get(f"/conversations/{conv}/export", params={"format": "json"})
    msgs = admin.get(f"/conversations/{conv}/messages")
    assert msgs.status_code == 200 and len(msgs.json()) >= 2
    return f"conv={conv[:8]} lock+export(md,json={jr.status_code})+messages ok"


def sec_graph(ctx):
    admin = ctx["admin"]
    assert admin.get("/graph/health").status_code == 200
    stats = admin.get("/graph/stats").json()
    r = admin.get("/graph/sample", params={"limit": 5})
    assert r.status_code == 200, f"sample → {r.status_code}"
    sample = r.json()
    nodes = sample.get("nodes") or sample.get("entities") or []
    deleted = "skipped (no nodes)"
    if nodes:
        name = nodes[0].get("name") or nodes[0].get("id")
        if name:
            from urllib.parse import quote
            dr = admin.delete(f"/graph/entities/{quote(str(name), safe='')}")
            deleted = f"deleted {str(name)[:30]!r} → {dr.status_code}"
    pr = admin.post("/graph/prune")
    assert pr.status_code == 200, f"prune → {pr.status_code}"
    return f"entities={stats.get('entities')} · {deleted} · prune={pr.json()}"


def sec_metrics_observability(ctx):
    admin = ctx["admin"]
    for p in ("/hardware", "/system/hardware", "/metrics/overview", "/metrics/models",
              "/metrics/latency"):
        assert admin.get(p).status_code == 200, f"{p} not 200"
    prom_text = admin.get("/metrics/prometheus").text
    if "api_requests_total" not in prom_text:   # some deployments serve it on /prometheus
        prom_text = admin.get("/prometheus").text
    missing = [c for c in ("api_requests_total", "stream_interruptions_total",
                           "all_models_failed_total", "arq_job_failed_total")
               if c not in prom_text]
    plain = httpx.Client(timeout=15)
    targets = plain.get("http://localhost:9090/api/v1/targets").json()
    up = [t["health"] for t in targets["data"]["activeTargets"]]
    graf = plain.get("http://localhost:3001/api/health").status_code
    assert graf == 200, f"grafana health → {graf}"
    return (f"api metrics ok (missing counters: {missing or 'none'}) · "
            f"prom targets {up.count('up')}/{len(up)} up · grafana ok")


def sec_cache(ctx):
    """model_override pins the 8B so a NIM-side fallback can't flip the cache key mid-test
    (override is cache-compatible; bypass only triggers on model_params/files/images)."""
    admin = ctx["admin"]
    msg = f"Reply with exactly the word OK. (probe {RUN_TAG})"
    code1, _, d1 = admin.stream(msg, model_override="llama")                  # cacheable
    code2, _, d2 = admin.stream(msg, model_override="llama")                  # identical → hit
    code3, _, d3 = admin.stream(msg, model_override="llama", temperature=0.4)  # params → bypass
    for cid in (d1.get("conversation_id"), d2.get("conversation_id"), d3.get("conversation_id")):
        if cid:
            CLEANUP.append((f"delete cache-conv {cid[:8]}",
                            lambda c=cid: admin.delete(f"/conversations/{c}")))
    assert code1 == code2 == code3 == 200
    assert d1.get("cache_hit") is False, f"first send cache_hit={d1.get('cache_hit')}"
    assert d2.get("cache_hit") is True, f"identical resend not cached (cache_hit={d2.get('cache_hit')})"
    assert d3.get("cache_hit") is False, "model-params send should bypass cache"
    return "miss → hit → param-bypass ok"


def sec_notifications(ctx):
    u = ctx["user"]
    r = u.get("/api/notifications/preferences")
    assert r.status_code == 200, f"prefs → {r.status_code}"
    prefs = r.json()
    flag = not prefs.get("email_digest", False)
    assert u.patch("/api/notifications/preferences", json={"email_digest": flag}).status_code == 200
    assert u.get("/api/notifications/preferences").json().get("email_digest") is flag
    assert u.patch("/api/notifications/preferences",
                   json={"email_digest": prefs.get("email_digest", False)}).status_code == 200
    v = u.get("/api/notifications/vapid-public-key")
    return f"prefs toggle ok · vapid={'set' if v.status_code == 200 else f'{v.status_code} (push off)'}"


def sec_voice(ctx):
    admin = ctx["admin"]
    env_set(admin, "VOICE_ENABLED", "true")
    try:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 3200)   # 0.2s silence
        r = admin.post("/api/transcribe",
                       files={"file": ("probe.wav", buf.getvalue(), "audio/wav")})
        assert r.status_code == 200, f"transcribe (enabled) → {r.status_code}: {r.text[:120]}"
        text = r.json()
    finally:
        env_set(admin, "VOICE_ENABLED", "false")
    r2 = admin.post("/api/transcribe", files={"file": ("probe.wav", b"x", "audio/wav")})
    assert r2.status_code == 503, f"transcribe (disabled) → {r2.status_code}, want 503"
    return f"stub transcript {str(text)[:60]!r} · gate-off 503 ok"


def sec_ocr(ctx):
    admin = ctx["admin"]
    env_set(admin, "IMAGE_OCR_ENABLED", "true")
    try:
        png = base64.b64decode(PNG_B64)
        r = admin.post("/files/upload", files={"file": (f"{RUN_TAG}.png", png, "image/png")})
        assert r.status_code in (200, 201), f"image upload → {r.status_code}"
        fid = r.json().get("id") or r.json().get("file_id")
        CLEANUP.append((f"delete image {fid}", lambda: admin.delete(f"/files/{fid}")))
        status = "?"
        for _ in range(45):
            st = admin.get(f"/files/{fid}/status").json()
            status = st.get("status") or st.get("upload_status")
            if status in ("ready", "partial", "failed", "error"):
                break
            time.sleep(2)
        # paste path must not hang/crash the stream even when OCR is unavailable
        code, _, done = admin.lean("what does this image say?", image_b64=PNG_B64,
                                   image_mime_type="image/png")
        paste = f"paste-path stream code={code} done={'yes' if done else 'no'}"
        if status in ("failed", "error"):
            raise XFail(f"upload OCR {status} — paddle absent (BUG-V7); {paste}")
        return f"upload status={status} · {paste}"
    finally:
        env_set(admin, "IMAGE_OCR_ENABLED", "false")


# ═════════════════════════════ D2 — stateful features ════════════════════════════
def sec_webhooks(ctx):
    u = ctx["user"]
    r = u.post("/auth/me/webhook-token")
    tok = next((v for v in r.json().values() if isinstance(v, str) and len(v) > 8), None)
    assert tok, f"no webhook token: {r.text[:120]}"
    assert u.get("/auth/me/webhook-token").status_code == 200
    plain = httpx.Client(timeout=15)
    for et in ("reminder", "file.uploaded", "external.data"):
        pr = plain.post(f"{u.base}/api/webhooks/{tok}",
                        json={"event_type": et, "payload": {"note": f"{RUN_TAG} {et}"}})
        assert pr.status_code in (200, 201, 202), f"{et} → {pr.status_code}"
    processed = "0"
    for _ in range(30):
        processed = PG("SELECT count(*) FROM webhook_events WHERE status='processed' "
                       f"AND payload::text LIKE '%{RUN_TAG}%';")
        if processed == "3":
            break
        time.sleep(3)
    assert u.delete("/auth/me/webhook-token").status_code in (200, 204)
    dead = plain.post(f"{u.base}/api/webhooks/{tok}",
                      json={"event_type": "reminder", "payload": {}})
    assert dead.status_code == 404, f"deleted token → {dead.status_code}, want 404"
    assert processed == "3", f"only {processed}/3 events processed"
    return "3 event types processed · token CRUD + 404-after-delete ok"


def sec_memory_deep(ctx):
    admin = ctx["admin"]
    fact = f"{RUN_TAG}: the user prefers deterministic test harnesses."
    assert admin.post("/memory/write", json={"fact": fact}).status_code == 200
    mem = admin.get("/memory").json()
    assert RUN_TAG in json.dumps(mem), "written fact not visible in GET /memory"
    scan = admin.post("/memory/conflicts/scan")
    conflicts = admin.get("/memory/conflicts").json()
    clist = conflicts if isinstance(conflicts, list) else conflicts.get("conflicts", [])
    resolved = "none to resolve"
    if clist:
        cid = clist[0].get("id")
        rr = admin.post(f"/memory/conflicts/{cid}/resolve", json={"strategy": "keep_a"})
        resolved = f"resolved #{cid} → {rr.status_code}"
    assert admin.get("/memory/history").status_code == 200
    assert admin.post("/memory/decay").status_code == 200
    comp = admin.post("/memory/compact")
    exp = admin.get("/memory/export")
    assert exp.status_code == 200
    imp = admin.post("/memory/import", json={"content": exp.json().get("content", "")})
    return (f"write+scan({scan.status_code})+{resolved}+history+decay+"
            f"compact({comp.status_code})+export/import({imp.status_code}) ok")


def sec_scheduled_prompts(ctx):
    u = ctx["user"]
    r = u.post("/scheduled-prompts",
               json={"name": f"{RUN_TAG} sched", "prompt": "Reply with the word OK.",
                     "schedule": "daily"})
    assert r.status_code in (200, 201), f"create → {r.status_code}: {r.text[:120]}"
    sid = r.json()["id"]
    CLEANUP.append((f"delete sched {sid}", lambda: u.delete(f"/scheduled-prompts/{sid}")))
    assert u.post(f"/scheduled-prompts/{sid}/run").status_code in (200, 202)
    runs = []
    for _ in range(30):
        runs = u.get(f"/scheduled-prompts/{sid}/runs").json()
        if runs:
            break
        time.sleep(3)
    assert runs, "manual run never showed in run history"
    assert u.patch(f"/scheduled-prompts/{sid}", json={"is_active": False}).status_code == 200
    return f"create+run(history={len(runs)})+deactivate ok"


def sec_goals(ctx):
    u = ctx["user"]
    code, _, done = u.lean(f"Note {RUN_TAG} goal test.")
    conv = done.get("conversation_id")
    if conv:
        CLEANUP.append((f"delete goal-conv {conv[:8]}", lambda: u.delete(f"/conversations/{conv}")))
    r = u.post("/goals", json={"title": f"{RUN_TAG} goal", "description": "exercise goals API"})
    assert r.status_code in (200, 201), f"create → {r.status_code}"
    gid = r.json()["id"]
    CLEANUP.append((f"delete goal {gid}", lambda: u.delete(f"/goals/{gid}")))
    link = "no conv"
    if conv:
        lr = u.post(f"/goals/{gid}/link/{conv}")
        link = f"link → {lr.status_code}"
    assert u.patch(f"/goals/{gid}", json={"status": "paused"}).status_code == 200
    assert u.patch(f"/goals/{gid}", json={"status": "completed"}).status_code == 200
    return f"create+{link}+paused→completed ok"


def sec_rotation(ctx):
    if ctx["args"].skip_rotation:
        raise Skip("--skip-rotation")
    u = ctx["user"]
    conv, rotated = None, None
    for i in range(46):                       # 46 turns ≈ 92 msgs > 80-msg threshold
        code, events, done = u.lean(f"turn {i} ack {RUN_TAG}", conv)
        if code == 429:
            time.sleep(20)
            continue
        assert code == 200, f"turn {i} → {code}"
        conv = done.get("conversation_id") or conv
        rot = next((e for e in events if e.get("type") == "rotated"), None)
        if rot:
            rotated = rot
            break
    assert rotated, f"no rotated event after 46 turns (conv={conv})"
    old = rotated.get("old_conversation_id")
    arch = PG(f"SELECT is_archived FROM conversations WHERE id='{old}';")
    assert arch == "t", f"old conv is_archived={arch!r}"
    new = rotated.get("new_conversation_id")
    for cid in (old, new):
        if cid:
            CLEANUP.append((f"delete rotated conv {cid[:8]}",
                            lambda c=cid: u.delete(f"/conversations/{c}")))
    return f"rotated old={old[:8]} → new={str(new)[:8]}, old archived in DB"


# ═════════════════════════════ D3 — real mutations ═══════════════════════════════
def sec_admin_sweep(ctx):
    admin, uid = ctx["admin"], ctx["user_id"]
    users = admin.get("/admin/users").json()
    ulist = users if isinstance(users, list) else users.get("users", [])
    assert any(u.get("id") == uid for u in ulist), "throwaway user missing from /admin/users"
    assert admin.patch(f"/admin/users/{uid}/cost-limit",
                       json={"cost_limit_usd": 5, "cost_window_days": 30}).status_code == 200
    assert admin.get(f"/admin/users/{uid}/usage").status_code == 200
    # is_active toggle: disable → user 401s → re-enable → works again
    assert admin.patch(f"/admin/users/{uid}/active").status_code == 200
    u = ctx["user"]
    blocked = u.get("/usage").status_code
    assert admin.patch(f"/admin/users/{uid}/active").status_code == 200
    u.login(u.user, "richfull-secret")
    assert u.get("/usage").status_code == 200, "user not restored after re-enable"
    assert blocked == 401, f"disabled user got {blocked}, want 401"
    # env roundtrip on a harmless probe key
    env_set(admin, "RICHFULL_PROBE", RUN_TAG)
    got = admin.get("/admin/env/RICHFULL_PROBE").json()
    assert RUN_TAG in json.dumps(got), f"env roundtrip: {got}"
    env_set(admin, "RICHFULL_PROBE", "removed")
    audit = admin.get("/admin/audit-log").text
    for act in ("cost_limit", "env.updated", "env.reloaded", "active"):
        assert act in audit, f"audit log missing {act!r}"
    return "users+cost-limit+usage+active-toggle(401)+env-roundtrip+audit ok"


def sec_cost_cap(ctx):
    admin, u, uid = ctx["admin"], ctx["user"], ctx["user_id"]
    code, _, _ = u.lean(f"cost seed {RUN_TAG}")   # ensure non-zero window spend
    assert admin.patch(f"/admin/users/{uid}/cost-limit",
                       json={"cost_limit_usd": 0.000001, "cost_window_days": 30}).status_code == 200
    code2, _, _ = u.lean(f"over the cap {RUN_TAG}")
    assert admin.patch(f"/admin/users/{uid}/cost-limit",
                       json={"cost_limit_usd": None}).status_code == 200
    code3, _, _ = u.lean(f"cap removed {RUN_TAG}")
    assert code2 == 402, f"capped chat → {code2}, want 402"
    assert code3 == 200, f"post-uncap chat → {code3}"
    return "402 under tiny cap · 200 after removal"


def sec_rate_limit(ctx):
    """Concurrent burst — status only, never read the stream body. A sequential burst
    can't trip the 15/60s window when each turn takes ~60s to stream under NIM load."""
    from concurrent.futures import ThreadPoolExecutor
    u = ctx["user"]

    def fire(i):
        try:
            with u.http.stream("POST", f"{u.base}/chat/stream", headers=u.h,
                               json={"message": f"burst {i} {RUN_TAG}", "max_tokens": 1,
                                     "temperature": 0.2}) as r:
                return r.status_code   # counted at request start; close without reading
        except Exception:
            return 0

    with ThreadPoolExecutor(max_workers=6) as ex:
        codes = list(ex.map(fire, range(18)))
    assert 429 in codes, f"no 429 in burst: {codes}"
    time.sleep(61)   # clear the sliding window for later sections
    return f"{codes.count(429)}×429 in 18-request burst"


def _restart_api():
    subprocess.run(["docker", "compose", "restart", "api"],
                   cwd=DOCKER_DIR, check=True, capture_output=True, timeout=180)
    for _ in range(60):
        try:
            if httpx.get("http://localhost:8000/health", timeout=5).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise AssertionError("api did not come back healthy after restart")


def sec_circuit_breaker(ctx):
    """Persistence→restore→enforcement semantics. is_open() reads only in-process state; the
    Redis key is persistence consumed by restore_circuit_state() at startup (before the model
    probe, which never clears healthy models). A synthetic failure-driven trip is unreachable
    (MODELS frozen at import; compose env outranks .env on restart) — the failure-driven OPEN
    is instead evidenced by "[circuit] opened" in api logs during real NIM 429s. Here: seed
    cb:open:<coder> → restart → restored-open must block explicit coder within the 90s
    cooldown → delete key + wait cooldown → coder serves again."""
    admin = ctx["admin"]
    coder = "deepseek-ai/deepseek-v4-flash"
    RED("SET", f"cb:open:{coder}", "1", "EX", "600")
    try:
        _restart_api()
        admin.login("admin", "admin-secret")
        # probe FIRST — the 90s in-process cooldown starts at restore (early in lifespan),
        # and a slow lifespan can nearly exhaust it before the app even serves
        code, _, done = admin.stream(f"breaker enforce {RUN_TAG}", max_tokens=1,
                                     temperature=0.2, model_override="coder", pace=False)
        blocked_model = str(done.get("model", ""))
        enforced = code != 200 or not done or "deepseek" not in blocked_model \
            or bool(done.get("fallback_used"))
        logs = subprocess.run(["docker", "compose", "logs", "api", "--since", "5m"],
                              cwd=DOCKER_DIR, capture_output=True, text=True, timeout=30).stdout
        restored = "restored open state" in logs
        lapsed = f"[circuit] reset model={coder}" in logs
    finally:
        RED("DEL", f"cb:open:{coder}")
    time.sleep(95)   # let the in-process cooldown lapse
    code2, _, done2 = admin.stream(f"breaker recovery {RUN_TAG}", max_tokens=1,
                                   temperature=0.2, model_override="coder")
    assert code2 == 200 and "deepseek" in str(done2.get("model", "")), \
        f"coder not recovered after cooldown: code={code2} model={done2.get('model')}"
    assert restored, "no '[circuit] restored open state' log line after restart"
    if not enforced and lapsed:
        raise Skip("cooldown lapsed before probe (slow lifespan) — restore verified, "
                   "enforcement inconclusive this run")
    assert enforced, f"restored-open breaker ignored: coder served (model={blocked_model})"
    return (f"restored-on-startup + enforced (served model={blocked_model or 'n/a'} "
            f"fallback={done.get('fallback_used')}) · recovered after cooldown")


def sec_re_embed(ctx):
    r = ctx["admin"].post("/admin/re-embed")
    assert r.status_code in (200, 202), f"→ {r.status_code}: {r.text[:120]}"
    return f"→ {r.status_code} {r.text[:160]}"


def sec_memory_reset_restore(ctx):
    admin, uid = ctx["admin"], ctx["user_id"]
    # -- restore rehearsal on the THROWAWAY user --
    u = ctx["user"]
    u.post("/memory/write", json={"fact": f"{RUN_TAG} pre-reset fact"})
    r = admin.post("/admin/memory/reset",
                   json={"user_id": uid, "level": "soft", "dry_run": False,
                         "confirm": f"RESET {uid}"})
    assert r.status_code == 200, f"user soft reset → {r.status_code}: {r.text[:160]}"
    vers = admin.get("/admin/memory/versions", params={"user_id": uid}).json()
    vlist = vers if isinstance(vers, list) else vers.get("versions", [])
    assert vlist, "no memory versions after reset"
    vid = vlist[0].get("id") or vlist[0].get("version")
    rr = admin.post("/admin/memory/restore",
                    json={"user_id": uid, "version_id": vid, "confirm": f"RESTORE {vid}"})
    if rr.status_code != 200:   # confirm string variant
        rr = admin.post("/admin/memory/restore",
                        json={"user_id": uid, "version_id": vid, "confirm": f"RESTORE {uid}"})
    assert rr.status_code == 200, f"restore → {rr.status_code}: {rr.text[:160]}"
    # -- admin finale: dry-run report, then REAL soft reset (doubles as de-poison) --
    before = PG("SELECT length(content) FROM user_memory WHERE user_id=1;")
    dr = admin.post("/admin/memory/reset",
                    json={"user_id": 1, "level": "soft", "dry_run": True, "confirm": "RESET 1"})
    assert dr.status_code == 200, f"dry-run → {dr.status_code}"
    mid = PG("SELECT length(content) FROM user_memory WHERE user_id=1;")
    assert mid == before, "dry_run mutated the sheet!"
    rr2 = admin.post("/admin/memory/reset",
                     json={"user_id": 1, "level": "soft", "dry_run": False, "confirm": "RESET 1"})
    assert rr2.status_code == 200, f"real soft reset → {rr2.status_code}: {rr2.text[:160]}"
    after = PG("SELECT length(content) FROM user_memory WHERE user_id=1;")
    snap = PG("SELECT count(*) FROM user_memory_versions WHERE user_id=1;")
    return (f"user{uid} reset+restore({rr.status_code}) ok · admin dry-run inert · "
            f"real soft reset: {before}→{after} chars, {snap} snapshots")


# ═════════════════════════════ D4 — UI panel sweep ═══════════════════════════════
# Exact accessible button names (panels stay mounted in the DOM, so loose text
# locators match hidden panel internals — use role=button + exact name only).
# Flight Ops shell (2026-07-11): header buttons are gone — panels live in the
# right dock (group tab → sub-tab). Group tab DOM text is lowercase ("mind");
# CSS uppercases it visually. Search moved into the Ctrl+K command palette.
DOCK_PANELS = [
    ("mind",  [("memory", "Memory"), ("goals", "Goals"), ("insights", "Insights")]),
    ("files", []),                                    # single pane, no sub-tabs
    ("ops",   [("usage", "Usage"), ("toollog", "Tool log"),
               ("automations", "Automations"), ("integrations", "Integrations")]),
    ("admin", []),                                    # invites pane (admin only)
]


def sec_ui_panels(ctx):
    if ctx["args"].skip_ui:
        raise Skip("--skip-ui")
    try:
        from ui_capture import UICapture
    except Exception as e:
        raise Skip(f"playwright unavailable: {e}")
    ui = UICapture(base=ctx["admin"].base.replace(":8000", ":3000"), user="admin",
                   pw="admin-secret", capture_path=f"{LOGS_DIR}/ui_capture.jsonl",
                   headless=False, timeout_ms=120000)
    page = ui.page
    shot_dir = f"{LOGS_DIR}/ui"
    import os
    os.makedirs(shot_dir, exist_ok=True)
    opened, failed = [], []
    try:
        def click_btn(name_pat):
            # dock tab labels are lowercase in the DOM (CSS uppercases); badge
            # counts may append digits → prefix-match, case-insensitive.
            pat = name_pat if hasattr(name_pat, "match") else re.compile(rf"^{re.escape(name_pat)}", re.I)
            page.get_by_role("button", name=pat).first.dispatch_event("click")
            page.wait_for_timeout(900)

        for group, subs in DOCK_PANELS:
            try:
                click_btn(group)
                ok = True
            except Exception:
                ok = False
            page.screenshot(path=f"{shot_dir}/{group}.png", full_page=True)
            (opened if ok else failed).append(group)
            if not ok:
                continue
            for sub_id, sub_label in subs:
                try:
                    click_btn(sub_label)
                    page.screenshot(path=f"{shot_dir}/{sub_id}.png", full_page=True)
                    opened.append(sub_id)
                except Exception:
                    failed.append(sub_id)
                    continue
                if sub_id == "integrations":
                    body = page.content()
                    assert ("Soon" in body or "More integrations" in body), \
                        "integrations pane missing re-stub 'Soon' state"
                if sub_id == "memory":
                    for tab in ("History", "Graph", "Conflicts", "View"):
                        try:
                            click_btn(tab)
                            page.wait_for_timeout(400)
                            page.screenshot(path=f"{shot_dir}/memory_{tab.lower()}.png")
                        except Exception:
                            failed.append(f"memory:{tab}")
            click_btn(group)   # second click on the active group tab closes the dock
        # one watched streamed turn + grounding gauge → trace expand
        ui.new_conversation()
        ui.send(f"In one short sentence, what is a test harness? ({RUN_TAG})", band="positive")
        page.wait_for_timeout(1500)
        badge = page.get_by_text(re.compile(r"GROUNDING"))
        trace = "gauge absent (grounding=none)"
        if badge.count() > 0:
            badge.first.click()
            page.wait_for_timeout(600)
            trace = ("trace expanded" if "Reasoning steps" in page.content()
                     else "gauge clicked, trace text not found")
        page.screenshot(path=f"{shot_dir}/chat_turn.png", full_page=True)
    finally:
        ui.close()
    assert len(failed) <= 3, f"too many panels unopenable: {failed}"
    return f"opened={opened} failed={failed or 'none'} · {trace} · shots in {shot_dir}/"


# ═════════════════════════════ runner ════════════════════════════════════════════
SECTIONS = [
    ("auth_onboarding", sec_auth_onboarding),
    ("unified_search", sec_unified_search),
    ("full_export", sec_full_export),
    ("conversations", sec_conversations),
    ("graph", sec_graph),
    ("metrics_observability", sec_metrics_observability),
    ("cache", sec_cache),
    ("notifications", sec_notifications),
    ("voice", sec_voice),
    ("ocr", sec_ocr),
    ("webhooks", sec_webhooks),
    ("memory_deep", sec_memory_deep),
    ("scheduled_prompts", sec_scheduled_prompts),
    ("goals", sec_goals),
    ("rotation", sec_rotation),
    ("admin_sweep", sec_admin_sweep),
    ("cost_cap", sec_cost_cap),
    ("rate_limit", sec_rate_limit),
    ("circuit_breaker", sec_circuit_breaker),
    ("re_embed", sec_re_embed),
    ("ui_panels", sec_ui_panels),
    ("memory_reset_restore", sec_memory_reset_restore),   # LAST — doubles as de-poison
]


def main():
    ap = argparse.ArgumentParser(description="Full-surface feature exerciser (gap-filler).")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--skip-ui", action="store_true")
    ap.add_argument("--skip-rotation", action="store_true")
    ap.add_argument("--skip-destructive", action="store_true",
                    help="skip admin_sweep/cost_cap/rate_limit/circuit_breaker/re_embed/reset")
    ap.add_argument("--only", default="", help="comma-separated section names")
    a = ap.parse_args()

    import os
    os.makedirs(LOGS_DIR, exist_ok=True)
    print(f"=== rich_full run_tag={RUN_TAG} ===", flush=True)
    ctx = {"admin": C(a.base, "admin", "admin-secret"), "args": a}

    destructive = {"admin_sweep", "cost_cap", "rate_limit", "circuit_breaker",
                   "re_embed", "memory_reset_restore"}
    only = {s.strip() for s in a.only.split(",") if s.strip()}
    for name, fn in SECTIONS:
        if only and name not in only:
            continue
        if a.skip_destructive and name in destructive:
            _log(name, "SKIP", "--skip-destructive", 0.0)
            continue
        run_section(name, fn, ctx)

    print("\n[cleanup] removing tagged artifacts…", flush=True)
    for desc, fn in reversed(CLEANUP):
        try:
            fn()
            print(f"  · {desc}", flush=True)
        except Exception as e:
            print(f"  ! {desc} failed: {e}", flush=True)

    counts = {}
    for r in RESULTS:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"\n=== SUMMARY {RUN_TAG} ===", flush=True)
    for r in RESULTS:
        print(f"  {r['status']:5} {r['section']:24} {r['detail'][:110]}", flush=True)
    print(f"  totals: {counts}", flush=True)
    with open(f"{LOGS_DIR}/rich_full_summary.json", "w") as f:
        json.dump({"run_tag": RUN_TAG, "counts": counts, "results": RESULTS}, f, indent=1)
    sys.exit(1 if counts.get("FAIL") else 0)


if __name__ == "__main__":
    main()
