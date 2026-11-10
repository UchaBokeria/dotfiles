# Working understanding of the owner's taste and engineering preferences

Evidence-backed development guide from the bounded 2026-11-08 audit. This is not a replacement for current user instructions or project-specific rules. See `history-intent.md` for direct quotations and exact archive locators; `desktop.md`, `infrastructure.md`, `machine.md`, and `whatsapp.md` connect preferences to source and runtime.

## What ties the projects together

The rice is an operational environment, not just matching configuration files. It combines visual materials, keyboard navigation, task/session continuity, local/remote access, reproducible installation, and recovery. The recurring standard is whether a complete workflow works on the actual host after restart, not whether a screenshot or a unit-test count looks convincing. The owner repeatedly asks for depth, concrete causes, omission review and preservation of accumulated sessions/configs.

The visual direction started with a glass widget the owner liked, then a direct request to carry that feel across the whole rice (Claude global history line 2775, 2026-08-24). Later requests refine the translation into each app: Waybar capsules, tmux segments/dots, consistent spacing and icon balance, rounded message bubbles and discoverable modal interaction. This is a trajectory of decisions; every old variant in the repo is not a current preference.

## Visual decisions to preserve

- Use translucent surfaces with depth, subdued tint, clean inset rims and controlled shadow. Keep text and useful marks legible; do not make foreground opacity follow background alpha. Panel text should remain stable rather than swimming through strong distortion.
- Keep colour expressive but restrained in functional chrome. Wallpaper can provide a vivid scene; semantic warning/error/success roles must keep their meaning when the palette changes. The asset catalogue includes neon rainy cities/anime, quiet scenery and Arch variants; inclusion alone does not prove that every asset is an active favourite.
- Treat spacing, shape, font, hit target and alignment as one design problem. A nominally rounded element can still look wrong if its glyph is off-centre, its square outer backdrop shows, or its padding breaks the neighbouring capsule rhythm.
- Use compact information density with clear hierarchy. Icons can save room, but unlabeled controls, crowded actions and small awkward close targets have repeatedly prompted corrections. Discoverability belongs in which-key/shortcut hints and useful drill-ins rather than permanently crowding the primary surface.
- Use centralized tokens and generators for shared material/colour. The current 22/18/12/8/pill geometry is a foundation, not a rule that forbids documented component-specific geometry (for example notification capsule construction or terminal cell halves).
- Preserve keyboard-first operation and purposeful mouse support. Vim directions, familiar Neovim timing/register behavior, named actions, selection/bulk actions, and context menus should agree about the selected object and scope.
- Verify visuals with the actual rendered interface. String checks, hashes and screenshots of unrelated variants do not prove usable spacing, clipped corners, keyboard focus, scroll behavior, text selection or live hit targets.

## Engineering decisions to preserve

- Keep one source of truth where possible: palette derivation feeds per-tool emitters, while Eww mostly renders explicit state produced by adapters. Reuse a real capability through a narrow contract rather than copying half of its behavior into another click handler.
- Preserve explicit source/config/state/cache separation. Source-owned symlinks, user-owned settings, generated outputs, credentials and runtime state have different ownership and rollback rules. An atomic rename protects against partial writes; it does not by itself protect concurrent writers or already-dirty user work.
- Make failures visible and useful. Keep editor notifications available during diagnosis, distinguish a failed probe from a healthy empty result, and report the concrete missing capability. An unsupported WhatsApp feature should say so rather than silently pretend success.
- Make persistence observable: preserve ordering, selections and relevant choices, recover after reconnect, and provide a useful status path. Enabled units and intended retry policies are configuration evidence; restart/reboot acceptance needs its own observation.
- Respect ownership and reversibility. Preserve dirty worktrees and encrypted/device state; isolate changes when histories diverge. A Git commit is useful only if it actually captures the changes being promised as reversible. Scope recovery to the component and evidence involved.
- Keep the desktop usable during automation. Resource caps, serialized heavy builds, bounded polling, debouncing, detached Eww handlers, quiet/DND behavior and spam limits express product requirements. An agent's verification must not unexpectedly open windows or mutate another session's tools.
- Reproduce the whole setup in the installer. The owner explicitly wanted fresh-Arch/VM validation, host/user/key choices, backups and undo. Simulating a happy-path command list is weaker than this intent, and dry-run/status commands need their own side-effect review.
- Prefer verified integration over a broad but incomplete feature claim. Local/source checks, controlled pure-function probes, actual desktop rendering, remote-host deployment and physical-device acceptance are different evidence layers.

