#!/bin/bash
# Job control gives the background harness its own process group, so the
# watchdog can kill the whole tree. A harness is typically a shell running
# a Node CLI that spawns further children; killing only direct children
# leaves those grandchildren running.
set -m
WRAPPER_PID=$$
bash '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/d3c6d52afa40/harness.sh' &
HARNESS_PID=$!

(
  END=$((SECONDS + 1800))
  while [ $SECONDS -lt $END ]; do
    if ! kill -0 $WRAPPER_PID 2>/dev/null; then
      if kill -0 $HARNESS_PID 2>/dev/null; then
        kill -TERM -$HARNESS_PID 2>/dev/null || kill -TERM $HARNESS_PID 2>/dev/null
        sleep 5
        kill -KILL -$HARNESS_PID 2>/dev/null || kill -KILL $HARNESS_PID 2>/dev/null
      fi
      exit 0
    fi
    sleep 1
  done
  if kill -0 $HARNESS_PID 2>/dev/null; then
    echo 'sonata: run timeout after 1800s' >> '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/d3c6d52afa40/harness.log'
    echo timeout > '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/d3c6d52afa40/timeout'
    pkill -P $HARNESS_PID 2>/dev/null
    kill -TERM -$HARNESS_PID 2>/dev/null || kill -TERM $HARNESS_PID 2>/dev/null
    sleep 5
    kill -KILL -$HARNESS_PID 2>/dev/null || kill -KILL $HARNESS_PID 2>/dev/null
  fi
) 2>/dev/null &
WATCHDOG_PID=$!
# Job control reports a killed background job to the terminal. On a normal
# run the watchdog is always killed, so without this every completed run
# ended with a "Terminated: 15" line in the pane — which then became the
# tail of any degraded report. Disowning it silences the report only; the
# watchdog still runs, and still kills the tree if it fires.
disown $WATCHDOG_PID 2>/dev/null

# `set -m` above put the harness in its own process group, which means it is
# NOT the terminal's foreground group. Any harness that reads the terminal —
# every interactive TUI, which is how sonata honours `default` mode — then
# takes SIGTTIN and stops dead. Reproduced with a one-line harness that reads
# a single key: the pane freezes and the process sits in state T forever,
# until the run timeout kills something that never started.
#
# `fg` hands the terminal to that process group and waits for it exactly as
# `wait` did, returning the same status.
#
# Its output is deliberately NOT redirected. `fg %1 >/dev/null 2>&1` runs and
# reports success, but the job stays stopped — the handover simply does not
# happen. Reproduced both ways against the same wrapper. The cost is one
# extra pane line, the job command that fg echoes.
#
# With no terminal there is nothing to hand over and no job control to do it
# with, so fall back to the plain wait.
# Non-interactive harness: skip fg, use wait. fg interferes with
# output redirection in some harnesses (claude -p hangs under fg).
wait $HARNESS_PID
STATUS=$?

pkill -P $WATCHDOG_PID 2>/dev/null
kill $WATCHDOG_PID 2>/dev/null
wait $WATCHDOG_PID 2>/dev/null

if [ ! -f '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/d3c6d52afa40/exit' ]; then
  echo $STATUS > '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/d3c6d52afa40/exit'
fi

exit $STATUS
