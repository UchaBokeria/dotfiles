# How wacli sends while a sync process holds the store lock

Recorded 2026-09-08 against wacli 0.18.1, before any of wa was written. The
design assumed sends are delegated to a running `sync --follow`; this is the
evidence for how that actually behaves.

## The store lock is exclusive, and almost everything takes it

`wacli sync --follow` holds the lock for its whole life. So does `wacli doctor`,
briefly — which is how the first probe failed: a one-second `doctor` poll loop
kept stealing the lock, and the sync process gave up trying to acquire it.

**Do not poll `wacli doctor` while a sync process is starting.**

Reads are the exception. `wacli chats list --json` returns in 25 ms while sync
holds the lock, because `wacli.db` is in WAL mode.

## Sends are delegated over a Unix socket

While `sync --follow` runs, the store directory gains:

    .send.sock      Unix socket - the delegation channel
    .last-send-at   pacing state for --send-spacing
    HEARTBEAT       sync liveness

`send text` connects to `.send.sock` and hands the message to the sync process.
The socket disappears when sync stops.

## Timings

    connected at 2278ms, .send.sock at 3408ms

    plain send 1: 2892ms  ok
    plain send 2: 2644ms  ok
    plain send 3: 2747ms  ok

## --lock-wait makes it worse, not better

    --lock-wait 1s   : FAILED after 1010ms
    --lock-wait 3s   : ok after  6216ms
    --lock-wait 10s  : ok after 12870ms
    --lock-wait 60s  : ok after 62897ms
    no --lock-wait   : ok after  2866ms

A send given `--lock-wait` spends the entire duration failing to acquire the
lock and only then falls back to the socket. The wait is pure added latency.

## What wa does with this

1. Never pass `--lock-wait` on a send.
2. Treat `.send.sock` as the readiness signal after spawning sync, not the
   `connected` event — the socket appears about a second later, and a send
   issued in that gap fails with "store is locked".
3. Never call `wacli doctor` while sync is starting.
4. Budget about 2.7 s for a send. That is far too slow to block the interface
   on, which is why the composer draws an optimistic bubble immediately and
   reconciles it when the real message id comes back.
