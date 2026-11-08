# Warm workspace picker

`Ctrl+A s` uses a preloaded helper for the current tmux server. A small native
transport passes the popup terminal descriptor to a forked picker worker; it
avoids starting another Python interpreter for each opening. The helper does
not attach a tmux client or create a session, window or pane.

The workspace JSON and tmux server remain authoritative. The helper holds one
read-only metadata snapshot, never a second workspace database. Backend changes
invalidate it; a snapshot older than 350 ms is refreshed before an opening. The
current session/window/pane is checked live, and normal picker refreshes continue
after opening. Destructive actions retain their existing live validation and
confirmation checks.

## Bounds

- Shared cache: one snapshot, at most 1,024 pane rows or 2 MiB of serialized
  metadata. Larger servers bypass caching and still display the complete list.
- Popup preview cache: at most eight panes / 100,000 display cells. Oversized
  previews render without being retained. Preview contents are never cached by
  the parent or written to disk.
- At most four helper UI workers. Additional requests use the regular picker.
- Idle metadata refresh is every two seconds; recent use refreshes every 300 ms.
  No event history or accumulating session-name cache is kept.
- Private runtime directory: `/tmp/tmux-picker-UID`, mode 0700; sockets are 0600.
  One atomically replaced executable, a small checksum file and two lock files
  are retained. Active servers have one socket each; dead sockets are cleaned.
  There is no disk metadata/preview cache or helper log.

The 2 MiB limit describes metadata input, not the Python interpreter's total RSS.
The lifecycle test also checks resident memory, file descriptors and repeated
open/close behavior. Each popup's process releases its caches when it exits.

## Failure and lifecycle

If the helper is unavailable, busy or cannot be built, the existing Python
picker remains available. An unavailable helper is warmed again automatically.
A crash after a popup has started closes that popup instead of replaying an
action. Signals use Linux pidfds, and worker parent-death handling prevents
orphan pickers. Shell panes and tmux itself are never stopped by this service.

`workspaces.py init` compiles the transport using the installed `cc` when needed,
warms the helper and installs the binding. Reinitialization replaces outdated
helpers gracefully: existing popups finish before their old parent exits. The
helper exits when its tmux server ends, and a server restart starts a new cache
generation. Nothing from the cache is restored or saved by Resurrect/Continuum.

For diagnostics, run `scripts/picker_service.py status` inside the relevant tmux
server. `scripts/picker_service.py retire` drains the helper; the next opening
can rewarm it. To install the regular binding instead, run
`TMUX_PICKER_SERVICE=0 scripts/workspaces.py init`; this lasts until the next
initialization without that environment setting. Native layout also retires the
helper. Runtime files need no manual maintenance; do not delete the executable
while live bindings reference it.

`tests/picker_service.py` tests bounded caches, repeated openings, malformed
requests, crashed workers/transports/helpers, unresponsive helpers, graceful
replacement, compiler failure, cache corruption, same-path server restart and
SSH initialization without `TMUX`. All fixtures use disposable servers.
`tests/picker_speed.py` measures first complete frame latency across seven opens.
