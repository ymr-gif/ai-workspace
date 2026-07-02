#!/usr/bin/env bash
# Orchestrator for the rich full-feature run (plan: happy-crafting-catmull).
# Phases: B existing tiers → C rich_exercise → D rich_full gap-filler.
# Preflight (phase A) and report/RUNLOG (phase E) are done by the operator around this script.
#
# Usage (from backend/tests/latch):
#   bash run_rich_full.sh [--skip-ui] [--skip-rotation] [--skip-live]
set -uo pipefail

BASE="${VERIFY_BASE_URL:-http://localhost:8000}"
LOGS=rich_full_logs
mkdir -p "$LOGS"
PASS_UI="" PASS_ROT="" SKIP_LIVE=0
for a in "$@"; do
  case "$a" in
    --skip-ui) PASS_UI="--skip-ui" ;;
    --skip-rotation) PASS_ROT="--skip-rotation" ;;
    --skip-live) SKIP_LIVE=1 ;;
  esac
done

FAILED=()
step() {  # step <name> <cmd...>
  local name="$1"; shift
  echo "=== [$name] $* ==="
  if "$@" 2>&1 | tee "$LOGS/$name.log"; then
    echo "=== [$name] OK ==="
  else
    echo "=== [$name] FAILED (see $LOGS/$name.log) ==="
    FAILED+=("$name")
  fi
}

cd "$(dirname "$0")"          # backend/tests/latch
BACKEND=../..

# ── Phase B — existing tiers (cheap → costly) ──────────────────────────────
step b1_unit      python3 -m pytest "$BACKEND" -m "not infra and not live_nim and not optional" -q --rootdir="$BACKEND"
step b2_retrieval python3 -m pytest "$BACKEND/tests/retrieval/" -q --rootdir="$BACKEND"
step b3_infra     env RUN_INFRA=1 python3 -m pytest "$BACKEND" -m infra -q --rootdir="$BACKEND"
if [ "$SKIP_LIVE" -eq 0 ]; then
  step b4_live    env RUN_LIVE_NIM=1 VERIFY_BASE_URL="$BASE" \
                  python3 -m pytest "$BACKEND/tests/live/" -q -m "live_nim or optional" --rootdir="$BACKEND"
  step b5_smoke   bash "$BACKEND/scripts/smoke.sh" "$BASE"
fi

# ── Phase C — rich_exercise (full agent loop; UI half unless --skip-ui) ────
if [ -n "$PASS_UI" ]; then
  step c_rich_exercise python3 rich_exercise.py --capture "$LOGS/rich.jsonl" --api-only
else
  step c_rich_exercise python3 rich_exercise.py --capture "$LOGS/rich.jsonl"
fi

# ── Phase D — gap-filler (incl. real mutations; reset finale = de-poison) ──
step d_rich_full python3 rich_full.py --base "$BASE" $PASS_UI $PASS_ROT

echo
echo "=== RICH FULL RUN COMPLETE ==="
if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "failed steps: ${FAILED[*]}"
  exit 1
fi
echo "all steps green — logs in $LOGS/"
