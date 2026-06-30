"""Layer 1 — deterministic, paced collection orchestrator for the connector-intent latch.

Generates labeled traffic through `LatchCapture`, paces to the rate limit, and appends to the
shared capture JSONL (→ `measure.py` unchanged). Phrasings come from `prompt_bank.PROMPTS` with
templated variation so repeats don't cache-hit.

Modes:
  singles   — each send is a fresh COLD conversation (clean cold-band score data).
  sessions  — multi-turn CONTINUOUS conversations: one conv_id, several varied turns. Turn 0 is
              cold; once a connector latches mid-session, every later turn is WARM — the efficient
              way to produce warm data (one 6-turn session ≈ 5 warm rows).
  mixed     — blend of both (default; --session-frac controls the split).

Lean (default ON): caps the model reply to 1 token. The latch runs BEFORE the model, so scores are
unaffected; this just stops the tool loop (the real token sink), keeps NIM cost ~flat over a long
run, and forces a cache bypass so the latch logs every turn. Use --rich only for realism passes.

Sizing: pick --target N or --duration 3h (or both → whichever hits first). At ~12 sends/min a 3h run
is ~2000 rows per worker. Token cost stays bounded by lean mode.

Examples:
  python3 run_collection.py --duration 3h --user admin --pw admin-secret --capture run.jsonl
  python3 run_collection.py --target 400 --mode sessions --user admin --pw admin-secret --capture run.jsonl
"""
from __future__ import annotations

import argparse
import random
import time

from agent_capture import LatchCapture, BANDS, CONNECTORS, DEFAULT_CAPTURE
from prompt_bank import PROMPTS

DEFAULT_WEIGHTS = {"none_intent": 0.40, "weak_real": 0.25, "tie": 0.10, "positive": 0.15, "easy_neg": 0.10}

_PREFIX = ["", "hey ", "ok ", "so ", "please ", "could you ", "can you ", "i need to ", "quick one — "]
_SUFFIX = ["", " please", " for me", " real quick", " now", " when you can", " thanks"]


def _vary(msg, rng):
    out = (rng.choice(_PREFIX) + msg + rng.choice(_SUFFIX)).strip()
    return (out[0].upper() + out[1:]) if out else out


def _sample(band, rng, connectors):
    if band in ("positive", "weak_real"):
        conn = rng.choice(connectors)
        return _vary(rng.choice(PROMPTS[band][conn]), rng), conn
    return _vary(rng.choice(PROMPTS[band]), rng), None


def _pick(weights, rng):
    total = sum(weights.values())
    r, acc = rng.random() * total, 0.0
    for b, w in weights.items():
        acc += w
        if r <= acc:
            return b
    return next(iter(weights))


def _parse_duration(s):
    s = s.strip().lower()
    mult = {"h": 3600, "m": 60, "s": 1}.get(s[-1:], 1)
    return float(s[:-1] if s[-1:] in "hms" else s) * mult


def _parse_range(s):
    if "-" in s:
        lo, hi = s.split("-", 1)
        return int(lo), int(hi)
    return int(s), int(s)


def run(*, target, duration, mode, session_frac, session_len, weights, base, user, pw, capture,
        rate_per_min, connectors, lean_tokens, lean_model, seed):
    rng = random.Random(seed)
    cap = LatchCapture(base=base, user=user, pw=pw, capture_path=capture)
    interval = 60.0 / max(1.0, rate_per_min)
    deadline = (time.monotonic() + duration) if duration else None
    counts: dict[str, int] = {}
    sent = 0
    t0 = time.monotonic()
    tag = f"[{user}/{seed}]"
    slo, shi = session_len
    print(f"{tag} start mode={mode} target={target} duration={duration}s rate={rate_per_min}/min "
          f"lean_tokens={lean_tokens} weights={weights}", flush=True)

    def more():
        if target and sent >= target:
            return False
        if deadline and time.monotonic() >= deadline:
            return False
        return True

    def one(band, conv, cold):
        nonlocal sent
        msg, conn = _sample(band, rng, connectors)
        try:
            out = cap.send(msg, band=band, connector=conn, conv_id=conv, expect_cold=cold,
                           max_tokens=lean_tokens, model_override=lean_model,
                           note=("session" if conv or not cold else "single"))
            counts[band] = counts.get(band, 0) + 1
            sent += 1
            return out
        except Exception as e:
            print(f"{tag} send failed ({band}): {e}", flush=True)
            return conv
        finally:
            time.sleep(interval)

    while more():
        do_session = (mode == "sessions") or (mode == "mixed" and rng.random() < session_frac)
        if do_session:
            conv = None
            for turn in range(rng.randint(slo, shi)):
                if not more():
                    break
                conv = one(_pick(weights, rng), conv, cold=(turn == 0))
        else:
            one(_pick(weights, rng), None, cold=True)

        if sent and sent % 25 == 0:
            el = int(time.monotonic() - t0)
            print(f"{tag} {sent} sent ({el}s) {counts}", flush=True)

    print(f"{tag} DONE {sent} sent in {int(time.monotonic()-t0)}s {counts}", flush=True)
    return counts


def main():
    ap = argparse.ArgumentParser(description="Layer 1 — paced latch data collection.")
    ap.add_argument("--target", type=int, default=0, help="stop after N sends")
    ap.add_argument("--duration", type=str, default="", help="stop after this long, e.g. 3h / 90m / 600s")
    ap.add_argument("--mode", choices=["singles", "sessions", "mixed"], default="mixed")
    ap.add_argument("--session-frac", type=float, default=0.6, help="(mixed) fraction of traffic as sessions")
    ap.add_argument("--session-len", type=str, default="4-8", help="turns per session, e.g. 4-8 or 5")
    ap.add_argument("--band-focus", choices=BANDS, default=None, help="collect only this band")
    ap.add_argument("--user", default="user")
    ap.add_argument("--pw", default="user-secret")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--capture", default=DEFAULT_CAPTURE)
    ap.add_argument("--rate", type=float, default=12.0, help="sends/min (keep < 15)")
    ap.add_argument("--connectors", default=",".join(CONNECTORS))
    ap.add_argument("--lean", dest="lean", action="store_true", default=True,
                    help="cap reply to 1 token (default; cheap, no tool loop)")
    ap.add_argument("--rich", dest="lean", action="store_false", help="full replies + tool loop (expensive)")
    ap.add_argument("--lean-tokens", type=int, default=1)
    ap.add_argument("--lean-model", default="", help="pin a model id (e.g. meta/llama-3.1-8b-instruct) "
                    "to minimize cost + dodge fallback churn; empty = let the router decide")
    ap.add_argument("--seed", type=int, default=random.randint(0, 1 << 30))
    a = ap.parse_args()

    if not a.target and not a.duration:
        ap.error("set --target and/or --duration")
    weights = {a.band_focus: 1.0} if a.band_focus else dict(DEFAULT_WEIGHTS)
    run(target=a.target,
        duration=_parse_duration(a.duration) if a.duration else None,
        mode=a.mode, session_frac=a.session_frac, session_len=_parse_range(a.session_len),
        weights=weights, base=a.base, user=a.user, pw=a.pw, capture=a.capture,
        rate_per_min=a.rate, connectors=[c.strip() for c in a.connectors.split(",") if c.strip()],
        lean_tokens=(a.lean_tokens if a.lean else None), lean_model=a.lean_model, seed=a.seed)


if __name__ == "__main__":
    main()