## Permission intent is contextual

Full-session archaeology found an explicit correction: an October7 request to configure permissions "to yourself" was mistakenly applied to OpenCode. The owner clarified that they meant the current agent, and that session restored OpenCode's prior deny rules. Do not explain a permissive current OpenCode configuration as acceptance of that mistaken change, or generalize today's hands-off analysis authorization into permanent provider/tool policy. Direct correction outweighs an assistant's earlier success summary; history-intent.md records the exact turn evidence.

## Historical preferences with scope

The owner said not to test brightness in August and said Waybar was perfect in September; neither is a reason to skip read-only analysis. They are reasons to avoid casually changing those parts. October's autonomous bug hunt was explicitly stopped after tests opened Downloads; today's explicit request authorizes a new analysis with parallel agents, not a resumption of old repair commands. Current readb instructions supersede the legacy raw-ADB/VPN recipes.

The terminal-browser work mentioned during this audit is owned by another active session. Treat its files and behavior as concurrent development. Do not stabilize, replace or reject it based on a stale inventory or partially observed implementation.

## How to apply this guide in future work

Start from the specific owner goal and the active implementation path. Locate the applicable historical decision, inspect the current source and installed/live state, then change the smallest coherent workflow that fulfills the goal. Check omissions against the request, verify at the right evidence layer, and state any remaining acceptance gap. Do not generalize an agent's suggestion, a dormant variant, or an old successful test into a permanent owner preference.

Treat this guide as revisable when new owner instructions or stronger evidence arrive. The audit concluded under the owner’s revised bounded scope; it does not claim exhaustive upstream convergence.

## What the deeper session evidence changes

The owner’s requests repeatedly describe complete loops: see what is happening, take the right action, preserve the result, and return later without rebuilding context. This connects a notification's action/close controls, a vim register, mobile session continuity, sync reconnect, and a release rollback. The interface should make the actual state and action scope visible. A green connection badge, HTTP204, enabled timer, installed APK, successful build or polished screenshot is one stage of that loop; future development should verify what happens after it. See [mobile/browser chronology](opencode-desktop-session.md), [ArchPilot chronology](archpilot-session-chronology.md), and [machine helpers](machine-helpers.md).

Autonomy means reducing the owner’s coordination burden while respecting the owner’s working desktop. Historical failed tests explain why this matters: a shim that falls through to a real desktop action defeats the purpose of a quiet verification run. Likewise an old failure should not become permanent folklore: a later screenshot positively showing hover controls supersedes an earlier failed-pointer test, and a packet capture receiving a handshake refutes a blanket assertion that packets never arrive. Keep the exact failure boundary and the evidence that could change it. This is a practical extension of the owner's explicit demand for concrete causes, not a preference inferred from an agent's confidence.

The architecture deliberately uses different ownership models. Dotfiles link directly into live configuration; palette generators produce application-specific outputs; Sonata deploys committed releases through a switchable symlink; remote agent work may continue on another host; local application stores retain user state. Unifying their appearance or launch commands does not justify unifying their deployment, state storage, billing, or recovery policy. Preserve those contracts while making their status understandable. The API standby files, for example, belong to one Quickshard thread and do not authorize a global automatic provider fallback.

The phone and browser research is useful evidence of explored possibilities, not a shopping list the owner approved. Several upstream products offer their own coordinator, push distributor, hosted backend or account memory. Carrying over a useful interaction does not imply adopting that infrastructure. The selected local Android plan, explicit later corrections and actual current source have stronger authority than a third-party README or a library search snippet. Blue/purple extension prototypes and marketplace icons are scoped artifacts; they do not displace the wallpaper-driven desktop material system.

