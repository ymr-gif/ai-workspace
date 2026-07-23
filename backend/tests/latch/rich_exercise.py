"""Richest-rich exerciser — the opposite end of lean.

Where the latch collectors cap the reply to 1 token (no tool execution), this drives the FULL agent
loop: real replies, real tool calls, real connector round-trips, web search, and the write confirms
*executed for real* (with auto-cleanup). It also keeps the latch harness's session shape — multiple
back-to-back messages in one conversation.

NIM tokens are allowed to burn here (that's the point). It is deterministic — prompts come from a
fixed bank, so it costs ZERO AI-agent (Claude) tokens to generate; your agent just launches it and
reads the summary.

What it does per message: POST /chat/stream (no token cap), read the whole SSE stream, record which
tools fired (`tool_call` name), and when a write confirm appears:
  • confirm_calendar_write → POST /integrations/calendar/execute {op,args}; for a create it parses the
    returned `(id=…)` and immediately deletes it → real write+delete loop, calendar left clean.
  • confirm_write_memory   → POST /memory/write {fact}; the fact is tagged RICHTEST-<run> and reported
    for you to remove (no per-fact delete endpoint).

Half the sessions run via the API (headless, fast); half via the real UI (headed Playwright) so you
can WATCH the tool pills / cards happen live. UI sessions exercise the visible read/web/file tools;
write execute+cleanup is handled on the API sessions (no fragile confirm-card clicking).

Run (defaults: mixed API+UI, web enabled, writes executed+cleaned, as admin):
  python3 rich_exercise.py --capture rich.jsonl
  python3 rich_exercise.py --api-only            # no browser
  python3 rich_exercise.py --no-web              # skip web_search setup
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

# No literal password default — the old admin-secret/user-secret pair was rotated 2026-07-22.
# Set VERIFY_ADMIN_PW (same var conftest.py's live tier uses) or pass --pw explicitly.
DEFAULT_ADMIN_PW = os.environ.get("VERIFY_ADMIN_PW")

RUN_TAG = "RICHTEST-" + uuid.uuid4().hex[:8]
DOCKER_DIR = "../../../docker"


# ── tool-coverage prompts, grouped into back-to-back sessions ───────────────────
# Each inner list = one conversation (messages sent in order, same conv_id).
def _sessions(tag):
    nxt = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT15:00:00Z")
    # IMPORTANT: connector tools are latch-gated — a COLD turn won't have the schema. So each
    # connector session LEADS with a strong read to latch the connector, then does breadth/writes
    # on the SAME conversation (now warm/latched). Strong "use the X tool to…" steering makes the
    # tool-eager 70B actually emit the call. web_search/fetch_url/file/graph/write_memory are NOT
    # latch-gated, so they fire from a cold turn.
    return {
        # READ / SEARCH / WEB / FILE / GRAPH — safe to run in the UI (visible, no writes)
        "ui": [
            ["Use the web_search tool to find the current population of Tokyo.",
             "Use the fetch_url tool on https://example.com and tell me its title.",
             "Use the list_files tool to show my files."],
            ["Use the calendar tool to show what's on my calendar this week.",   # latch calendar
             "Now use the calendar tool to search my calendar for any meetings.",
             "Use the gmail tool to list my most recent emails."],               # latch gmail
            ["Use the drive tool to list my Google Drive files.",                # latch drive
             "Use the drive tool to search my drive for anything about budgets.",
             "Use the query_graph tool to tell me what my knowledge graph knows about me."],
        ],
        # WRITES + connector breadth — API sessions (execute + auto-clean), latch-first.
        "api": [
            ["Use the gmail tool to list my most recent emails.",                # latch gmail
             "Use the gmail tool to read my most recent email in full.",         # gmail_get
             "Use the gmail tool to search my gmail for 'invoice'.",             # gmail_search
             f"Remember this exact note: {tag} is my temporary test marker."],   # write_memory (not latch-gated)
            ["Use the calendar tool to show what's on my calendar this week.",    # latch calendar
             f"Now use the calendar tool to create an event titled '{tag} sync' two days from now from 3pm to 4pm.",  # create→execute→delete
             "Use the drive tool to list my Google Drive files and read the first one."],  # latch+read drive
        ],
    }, nxt


class RichClient:
    def __init__(self, base, user, pw, capture_path, timeout=300.0):
        self.base = base.rstrip("/")
        self.capture_path = capture_path
        self.timeout = timeout
        self.http = httpx.Client(timeout=timeout)
        self.token = self._login(user, pw)
        self.h = {"Authorization": f"Bearer {self.token}"}
        self.created_events: list[str] = []   # ids we created (and delete)
        self.memory_facts: list[str] = []     # tagged facts written (manual cleanup)

    def _login(self, user, pw):
        r = self.http.post(f"{self.base}/auth/token", data={"username": user, "password": pw})
        r.raise_for_status()
        return r.json()["access_token"]

    def _stream(self, message, conv_id):
        """One rich turn. Returns (conv_id, tools_fired, confirm_events, done)."""
        body = {"message": message}
        if conv_id:
            body["conversation_id"] = conv_id
        tools, confirms, done = [], [], {}
        with self.http.stream("POST", f"{self.base}/chat/stream", json=body, headers=self.h) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:])
                except Exception:
                    continue
                t = ev.get("type")
                if t == "tool_call":
                    tools.append(ev.get("name", ""))
                elif t in ("confirm_calendar_write", "confirm_write_memory"):
                    confirms.append(ev)
                elif t == "done":
                    done = ev
        return done.get("conversation_id") or conv_id, tools, confirms, done

    def _exec_confirm(self, ev):
        """Execute a write confirm for real, with cleanup. Returns a short status string."""
        if ev["type"] == "confirm_write_memory":
            fact = ev.get("fact", "")
            r = self.http.post(f"{self.base}/memory/write", json={"fact": fact}, headers=self.h)
            self.memory_facts.append(fact)
            return f"memory.write({fact[:40]!r}) → {r.status_code}"

        # confirm_calendar_write
        op = ev.get("op")
        args = dict(ev.get("args") or {})
        if op == "create":
            # Force a clean, valid, tagged event regardless of the model's arg quality.
            nxt = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
            args.setdefault("summary", f"{RUN_TAG} sync")
            args["summary"] = f"{RUN_TAG} " + str(args.get("summary", "sync"))[:40]
            args["start"] = nxt.strftime("%Y-%m-%dT15:00:00Z")
            args["end"] = nxt.strftime("%Y-%m-%dT16:00:00Z")
            r = self.http.post(f"{self.base}/integrations/calendar/execute",
                               json={"op": "create", "args": args}, headers=self.h)
            summ = (r.json() or {}).get("summary", "") if r.status_code == 200 else r.text[:120]
            m = re.search(r"id=([^)]+)\)", summ)
            if m:
                eid = m.group(1)
                self.created_events.append(eid)
                d = self.http.post(f"{self.base}/integrations/calendar/execute",
                                   json={"op": "delete", "args": {"event_id": eid}}, headers=self.h)
                return f"calendar.create→delete (id={eid[:12]}… create={r.status_code} delete={d.status_code})"
            return f"calendar.create → {r.status_code} (no id parsed: {summ[:60]})"
        # update/delete from the model — just run as given
        r = self.http.post(f"{self.base}/integrations/calendar/execute",
                           json={"op": op, "args": args}, headers=self.h)
        return f"calendar.{op} → {r.status_code}"

    def run_session(self, prompts, *, label):
        conv = None
        rows = []
        for i, msg in enumerate(prompts):
            t0 = time.monotonic()
            try:
                conv, tools, confirms, done = self._stream(msg, conv)
            except Exception as e:
                print(f"  [{label}] turn {i} ERROR: {e}", flush=True)
                continue
            execs = [self._exec_confirm(c) for c in confirms]
            dt = time.monotonic() - t0
            row = {"label": label, "turn": i, "conv_id": conv, "msg": msg[:80],
                   "tools": tools, "confirms": [c["type"] for c in confirms], "executed": execs,
                   "web_searched": done.get("web_searched"), "url_fetched": done.get("url_fetched"),
                   "secs": round(dt, 1)}
            rows.append(row)
            with open(self.capture_path, "a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"  [{label}] t{i} {dt:4.1f}s tools={tools or '-'} "
                  f"{'· '+'; '.join(execs) if execs else ''}", flush=True)
        return rows

    def close(self):
        self.http.close()


def enable_web(base, user, pw):
    """Turn on WEB_SEARCH_ENABLED (admin env) + start the searxng container."""
    try:
        http = httpx.Client(timeout=30)
        tok = http.post(f"{base}/auth/token", data={"username": user, "password": pw}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        http.put(f"{base}/admin/env/WEB_SEARCH_ENABLED", json={"value": "true"}, headers=h)
        http.post(f"{base}/admin/env/reload", headers=h)
        print("[setup] WEB_SEARCH_ENABLED=true + reloaded", flush=True)
    except Exception as e:
        print(f"[setup] env toggle failed (continuing): {e}", flush=True)
    try:
        subprocess.run(["docker", "compose", "--profile", "web-search", "up", "-d", "searxng"],
                       cwd=DOCKER_DIR, check=False, capture_output=True, timeout=120)
        print("[setup] searxng container up (profile web-search)", flush=True)
    except Exception as e:
        print(f"[setup] searxng start failed (web_search may skip): {e}", flush=True)


def run_ui_sessions(sessions, base, user, pw, capture_path):
    """Headed browser so you can WATCH the tool activity. Read/web tools only (no write clicks)."""
    try:
        from ui_capture import UICapture
    except Exception as e:
        print(f"[ui] Playwright unavailable, skipping UI sessions: {e}", flush=True)
        return
    ui = UICapture(base=base.replace(":8000", ":3000"), user=user, pw=pw,
                   capture_path=capture_path, headless=False, timeout_ms=300000)
    try:
        for s_i, prompts in enumerate(sessions):
            print(f"  [ui] session {s_i} (watch the browser)", flush=True)
            ui.new_conversation()
            for msg in prompts:
                try:
                    ui.send(msg, band="positive")   # band is just a capture tag here
                except Exception as e:
                    print(f"  [ui] send failed: {e}", flush=True)
    finally:
        ui.close()


def main():
    ap = argparse.ArgumentParser(description="Richest-rich full-tool exerciser.")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--pw", default=DEFAULT_ADMIN_PW, help="password (env VERIFY_ADMIN_PW; no default)")
    ap.add_argument("--capture", default="rich.jsonl")
    ap.add_argument("--api-only", action="store_true", help="skip the headed UI sessions")
    ap.add_argument("--ui-only", action="store_true", help="skip the API (write) sessions")
    ap.add_argument("--no-web", action="store_true", help="don't enable web_search/searxng")
    a = ap.parse_args()
    if not a.pw:
        ap.error("--pw not given and VERIFY_ADMIN_PW not set — seeded password was rotated, there is no default")

    sessions, _ = _sessions(RUN_TAG)
    print(f"=== rich_exercise run_tag={RUN_TAG} ===", flush=True)
    if not a.no_web:
        enable_web(a.base, a.user, a.pw)

    all_tools, all_exec = set(), []
    if not a.ui_only:
        c = RichClient(a.base, a.user, a.pw, a.capture)
        for s_i, prompts in enumerate(sessions["api"]):
            print(f"[api] session {s_i}", flush=True)
            for r in c.run_session(prompts, label=f"api{s_i}"):
                all_tools.update(r["tools"]); all_exec += r["executed"]
        print(f"\n[cleanup] calendar events created+deleted: {len(c.created_events)}", flush=True)
        if c.memory_facts:
            print("[cleanup] memory facts written (remove manually via Memory panel / soft reset):", flush=True)
            for f in c.memory_facts:
                print("   -", f[:90], flush=True)
        c.close()
    if not a.api_only:
        run_ui_sessions(sessions["ui"], a.base, a.user, a.pw, a.capture)

    print("\n=== TOOL COVERAGE (API sessions) ===", flush=True)
    print("fired:", ", ".join(sorted(t for t in all_tools if t)) or "(none)", flush=True)
    for e in all_exec:
        print("exec:", e, flush=True)
    print(f"\nrun_tag {RUN_TAG} — capture: {a.capture}. Log it in RUNLOG.md.", flush=True)


if __name__ == "__main__":
    main()
