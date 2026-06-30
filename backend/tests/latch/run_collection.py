"""Layer 1 — deterministic, paced collection orchestrator for the connector-intent latch.

Loops weighted band picks through `LatchCapture`, scripts cold/warm sessions, paces to the rate
limit, and appends to the shared capture JSONL (→ `measure.py` unchanged). Phrasings are drawn from
`prompt_bank.PROMPTS` with templated prefix/suffix variation so repeats don't cache-hit (a cache hit
skips the latch → no score line).

Account routing is per-process: run flip/warm-bearing collection as the connector-bearing account
(`--user admin`), pure score-band collection as any account. (Warm rows only materialize when the
positive turn actually latches, i.e. the connector is active for that account.)

Examples:
  # mixed run on the connector account (gets flips + warm rows)
  python run_collection.py --target 200 --user admin --pw admin-secret --capture run.jsonl
  # score-band volume on a plain account (no flips needed; scores still log)
  python run_collection.py --target 400 --band-focus none_intent --user user --pw user-secret --capture run.jsonl
"""
from __future__ import annotations

import argparse
import random
import time

from agent_capture import LatchCapture, BANDS, CONNECTORS, DEFAULT_CAPTURE
from prompt_bank import PROMPTS

DEFAULT_WEIGHTS = {"none_intent": 0.40, "weak_real": 0.25, "tie": 0.10, "positive": 0.15, "easy_neg": 0.10}

# Templated variation: ~9×7 surface forms per base phrase → enough unique strings to dodge the cache
# over hundreds of sends while keeping the band intent intact.
_PREFIX = ["", "hey ", "ok ", "so ", "please ", "could you ", "can you ", "i need to ", "quick one — "]
_SUFFIX = ["", " please", " for me", " real quick", " now", " when you can", " thanks"]


def _vary(msg: str, rng: random.Random) -> str:
    out = (rng.choice(_PREFIX) + msg + rng.choice(_SUFFIX)).strip()
    return (out[0].upper() + out[1:]) if out else out


def _sample(band: str, rng: random.Random, connectors: list[str]) -> tuple[str, str | None]:
    if band in ("positive", "weak_real"):
        conn = rng.choice(connectors)
        return _vary(rng.choice(PROMPTS[band][conn]), rng), conn
    return _vary(rng.choice(PROMPTS[band]), rng), None


def _pick(weights: dict[str, float], rng: random.Random) -> str:
    total = sum(weights.values())
    r, acc = rng.random() * total, 0.0
    for b, w in weights.items():
        acc += w
        if r <= acc:
            return b
    return next(iter(weights))


def run(target, weights, *, base, user, pw, capture, rate_per_min, warm_rate, connectors, seed):
    rng = random.Random(seed)
    cap = LatchCapture(base=base, user=user, pw=pw, capture_path=capture)
    interval = 60.0 / max(1.0, rate_per_min)
    sent = 0
    counts: dict[str, int] = {}
    tag = f"[{user}/{seed}]"
    print(f"{tag} start: target={target} rate={rate_per_min}/min warm_rate={warm_rate} weights={weights}", flush=True)

    while sent < target:
        band = _pick(weights, rng)
        msg, conn = _sample(band, rng, connectors)
        try:
            conv = cap.send(msg, band=band, connector=conn, expect_cold=True)
            counts[band] = counts.get(band, 0) + 1
            sent += 1
        except Exception as e:
            print(f"{tag} send failed ({band}): {e}", flush=True)
            time.sleep(interval)
            continue
        time.sleep(interval)

        # Manufacture a WARM row: after a connector-targeting turn (which latches when active),
        # send an unrelated follow-up on the SAME conv so its prior_latch_state is warm.
        if conv and band in ("positive", "weak_real") and rng.random() < warm_rate and sent < target:
            fb_band = rng.choice(["easy_neg", "none_intent"])
            fmsg, _ = _sample(fb_band, rng, connectors)
            try:
                cap.send(fmsg, band=fb_band, conv_id=conv, expect_cold=False, note="warm-followup")
                counts[fb_band] = counts.get(fb_band, 0) + 1
                sent += 1
            except Exception as e:
                print(f"{tag} warm-followup failed: {e}", flush=True)
            time.sleep(interval)

        if sent % 25 == 0:
            print(f"{tag} {sent}/{target} {counts}", flush=True)

    print(f"{tag} DONE {sent} sent {counts}", flush=True)
    return counts


def main():
    ap = argparse.ArgumentParser(description="Layer 1 — paced latch data collection.")
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--band-focus", choices=BANDS, default=None, help="collect only this band")
    ap.add_argument("--user", default="user")
    ap.add_argument("--pw", default="user-secret")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--capture", default=DEFAULT_CAPTURE)
    ap.add_argument("--rate", type=float, default=12.0, help="sends/min (keep < 15 to respect the limit)")
    ap.add_argument("--warm-rate", type=float, default=0.25, help="P(follow-up warm turn) after a connector turn")
    ap.add_argument("--connectors", default=",".join(CONNECTORS))
    ap.add_argument("--seed", type=int, default=random.randint(0, 1 << 30))
    a = ap.parse_args()

    weights = {a.band_focus: 1.0} if a.band_focus else dict(DEFAULT_WEIGHTS)
    connectors = [c.strip() for c in a.connectors.split(",") if c.strip()]
    run(a.target, weights, base=a.base, user=a.user, pw=a.pw, capture=a.capture,
        rate_per_min=a.rate, warm_rate=a.warm_rate, connectors=connectors, seed=a.seed)


if __name__ == "__main__":
    main()
