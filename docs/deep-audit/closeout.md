# Development handover — 2026-11-08

## Scope and stopping decision

At 16:35 +04 the owner removed the three-consecutive-zero-findings condition and requested that material gaps be filled and the audit concluded so development can resume. This handover closes the audit under that revised scope. It does not claim exhaustive knowledge of every installed upstream dependency, every historical commit, every image frame or every unavailable session tail. Older cycle counters and pending checklists are historical progress records, not an instruction to keep the audit running.

## The environment we are building

This is a coherent working environment rather than a collection of matching themes. Hyprland, panels, notifications, launchers, terminal tools and remote agents support one continuing workflow: understand state, perform an action, preserve its result and return without rebuilding context. Visual consistency matters together with keyboard operation, task continuity, predictable state and recoverability.

The current architecture has several distinct ownership paths:

- Dotfile source links feed live desktop configuration; wallpaper/palette generation emits consumer-specific themes.
- Eww renders adapter state; Waybar and SwayNC have their own IPC and process lifecycles. Enabled-unit state alone does not describe the running desktop.
- Shell, tmux, terminal graphics and editor behavior depend on the actual terminal/client and foreground process, not merely the helper command.
- Sonata uses committed releases and a serving-release boundary. Installed Nous Hermes, the cloud Hermes project and Omnigent are separate systems with separate state and authority.
- cloudsync, downloadsync and lazyrsync have different scopes and should retain their distinct roles.
- Current readb rules govern Android/Quest. Historical mobile transport recipes are not current operating instructions.

See [architecture map](architecture-map.md), [machine](machine.md), [desktop](desktop.md), [infrastructure](infrastructure.md), and [machine helpers](machine-helpers.md).

## What to preserve in design

The strongest recurring visual direction is translucent material with depth, restrained tint, clean inset rims and controlled shadow. Text should remain legible and stable. Rounded geometry, spacing, icon balance, typography and hit targets need to work together; merely adding blur or border radius does not satisfy that taste.

Prefer compact hierarchy and useful density, with details available through hints, drill-ins and context actions. Keep keyboard-first operation coherent with mouse selection and action scope. Reuse semantic palette roles and shared generators while adapting them to each application. Do not flatten every app into an identical surface or treat all historical assets as current favorites. Verify changes in the actual rendered interface.

The fuller evidence and scoped historical corrections are in [taste and development](taste-and-development.md), [history and intent](history-intent.md), and [desktop chronology](opencode-desktop-session.md).

## What to preserve in engineering

Use a clear source of truth and narrow contracts. Keep source, generated outputs, user settings, credentials, cache, installed artifacts and running processes separately identifiable. Preserve dirty worktrees, encrypted state and existing workflows. Atomic replacement does not solve concurrent writers; a started process does not establish readiness; a timeout does not establish worker termination.

Autonomy should reduce coordination burden while keeping the desktop usable. Resource controls, quiet verification, bounded work, reconnect persistence and actionable status matter. Read-only inspection should be assessed by its actual effects: names such as doctor, status, preview, skill view and dry run do not guarantee inert behavior.

Evidence should follow the requested workflow to its real boundary. Source inspection, isolated synthetic tests, installed artifact identity, live rendering, remote deployment, restart persistence and physical-device acceptance establish different claims. Existing reports preserve those distinctions.

Owner-directed analysis is not permanent permission to change provider billing or dispatch policy. Historical worker instructions favor Claude Code/Codex subscriptions, scoped tool-and-host choices and asking on provider problems rather than silent paid fallback. Upstream defaults and assistant-written memories do not override direct later owner corrections.

## Material implementation boundaries to check when building

These are development constraints, not an instruction to repair everything before starting useful work:

1. **UI success and cancellation need backend evidence.** Hermes source contains cases where a status badge, action return, checkpoint message or diagnostic exit is weaker than the claimed result. Worker cancellation and timeout can leave work alive. When changing one of these paths, verify its actual terminal result and state ownership.
2. **Credentials and profile isolation require end-to-end tracing.** Review found ambient-environment fallback, nontransactional credential/config writes and a local-language-server environment overlay that can undo credential scrubbing. Scope any future fix to the actual reachable caller; do not infer that an owner's secret was exposed from source alone.
3. **Session identity must survive reconnect and asynchronous callbacks.** Concrete isolated proofs cover voice admission retargeting and several UI/backend races. A live PTY or connection does not guarantee the current page is receiving the right channel or selected model.
4. **Installed and source versions can differ.** SDDM selection, Spark theme provenance, WhatsApp build identity, serving Sonata release and the concurrently added terminal browser all need their own deployment check before modifying behavior.
5. **Authentication redirect handling has a specific source-level gap.** The Hermes password-login next-path check accepts a slash/backslash form that browser URL parsing can interpret as another origin. The isolated proof used synthetic hosts and no login or browser navigation. Any future repair must verify the real route and deployment prefix rather than extrapolate to token exposure.

Detailed source locations, qualifications and reproductions live in [CLI findings](hermes-cli-root.md), [core findings](hermes-runtime-infra.md), [desktop/gateway findings](hermes-runtime-desktop.md), [Omnigent](omnigent-runtime.md), and the component reports. Findings are not all owner-visible current failures and were not repaired during this audit.

## Coverage and remaining limits

The original dotfiles, submodule/source/history, session archaeology and machine survey have extensive per-path and per-record coverage records. Coverage classifications distinguish semantic reads from exact references, generated files, parsed assets, opaque credential material and unavailable historical data. Overlapping ledgers must not be summed as unique files.

The intentionally unfinished expansion is chiefly the large installed Nous Hermes upstream tree and its remote history. Root CLI coverage at closeout is 169 full reads (4,045,412 raw bytes), one partial file and 503 pending frozen paths; all 170 touched paths passed a fresh hash comparison. Core infrastructure closed 532/790 assigned paths (501 literal full reads, 26 exact semantic references, two generated and three asset classifications), leaving 258 unread; fresh hashes/sizes had zero drift. Desktop/gateway closed 311 full source reads and 11 asset inspections in its 1,058-path partition, with four partial and 732 unread. These are disjoint assigned partitions within the broader upstream tree, not whole-installation closure. See [core closeout](hermes-runtime-infra-closeout.json) and [desktop closeout](desktop-audit-closeout.md). Nous documentation/history closed 287 positive full-source or explicit reference/baseline-delta paths of its 2,026-path partition; 1,724 text paths, 13 assets and two externally owned rows remain pending. Its Git semantic review covers 12 commit messages and 40 scoped documentation patches. The Nous Git graph was inventoried structurally; its roughly 60,000 commits were not all semantically read. This limit does not invalidate the separately reviewed dotfiles Git histories.

Additional limits include shallow/unavailable upstream predecessors, missing original transcript tails, encrypted reasoning and deliberately opaque secret values. Representative asset rendering is not every glyph/frame. No reboot, service restart, installation, provider request, phone operation or broad application test was performed to obtain acceptance. Live observations are dated audit snapshots, not a perpetual health guarantee.

## Starting the next feature

Begin with the requested workflow and its existing active path. Read the linked component report and current source, identify the state owner and serving artifact, then implement the smallest coherent change. Preserve the shared visual language and existing operational boundaries. Verify the changed interaction at the relevant evidence layer and state any remaining acceptance gap. The audit is a reusable reference, not a prerequisite to repeating an exhaustive investigation before every edit.
