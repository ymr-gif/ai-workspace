"""Measure connector-intent latch scores → Phase 2 outputs A / B / C (+ optional eval-set emit).

Joins ground-truth labels (agent_capture.py) with `latch_score` log lines and prints the three
measurements the data-first plan forks on. NO tuning here — this only describes the data.

Inputs:
  --capture latch_capture.jsonl   labels from agent_capture.py
  --scores  scores.txt | -        latch_score lines; accepts docker's "api-1 | {...}" wrapper,
                                   the inner JSON-logger object, or a bare latch_score object.
Harvest score lines first, e.g.:
  (cd docker && docker compose logs api) | grep latch_score > scores.txt

Join: (conv_id, order) — the Nth latch-expected send for a conv_id ↔ the Nth latch_score line
for that conv_id (sorted by `turn`). Robust to `turn` != ordinal and to cache-hit gaps.

Outputs:
  A. max(none_intent argmax_score)  vs  min(weak_real target_score)  → GAP or OVERLAP
  B. margin distribution (none_intent + tie)                          → δ candidate band
  C. cold/warm split of over-fires (prior_latch_state authoritative)  → which layer to fix
  --emit-evalsets DIR  →  write none_intent/weak_real/tie _eval.jsonl, tagged cold|warm

Threshold-dependent stats (C, "would-fire") use the live constants if importable, else defaults.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Live thresholds if backend is importable (run from backend/, or PYTHONPATH=backend); else defaults.
_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
try:
    from llm.tools.connector_intent import INTENT_THRESHOLDS, FLOOR_THRESHOLD  # type: ignore
    _THR_SRC = "live import"
except Exception:
    INTENT_THRESHOLDS = {"drive": 0.60, "calendar": 0.60, "gmail": 0.65}
    FLOOR_THRESHOLD = 0.65
    _THR_SRC = "defaults (backend not importable)"


# ---------- parsing ----------

def parse_score_line(line: str) -> dict | None:
    """Extract a latch_score dict from a raw log line in any of the three accepted shapes."""
    line = line.strip()
    if not line:
        return None
    brace = line.find("{")
    if brace < 0:
        return None
    blob = line[brace:]
    try:
        outer = json.loads(blob)
    except Exception:
        return None
    # JSON-logger wrapper: {"logger": "...scores", "message": "<inner json>"}
    if isinstance(outer, dict) and "message" in outer and outer.get("logger", "").endswith("scores"):
        try:
            inner = json.loads(outer["message"])
        except Exception:
            return None
    else:
        inner = outer
    if isinstance(inner, dict) and inner.get("evt") == "latch_score":
        return inner
    return None


def load_scores(path: str) -> list[dict]:
    fh = sys.stdin if path == "-" else open(path)
    try:
        out = [d for d in (parse_score_line(ln) for ln in fh) if d]
    finally:
        if fh is not sys.stdin:
            fh.close()
    return out


def load_capture(path: str) -> list[dict]:
    with open(path) as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


# ---------- join ----------

def join(capture: list[dict], scores: list[dict]) -> tuple[list[dict], list[str]]:
    """Per conv_id: zip latch-expected capture rows (by ordinal) with score lines (by turn)."""
    warns: list[str] = []
    cap_by_conv: dict[str, list[dict]] = {}
    for r in capture:
        if r.get("conv_id") and r.get("latch_expected"):
            cap_by_conv.setdefault(r["conv_id"], []).append(r)
    sc_by_conv: dict[str, list[dict]] = {}
    for s in scores:
        if s.get("conv_id"):
            sc_by_conv.setdefault(s["conv_id"], []).append(s)

    joined: list[dict] = []
    for conv, caps in cap_by_conv.items():
        caps.sort(key=lambda r: r["ordinal"])
        scs = sorted(sc_by_conv.get(conv, []), key=lambda s: (s.get("turn") if s.get("turn") is not None else 0))
        if len(caps) != len(scs):
            warns.append(f"conv {conv[:8]}: {len(caps)} labeled sends vs {len(scs)} score lines — zipping to min")
        for c, s in zip(caps, scs):
            prior = s.get("prior_latch_state", {}) or {}
            joined.append({
                **{k: c[k] for k in ("band", "connector", "expect_cold", "message", "ordinal")},
                "conv_id":      conv,
                "reason":       s.get("reason"),
                "scores":       s.get("scores", {}),
                "argmax":       s.get("argmax"),
                "argmax_score": s.get("argmax_score"),
                "runner_up":    s.get("runner_up"),
                "margin":       s.get("margin"),
                "decision":     s.get("decision"),
                "prior_latch":  prior,
                "warm":         any(prior.values()),
            })
    return joined, warns


# ---------- little stats helpers ----------

def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    i = min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1))))
    return xs[i]


def _hist(xs: list[float], lo=0.0, hi=1.0, bins=10, width=40) -> str:
    if not xs:
        return "  (no data)"
    counts = [0] * bins
    for x in xs:
        b = min(bins - 1, max(0, int((x - lo) / (hi - lo) * bins)))
        counts[b] += 1
    mx = max(counts) or 1
    rows = []
    for i, c in enumerate(counts):
        a = lo + (hi - lo) * i / bins
        bar = "#" * int(width * c / mx)
        rows.append(f"  {a:4.2f} |{bar:<{width}} {c}")
    return "\n".join(rows)


def _target_score(r: dict) -> float | None:
    """For weak_real/positive, the score of the labeled connector; else None."""
    if r.get("connector"):
        return (r.get("scores") or {}).get(r["connector"])
    return None


# ---------- report ----------

def report(joined: list[dict], warns: list[str]) -> None:
    print("=" * 70)
    print(f"thresholds: {INTENT_THRESHOLDS}  floor={FLOOR_THRESHOLD}  [{_THR_SRC}]")
    print(f"joined rows: {len(joined)}")
    by_reason: dict[str, int] = {}
    for r in joined:
        by_reason[r.get("reason") or "?"] = by_reason.get(r.get("reason") or "?", 0) + 1
    print(f"by reason:  {by_reason}   (only reason==ok used for score histograms)")
    for w in warns:
        print(f"  [warn] {w}")

    ok = [r for r in joined if r.get("reason") == "ok"]

    # ---- A: separation ----
    none_s = [r["argmax_score"] for r in ok if r["band"] == "none_intent" and r["argmax_score"] is not None]
    weak_s = [s for r in ok if r["band"] == "weak_real" for s in [_target_score(r)] if s is not None]
    print("\n--- A. separation: max(none_intent argmax) vs min(weak_real target) ---")
    if none_s and weak_s:
        mn, mw = max(none_s), min(weak_s)
        gap = mw - mn
        verdict = f"GAP {gap:+.3f}  → θ_min lives in ({mn:.3f}, {mw:.3f})" if gap > 0 \
            else f"OVERLAP {gap:+.3f}  → query_emb alone insufficient; go to fork (see C)"
        print(f"  max(none)={mn:.3f}  min(weak_real)={mw:.3f}  →  {verdict}")
    else:
        print(f"  insufficient data (none={len(none_s)}, weak_real={len(weak_s)}; "
              f"weak_real needs --connector on capture)")

    # ---- B: margin distribution ----
    mar = [r["margin"] for r in ok if r["band"] in ("none_intent", "tie") and r["margin"] is not None]
    print("\n--- B. margin (argmax - runner_up) on none_intent + tie  → δ band ---")
    if mar:
        print(f"  n={len(mar)}  p50={_pct(mar,50):.3f}  p75={_pct(mar,75):.3f}  "
              f"p90={_pct(mar,90):.3f}  max={max(mar):.3f}")
        print(_hist(mar, 0.0, max(0.3, max(mar)), bins=12))
        print("  δ should sit ABOVE this cluster (these are ambiguous/cross-talk turns).")
    else:
        print("  (no none_intent/tie rows)")

    # ---- C: cold/warm split of over-fires ----
    def _would_fire(r):
        a, s = r.get("argmax"), r.get("argmax_score")
        return a in INTENT_THRESHOLDS and s is not None and s >= max(INTENT_THRESHOLDS[a], FLOOR_THRESHOLD)

    of_actual = [r for r in ok if r["band"] == "none_intent" and str(r.get("decision", "")).startswith("latched_")]
    of_would  = [r for r in ok if r["band"] == "none_intent" and _would_fire(r)]
    print("\n--- C. over-fires on none_intent (cold vs warm) ---")
    for label, rows in (("actually latched (decision)", of_actual), ("would-fire @ current θ", of_would)):
        cold = sum(1 for r in rows if not r["warm"])
        warm = sum(1 for r in rows if r["warm"])
        print(f"  {label:<28} total={len(rows):<4} cold={cold:<4} warm={warm}")
    print("  mostly COLD → θ_min + clarify fallback fixes it.")
    print("  mostly WARM → leak is stickiness/TTL, NOT the floor — fix decay/re-score instead.")
    print("=" * 70)


def emit_evalsets(joined: list[dict], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for band in ("none_intent", "weak_real", "tie"):
        rows = [r for r in joined if r["band"] == band]
        path = os.path.join(out_dir, f"{band}_eval.jsonl")
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps({
                    "text":      r["message"],
                    "label":     band,
                    "cold":      not r["warm"],
                    "connector": r.get("connector"),
                    "scores":    r.get("scores"),
                    "argmax":    r.get("argmax"),
                    "margin":    r.get("margin"),
                    "reason":    r.get("reason"),
                }, ensure_ascii=False) + "\n")
        print(f"  wrote {len(rows):>4} → {path}")


def main():
    ap = argparse.ArgumentParser(description="Measure latch scores → Phase 2 A/B/C.")
    ap.add_argument("--capture", required=True)
    ap.add_argument("--scores", required=True, help="file of latch_score lines, or '-' for stdin")
    ap.add_argument("--emit-evalsets", default=None, metavar="DIR")
    a = ap.parse_args()

    capture = load_capture(a.capture)
    scores  = load_scores(a.scores)
    joined, warns = join(capture, scores)
    report(joined, warns)
    if a.emit_evalsets:
        print(f"\nemitting eval sets → {a.emit_evalsets}")
        emit_evalsets(joined, a.emit_evalsets)


if __name__ == "__main__":
    main()
