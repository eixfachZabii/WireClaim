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

# Refuse to be the second runner. `pixi run play` was invoked five times in one night, and
# nothing stopped two supervisors from holding a live `main.py` each. Two runners do not
# double our coverage, they compete: both PUT to the same Game so the Submission becomes a
# race whose winner is whichever finished last, and both fire Strategy 2's two-draw ensemble,
# putting four model calls into one 60-second window. Four concurrent calls is exactly the
# contention that lost Game 46 both of its draws to a timeout and Game 49 one to an HTTP 429.
#
# `mkdir` is the mutex because it is atomic on every filesystem we might run on and needs no
# `flock`, which macOS does not ship. The PID inside lets a stale lock -- from a `kill -9`, or
# a laptop sleep -- be told apart from a live one, so this cannot lock us out of our own
# tournament. That distinction matters more than the guard: refusing to start when nothing is
# running would be a worse bug than the one being fixed.
#
# The lock is checked *second*, because it cannot see a runner that predates it. A supervisor
# started before this guard existed holds no lock, and on the night this was written exactly
# such a process was live -- so a lock-only check would have cheerfully started the second
# runner it exists to prevent. `pgrep` is the guard that does not depend on our own bookkeeping:
# at this point we have not launched a child, so any `python main.py` at all is somebody else's.
if pgrep -f "python main.py" >/dev/null 2>&1; then
  say "a main.py is already running (PID $(pgrep -f 'python main.py' | tr '\n' ' ')) -- refusing to start a second runner."
  say "two runners race on the same Submission and put four model calls in one window."
  exit 1
fi

LOCK="${LOG_DIR}/supervise.lock"
if ! mkdir "${LOCK}" 2>/dev/null; then
  holder=$(cat "${LOCK}/pid" 2>/dev/null || echo "")
  if [ -n "${holder}" ] && kill -0 "${holder}" 2>/dev/null; then
    say "already running as PID ${holder} -- refusing to start a second runner."
    say "two runners race on the same Submission and put four model calls in one window."
    say "to take over: kill ${holder} (its supervisor will exit too), then rerun."
    exit 1
  fi
  say "clearing a stale lock (PID '${holder}' is not running)."
  rm -rf "${LOCK}" && mkdir "${LOCK}" || { say "could not take the lock -- aborting."; exit 1; }
fi
echo "$$" > "${LOCK}/pid"

release() { rm -rf "${LOCK}"; }
trap 'release; say "stopped by signal -- not restarting."; exit 0' INT TERM
trap 'release' EXIT

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
