"""Layer 2 — multi-worker fleet over Layer 1.

Two modes:

1. Automated fleet (default): spawns several `run_collection.py` workers in parallel — one per
   account — all appending to the SAME capture file. The connector-bearing account (admin) runs a
   mixed flip+warm focus (gives `decision: latched_X` + warm rows); the other accounts run
   score-band focus (none_intent/weak_real/tie, scores log without an active connector). Each worker
   self-paces under the per-user rate limit, so one worker per account is the unit of parallelism —
   to scale score volume, seed more users (`create_user.py`) and add them to --accounts.

       python fleet.py --capture run.jsonl --admin-target 150 --score-target 400

2. Briefings (`--briefings`): prints a ready-to-paste prompt per band for human-launched LLM agents
   (improvising phrasings via the agent_capture CLI) instead of the deterministic workers. Use when
   you want richer Band-1 phrasing than the templated bank.

       python fleet.py --briefings

After either run: harvest + measure (see README / kickoff runbook).
"""
from __future__ import annotations

import argparse
import subprocess
import sys

BANK_NOTE = "agent_capture.py CLI (one send per call; --connector required for positive/weak_real)"


def _brief(band: str, account: str) -> str:
    conn = " --connector <drive|calendar|gmail>" if band in ("positive", "weak_real") else ""
    return f"""\
─── AGENT: band={band} · account={account} ───
You generate latch data collection traffic for ONE band: **{band}**.
Mission: send MANY varied, realistic '{band}' messages — collect data, do NOT tune anything.
Rules:
  • Improvise diverse phrasings (don't repeat — identical text cache-hits and skips the latch).
  • Band meaning: see prompt_bank.py PROMPTS['{band}'] for the intent; go beyond those examples.
  • Send each via: python agent_capture.py --message "<your text>" --band {band}{conn} \\
        --user {account} --pw <pw> --capture run.jsonl
  • For WARM rows: latch a connector with a positive turn, capture the printed conv_id, then send an
    unrelated follow-up with --conv <id> --expect-warm (only meaningful on the admin account).
  • Pace yourself: < 15 sends / 60s per account. Graphify-first if you read code.
Full briefing: plans/latch-data-session-kickoff.md (Part A). Stop after ~N sends; report counts."""


def briefings():
    print("# Paste each block into a separate LLM agent. Split bands across agents; use distinct")
    print("# accounts for score bands and ADMIN for anything that must actually latch.\n")
    for band, acct in [("none_intent", "user"), ("weak_real", "admin"),
                       ("tie", "user"), ("positive", "admin"), ("easy_neg", "user")]:
        print(_brief(band, acct), "\n")


def fleet(capture, accounts, admin_target, score_target, duration, rate, base):
    """accounts: list of (user, pw). The admin-named account runs mixed (flips+warm via sessions);
    others run score-band singles. duration (e.g. '3h') overrides the per-worker targets if set."""
    procs = []
    seed = 1000
    for user, pw in accounts:
        is_admin = "admin" in user
        if is_admin:
            args = ["--mode", "mixed"]                              # sessions → flips + warm rows
            args += ["--duration", duration] if duration else ["--target", str(admin_target)]
        else:
            args = ["--mode", "singles", "--band-focus", "none_intent"]   # cold score volume
            args += ["--duration", duration] if duration else ["--target", str(score_target)]
        cmd = [sys.executable, "run_collection.py",
               "--user", user, "--pw", pw, "--capture", capture,
               "--base", base, "--rate", str(rate), "--seed", str(seed)] + args
        print("spawn:", " ".join(cmd), flush=True)
        procs.append(subprocess.Popen(cmd))
        seed += 1

    print(f"\nfleet running: {len(procs)} workers → {capture}. Ctrl-C to stop.\n", flush=True)
    rc = 0
    try:
        for p in procs:
            rc |= p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        print("\nfleet stopped.")
    print(f"\nfleet done (rc={rc}). Next: harvest + measure —")
    print("  (cd ../../../docker && docker compose logs api) | grep latch_score > scores.txt")
    print(f"  PYTHONPATH=../.. python measure.py --capture {capture} --scores scores.txt --emit-evalsets ..")


def _parse_accounts(s: str) -> list[tuple[str, str]]:
    out = []
    for pair in s.split(","):
        pair = pair.strip()
        if not pair:
            continue
        u, _, p = pair.partition(":")
        out.append((u, p))
    return out


def main():
    ap = argparse.ArgumentParser(description="Layer 2 — multi-worker collection fleet.")
    ap.add_argument("--briefings", action="store_true", help="print LLM-agent briefings and exit")
    ap.add_argument("--capture", default="run.jsonl")
    ap.add_argument("--accounts", default="admin:admin-secret,user:user-secret",
                    help="comma list of user:pw; admin-named account runs flips+warm, rest score-band")
    ap.add_argument("--admin-target", type=int, default=150)
    ap.add_argument("--score-target", type=int, default=400)
    ap.add_argument("--duration", type=str, default="", help="run every worker this long (e.g. 3h); overrides targets")
    ap.add_argument("--rate", type=float, default=12.0)
    ap.add_argument("--base", default="http://localhost:8000")
    a = ap.parse_args()

    if a.briefings:
        briefings()
        return
    fleet(a.capture, _parse_accounts(a.accounts), a.admin_target, a.score_target, a.duration, a.rate, a.base)


if __name__ == "__main__":
    main()
