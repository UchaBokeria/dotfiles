# Version-bound primary-source cross-checks

## Animation units

Live process2870 maps libhyprutils.so.0.14.2; pacman also reports0.14.2-1. The [matching source](https://raw.githubusercontent.com/hyprwm/hyprutils/v0.14.2/src/animation/AnimatedVariable.cpp) at getPercent derives progress from elapsed milliseconds divided by100 and internalSpeed. For ordinary Bezier animations, speed7 therefore has a nominal700ms span. Springs use a different completion path. [Hyprland0.56.2](https://raw.githubusercontent.com/hyprwm/Hyprland/v0.56.2/src/animation/AnimationManager.cpp) consumes getCurveStep. No stopwatch or motion acceptance was performed. Current wiki HEAD can describe newer behavior; pinned dependency source resolves this installed-version question.

## Notification quiet semantics

Installed swaync is0.12.6-1. In the [matching upstream notiDaemon](https://raw.githubusercontent.com/ErikReider/SwayNotificationCenter/v0.12.6/src/notiDaemon/notiDaemon.vala), DND is bound to gsettings in construction. Notification visibility is checked before popup admission; critical urgency or the bypass hint skips the DND/inhibitor condition, while a non-enabled visibility state independently prevents the popup. This corroborates the custom quiet rule's reason for existing. It does not reproduce crash, restart or notification behavior on today's desktop. Source only, no notifications sent.

Other primary/API checks are linked near their findings in machine.md and whatsapp.md (Lua startup, tmux clipboard external mode, Kitty remote graphics, Go premultiplied RGBA). Fetch attempts using old repository paths returned404; GitHub tree discovery resolved the actual paths above. No missing source was replaced with an assumption.


## Eww poll scheduling, checked at audit resumption

Installed package eww0.6.0-1. [Matching upstream poll handler](https://raw.githubusercontent.com/elkowar/eww/v0.6.0/crates/eww/src/script_var_handler.rs) lines141–169 prevents duplicate variable handles and calls run_poll_once synchronously within one task before the next interval sleep. Long same-variable polls do not accumulate overlapping launches solely because duration exceeds interval. This contradicts the archived freeze explanation; it does not prove a different root cause.

[Matching command runner](https://raw.githubusercontent.com/elkowar/eww/v0.6.0/crates/eww/src/config/script_var.rs) lines19–44 also executes initial shell values synchronously and waits for subprocess output without a built-in timeout. Slow or blocked commands can therefore occupy threads/delay initial-value callers. Both full small source files were read; installed binary exact build equivalence is unverified.

GNU online manual fetches timed out; no claim is supported by those failed fetches. A read-only local find probe using the historical two -maxdepth/-name branches returns both target files under the explicit starting directory, refuting the claimed implicit-CWD right branch. No filesystem mutation.

## Codex cache accounting

[Official usage semantics](https://developers.openai.com/api/docs/guides/agents-api/observability) describes cached input as included in total input (Understand token usage). [Official Codex noninteractive output](https://learn.chatgpt.com/docs/non-interactive-mode) shows turn.completed with separate flat input_tokens/cached_input_tokens fields. Those docs alone do not prove every historical CLI version; local ArchPilot0.154.0 rollout token_count supplies matching-version arithmetic (codex-cache-accounting-evidence.json). Combined evidence confirms current ArchPilot adapter counts cached input twice when nonzero. No provider call or product change.
