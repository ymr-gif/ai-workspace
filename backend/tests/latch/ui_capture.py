"""Browser (Playwright) twin of agent_capture.py — drives the real Eidetic UI at localhost:3000.

Same job, same capture schema, same downstream `measure.py` — but messages go in through the
actual React app (login form → "Ask anything…" box → Enter) instead of a raw API call. Use this
for UI-realism passes (the full agent loop, confirm cards, OAuth-connected connectors as a user
sees them). For bulk latch-score volume prefer `agent_capture.py` — it's identical at the latch
and far more robust.

Like the API wrapper, this reads the `/chat/stream` SSE response off the network, so it captures
`conversation_id` + `cache_hit` precisely (not scraped from the DOM). Capture rows carry the same
keys agent_capture writes (+ "source": "ui"), so `measure.py` is unchanged.

Setup (host, not the container):
    pip install playwright && playwright install chromium

CLI (one cold send):
    python ui_capture.py --message "find my things" --band none_intent

Import (multi-turn; new_conversation() for a fresh COLD turn, consecutive send() = WARM):
    ui = UICapture(base="http://localhost:3000", user="user", pw=os.environ["VERIFY_USER_PW"])
    ui.new_conversation(); ui.send("what's on my calendar", band="positive", connector="calendar")
    ui.send("ok thanks", band="easy_neg", expect_cold=False)   # warm turn, same conv
    ui.close()
"""
from __future__ import annotations

import argparse
import json
import os
import time

from agent_capture import BANDS, CONNECTORS, DEFAULT_CAPTURE, DEFAULT_USER_PW   # reuse validation + schema constants

UI_BASE = os.environ.get("EIDETIC_UI", "http://localhost:3000")


def _parse_done(sse_body: str) -> dict:
    """Pull the `done` event out of a completed SSE response body."""
    done: dict = {}
    for line in sse_body.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            evt = json.loads(line[6:])
        except Exception:
            continue
        if evt.get("type") == "done":
            done = evt
    return done


class UICapture:
    def __init__(self, base=UI_BASE, user="user", pw=DEFAULT_USER_PW,
                 capture_path=DEFAULT_CAPTURE, headless=True, timeout_ms=90000):
        from playwright.sync_api import sync_playwright   # imported here so the module loads w/o playwright
        self.capture_path = capture_path
        self.timeout_ms   = timeout_ms
        self._ordinals: dict[str, int] = {}
        self._pw      = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=headless)
        self.page     = self._browser.new_page()
        self.page.set_default_timeout(timeout_ms)
        self._login(base, user, pw)

    def _login(self, base, user, pw):
        if not pw:
            raise ValueError(
                "no password given and VERIFY_USER_PW is not set — the seeded password was "
                "rotated, there is no default. Export VERIFY_USER_PW or pass pw= explicitly."
            )
        self.page.goto(base)
        self.page.fill('input[name="username"]', user)
        self.page.fill('input[name="password"]', pw)
        self.page.click('button[type="submit"]')
        self.page.wait_for_selector('input[placeholder^="Ask"]')
        self._dismiss_onboarding()

    def _dismiss_onboarding(self):
        try:
            skip = self.page.get_by_text("Skip onboarding", exact=False)
            if skip.count() > 0:
                skip.first.click(timeout=2000)
        except Exception:
            pass

    def new_conversation(self):
        """Start a fresh (cold) conversation — clears the persisted active id and reloads."""
        self.page.evaluate("localStorage.removeItem('nim_active_conv')")
        self.page.reload()
        self.page.wait_for_selector('input[placeholder^="Ask"]')
        self._dismiss_onboarding()

    def send(self, message, *, band, connector=None, expect_cold=None, note=""):
        if band not in BANDS:
            raise ValueError(f"band must be one of {BANDS}, got {band!r}")
        if connector is not None and connector not in CONNECTORS:
            raise ValueError(f"connector must be one of {CONNECTORS}, got {connector!r}")

        box = self.page.locator('input[placeholder^="Ask"]')
        box.fill(message)
        with self.page.expect_response(lambda r: "/chat/stream" in r.url) as ri:
            box.press("Enter")
        body = ri.value.text()                      # resolves when the SSE stream closes
        done = _parse_done(body)
        # input re-enables when the turn finishes
        try:
            self.page.wait_for_selector('input[placeholder^="Ask"]:not([disabled])')
        except Exception:
            pass

        conv      = done.get("conversation_id")
        cache_hit = bool(done.get("cache_hit"))
        key       = conv or "__no_conv__"
        ordinal   = self._ordinals.get(key, 0)
        self._ordinals[key] = ordinal + 1

        rec = {
            "ts":             time.time(),
            "band":           band,
            "connector":      connector,
            "expect_cold":    (ordinal == 0) if expect_cold is None else bool(expect_cold),
            "conv_id":        conv,
            "ordinal":        ordinal,
            "cache_hit":      cache_hit,
            "latch_expected": (not cache_hit) and conv is not None,
            "message":        message,
            "note":           note,
            "error":          None,
            "source":         "ui",
        }
        with open(self.capture_path, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if conv is None:
            print("[warn] no conversation_id in done — row unjoinable", flush=True)
        return conv

    def close(self):
        try:
            self._browser.close()
        finally:
            self._pw.stop()


def _cli():
    ap = argparse.ArgumentParser(description="Send one labeled latch-capture turn through the UI.")
    ap.add_argument("--message", required=True)
    ap.add_argument("--band", required=True, choices=BANDS)
    ap.add_argument("--connector", choices=CONNECTORS, default=None)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--expect-cold", dest="expect_cold", action="store_true")
    g.add_argument("--expect-warm", dest="expect_cold", action="store_false")
    ap.set_defaults(expect_cold=None)
    ap.add_argument("--base", default=UI_BASE)
    ap.add_argument("--user", default="user")
    ap.add_argument("--pw", default=DEFAULT_USER_PW, help="password (env VERIFY_USER_PW; no default)")
    ap.add_argument("--capture", default=DEFAULT_CAPTURE)
    ap.add_argument("--note", default="")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    a = ap.parse_args()
    if not a.pw:
        ap.error("--pw not given and VERIFY_USER_PW not set — seeded password was rotated, there is no default")

    ui = UICapture(base=a.base, user=a.user, pw=a.pw, capture_path=a.capture, headless=not a.headed)
    try:
        ui.new_conversation()
        conv = ui.send(a.message, band=a.band, connector=a.connector,
                       expect_cold=a.expect_cold, note=a.note)
        print(conv or "")
    finally:
        ui.close()


if __name__ == "__main__":
    _cli()