Stored app preferences also qualify generalizations: the deployed Code cache identifies a normal dark editor, Cursor selects high contrast, btop retains its own background, RustDesk trades visual quality for remote usability, while Thunar uses a detailed view and restored tabs. These observations support adapting coherence to the task; only direct owner statements establish why an individual stored setting was chosen. See [machine configuration continuation](machine-config-root.md).

## Deterministic controls and contextual consultation

The Spark parent session explicitly asks to remove an entire account, its models and its key; integrate OpenCode theme generation with wallpaper changes; build the patch locally; and avoid automatic commits (displays149/192). Later corrections require `/remove-account` to open a quiet native picker and confirmation directly, without asking a model to obey an instructional stub (488/580/706). Image707 shows that unwanted instruction becoming chat. A configured command or successful compile does not fulfill a visible interaction requirement when the owner still sees the prompt. Establish whether the full TUI or a separate mini/run surface owns the interaction before patching it. See [Spark history](spark-theme-session.md).

The DCP/statusbar history starts with a tmux bar, static Vim state and progressive collapse, then later explicitly authorizes a fork patch. The change in authorization is an evolution, not a contradiction. Compact indicators should communicate real phone, browser, tool, goal, agent and cost state without making narrow splits ugly. The owner also says not to overdo Wallust. This supports restraint and useful density. Requests for consultation on these choices coexist with hands-off execution elsewhere; agent-written “never ask” memories overgeneralize the actual instructions. See [history and intent](history-intent.md), H049.

RemoteADB displays206/218 explicitly request propagating knowledge to both hosts, global agents and Hermes. File writes, finished notification jobs, delivered receipts, live agent reload and actual understanding are separate outcomes. Preserve later successful pairing/reachability evidence alongside earlier failures. Superseded transport explanations must not become current constraints; current readb-only instructions govern operations.

## A coordinator should reduce coordination work without erasing boundaries

The installed Hermes setup brief asks for Blackwall as an always-on main agent with a paired Arch instance, persistent organization of topics/tasks/research, existing authenticated Chrome access, phone voice interaction and communication with the other coding agents. Its breadth explains the interest in a single operational environment. The same owner brief explicitly asks for questions, checklists and cross-checking, so autonomous execution must still surface missing capabilities and material choices.

Later turns narrow the grant: Cloudflare rather than Tailscale for infrastructure; reuse the existing Telegram bot while retiring the old Claude connection; read one WhatsApp colleague and send drafts to the owner, never directly to that colleague. The owner still wants to try Relay. An agent's “accepted implicitly” summary does not override that request. These are dated historical constraints, to check against current task-specific instructions, not authorization for this audit to send messages or change infrastructure. See [Hermes setup history](hermes-infra.md), owner displays106/123/396/447.

The setup history also shows why configuration echoes are insufficient. Stored unrestricted computer-use mode maps to standard unless the actual session bypass is active; voice module discovery is not a phone conversation; matching SOUL instructions are not cross-host replication; a ready card with “parked” in its title is still dispatchable. Future work should name the effective enforcement and persistence mechanism, then verify the requested interaction at its actual boundary.

The later Oct7 coordinator session explicitly revises transport scope: the owner first answers “use wireguard” to an external-watchdog proposal, then clarifies “PC↔Blackwall through WireGuard too” (original archive01a116cf-f6c4-7361-9891-935e9b2d3479, lines7337/7378). This supersedes an interpretation that earlier Cloudflare preference permanently excluded WireGuard for host transport. It does not establish that an independent external watchdog was placed or tested, and it does not revive the retired mobile Android route. Preserve the scoped change and current readb instructions together.

The same later primary conversation explicitly stages worker choice: ask first, collect examples, make suggestions configurable, and consider autonomy after months of evidence. Claude Code and Codex stay on subscriptions; Spark/OpenCode problems ask the owner rather than silently falling back. Hands-off administration and autonomous analysis are not permission to change worker billing or dispatch policy. Current direct task instructions still determine the scope of any new work.
