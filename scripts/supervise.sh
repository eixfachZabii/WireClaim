#!/usr/bin/env bash
#
# Keep the runner alive for the whole tournament.
#
#     pixi run play          # instead of `pixi run start`
#
# `main.py`'s `watch_games()` awaits `run_game()` with no exception boundary around it
# (main.py:323). Everything that talks to the network inside `run_game` is already caught,
# but the merge loop itself is not -- `_apply_event` raises `ValueError` on an unrecognised
# event kind, and `coordinator.start()`, `blind_floor()`, `standard_values(case)` and
# `coordinator.close()` all sit outside any handler. One uncaught exception there does not
# cost a Game; it ends the tournament, because the coroutine dies and the process exits.
#
# That is the whole reason this file exists. It converts "ends the tournament" into "costs
# at most one Game", without touching a line of the submission path -- which matters,
# because the submission path is the thing we cannot afford to regress at 03:00.
#
# CLAUDE.md rule 8: uptime outranks accuracy. Break-even uptime is 71%, rescuing one Game is
# worth `93t` against `37t` for improving one, and the overnight window (Games ~44-81) is
# both the longest unattended stretch and the one where an outage costs the most -- a dark
# team pays `1.5a` to every awake opponent on every Line Item and earns nothing back.
#
# Deliberately dumb: no Python, no imports, no dependency on the package tree that a bad
# merge could break. If `main.py` cannot even start, this still runs and still retries.

set -u

cd "$(dirname "$0")/.." || exit 1

LOG_DIR="var"
LOG="${LOG_DIR}/runner.log"
mkdir -p "${LOG_DIR}"

# A crash loop is worse than a stopped runner: it burns the API key against a Game it cannot
# play and buries the real error. So back off when restarts come faster than a Game does.
# Games are 757.575758 s apart, so anything that dies inside 60 s never played one.
MIN_HEALTHY_SECONDS=60
BACKOFF_SECONDS=15
MAX_CONSECUTIVE_FAST_EXITS=20

stamp() { date '+%Y-%m-%d %H:%M:%S'; }
say() { echo "[$(stamp)] supervise: $*" | tee -a "${LOG}"; }

trap 'say "stopped by signal -- not restarting."; exit 0' INT TERM

say "starting; logging to ${LOG}"
fast_exits=0

while true; do
  started_at=$(date +%s)
  say "launching main.py"

  # `python main.py` rather than `pixi run start`, so a restart does not re-resolve the
  # environment on every loop -- and so this works when invoked from a pixi task, which is
  # already inside the environment.
  python main.py 2>&1 | tee -a "${LOG}"
  code=${PIPESTATUS[0]}

  ran_for=$(( $(date +%s) - started_at ))
  say "main.py exited ${code} after ${ran_for}s"

  if [ "${ran_for}" -lt "${MIN_HEALTHY_SECONDS}" ]; then
    fast_exits=$(( fast_exits + 1 ))
    if [ "${fast_exits}" -ge "${MAX_CONSECUTIVE_FAST_EXITS}" ]; then
      say "${fast_exits} consecutive exits under ${MIN_HEALTHY_SECONDS}s -- giving up so the"
      say "failure is visible instead of buried. Read ${LOG} from the bottom."
      exit 1
    fi
    say "fast exit ${fast_exits}/${MAX_CONSECUTIVE_FAST_EXITS}; sleeping ${BACKOFF_SECONDS}s"
    sleep "${BACKOFF_SECONDS}"
  else
    # It played for a while, so whatever killed it was not a startup failure. Restart at
    # once: the next Game is at most 757 s away and we want to be waiting for it.
    fast_exits=0
    sleep 2
  fi
done
