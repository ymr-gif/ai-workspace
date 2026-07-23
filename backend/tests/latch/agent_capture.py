"""Labeled-capture wrapper for connector-intent latch data collection (Phase 0→2).

Agents drive synthetic traffic through JARVIS `/chat/stream` THROUGH this wrapper, so every
send is tagged with its ground-truth band + intended connector. The wrapper writes one
capture row per send (conv_id + per-conv ordinal + label) to a JSONL; the latch emits one
`latch_score` log line per non-cached turn. `measure.py` joins the two by (conv_id, order).

WHY a wrapper and not a marker in the text: the label must NOT go into the message — it would
be embedded into `query_emb` and shift every cosine score. The join key is (conv_id, send
ordinal), both captured out-of-band here.

Bands (see prompt_bank.py):
  positive     clear single-connector intent       "what's on my calendar"     (--connector)
  weak_real    terse but genuine                    "get that document"          (--connector)
  none_intent  connector-adjacent vagueness / task  "find my things", "debug this"
  tie          multi-connector                      "what's in my files and my email"
  easy_neg     greetings / chit-chat / tech Qs      "hello", "thanks"

CLI (one send; prints the conv_id so a shell agent can continue the session):
  python agent_capture.py --message "find my things" --band none_intent
  python agent_capture.py --message "get that document" --band weak_real --connector drive --conv <id> --expect-warm

Import (multi-turn, incl. the warm-leak case):
  cap  = LatchCapture(base="http://localhost:8000", user="user", pw=os.environ["VERIFY_USER_PW"])
  conv = cap.send("what's on my calendar", band="positive", connector="calendar")  # cold latch
  cap.send("ok thanks", band="easy_neg", conv_id=conv, expect_cold=False)          # warm turn → leak?

Notes:
  - cache hits return before the latch → no `latch_score` line; the row is marked
    latch_expected=False so measure.py keeps the ordinal alignment.
  - cold/warm is annotated here (expect_cold) but measure.py treats the latch line's
    `prior_latch_state` as authoritative.
  - run against the same user the connector is OAuth'd under, else `decision` stays "none"
    (scores still log — useful for the none/weak/tie score bands).
"""
from __future__ import annotations

import argparse
import json
import os
import time

import httpx

DEFAULT_BASE    = os.environ.get("JARVIS_BASE", "http://localhost:8000")
DEFAULT_CAPTURE = os.environ.get("LATCH_CAPTURE", "latch_capture.jsonl")
BANDS           = ["positive", "weak_real", "none_intent", "tie", "easy_neg"]
CONNECTORS      = ["drive", "calendar", "gmail"]
# No literal password default — the old admin-secret/user-secret pair was rotated 2026-07-22.
# Set VERIFY_USER_PW (same var conftest.py's live tier uses) or pass pw=/--pw explicitly.
DEFAULT_USER_PW = os.environ.get("VERIFY_USER_PW")


class LatchCapture:
    def __init__(self, base=DEFAULT_BASE, user="user", pw=DEFAULT_USER_PW, token=None,
                 capture_path=DEFAULT_CAPTURE, timeout=90.0):
        self.base         = base.rstrip("/")
        self.capture_path = capture_path
        self.timeout      = timeout
        self._ordinals: dict[str, int] = {}   # conv_id -> next ordinal
        self.token        = token or self._login(user, pw)

    def _login(self, user, pw):
        if not pw:
            raise ValueError(
                "no password given and VERIFY_USER_PW is not set — the seeded password was "
                "rotated, there is no default. Export VERIFY_USER_PW or pass pw= explicitly."
            )
        r = httpx.post(f"{self.base}/auth/token",
                       data={"username": user, "password": pw}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["access_token"]

    def send(self, message, *, band, connector=None, conv_id=None,
             expect_cold=None, note="", max_tokens=None, model_override=None):
        """Send one turn, record a labeled capture row, return the (server) conv_id.

        max_tokens caps the model reply. Passing max_tokens=1 ("lean") is the cheap path for
        data collection: the latch runs BEFORE the model so the score is unaffected, the cache
        is bypassed (model_params present) so the latch always logs, and a 1-token reply can't
        emit a tool call — so the tool loop (the real token sink) never starts.
        """
        if band not in BANDS:
            raise ValueError(f"band must be one of {BANDS}, got {band!r}")
        if connector is not None and connector not in CONNECTORS:
            raise ValueError(f"connector must be one of {CONNECTORS}, got {connector!r}")

        body = {"message": message}
        if conv_id:
            body["conversation_id"] = conv_id
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if model_override:
            body["model_override"] = model_override

        done: dict = {}
        err: str | None = None
        with httpx.stream("POST", f"{self.base}/chat/stream", json=body,
                          headers={"Authorization": f"Bearer {self.token}"},
                          timeout=self.timeout) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                try:
                    evt = json.loads(line[6:])
                except Exception:
                    continue
                t = evt.get("type")
                if t == "done":
                    done = evt
                elif t == "error":
                    err = evt.get("message", "error")

        new_conv  = done.get("conversation_id") or conv_id
        cache_hit = bool(done.get("cache_hit"))

        key     = new_conv or "__no_conv__"
        ordinal = self._ordinals.get(key, 0)
        self._ordinals[key] = ordinal + 1

        rec = {
            "ts":             time.time(),
            "band":           band,
            "connector":      connector,
            "expect_cold":    (conv_id is None) if expect_cold is None else bool(expect_cold),
            "conv_id":        new_conv,
            "ordinal":        ordinal,
            "cache_hit":      cache_hit,
            "latch_expected": (not cache_hit) and new_conv is not None,
            "message":        message,
            "note":           note,
            "error":          err,
        }
        with open(self.capture_path, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if new_conv is None:
            print(f"[warn] no conversation_id in done (error={err!r}) — row unjoinable", flush=True)
        return new_conv


def _cli():
    ap = argparse.ArgumentParser(description="Send one labeled latch-capture turn.")
    ap.add_argument("--message", required=True)
    ap.add_argument("--band", required=True, choices=BANDS)
    ap.add_argument("--connector", choices=CONNECTORS, default=None)
    ap.add_argument("--conv", default=None, help="continue an existing conversation")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--expect-cold", dest="expect_cold", action="store_true")
    g.add_argument("--expect-warm", dest="expect_cold", action="store_false")
    ap.set_defaults(expect_cold=None)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--user", default="user")
    ap.add_argument("--pw", default=DEFAULT_USER_PW, help="password (env VERIFY_USER_PW; no default)")
    ap.add_argument("--capture", default=DEFAULT_CAPTURE)
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if not a.pw:
        ap.error("--pw not given and VERIFY_USER_PW not set — seeded password was rotated, there is no default")

    cap  = LatchCapture(base=a.base, user=a.user, pw=a.pw, capture_path=a.capture)
    conv = cap.send(a.message, band=a.band, connector=a.connector, conv_id=a.conv,
                    expect_cold=a.expect_cold, note=a.note)
    print(conv or "")   # stdout = conv_id, so: CONV=$(python agent_capture.py ...)


if __name__ == "__main__":
    _cli()
