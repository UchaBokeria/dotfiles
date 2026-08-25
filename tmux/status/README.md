# tmux status variants

Each file here sets `status-left`, `status-right`, `window-status-format` and
`window-status-current-format` directly, rather than going through oh-my-tmux's
`tmux_conf_theme_*` variables.

That is deliberate. oh-my-tmux expands those variables with a *shell* while
reading `tmux.conf.local`, so they only exist during that one pass - a separate
file cannot use them. Setting the tmux options directly avoids the problem
entirely, and the colours come from `@bw_*` user options (written into the
generated block in `tmux.conf.local`), which live in the tmux server and
resolve inside `#[fg=...]` at render time.

The active variant is a symlink, `status/active.conf`, sourced a beat after
oh-my-tmux applies its own theme - it has to be after, or it would be
overwritten. Switch with `tmux/variant <name>`.
