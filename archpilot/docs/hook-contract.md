# PreToolUse hook contract (empirically verified)

Verified against Claude Code **2.1.237** on 2026-08-20 by probe, not from docs.
Probes lived in the session scratchpad; results reproduced below.

## stdin (JSON on the hook's stdin)

```json
{
  "session_id": "c8acd325-077f-4abd-8975-33df39b1afc6",
  "transcript_path": "/home/scriptkid/.claude/projects/<slug>/<uuid>.jsonl",
  "cwd": "/home/scriptkid/.config/.dotfiles/blackwall/archpilot",
  "prompt_id": "ad28fd2a-7aa5-4f4a-9814-012867122719",
  "permission_mode": "acceptEdits",
  "effort": { "level": "high" },
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": { "command": "echo hi", "description": "..." },
  "tool_use_id": "toolu_01XfJHNBurHh74Z25FmXDNDV"
}
```

`session_id` is what lets the hook route an approval request back to the
right ArchPilot session over the daemon socket.

## stdout (to decide)

```json
{"hookSpecificOutput":{
  "hookEventName":"PreToolUse",
  "permissionDecision":"allow"|"deny"|"ask",
  "permissionDecisionReason":"shown to the model"}}
```

## Fail modes — THE IMPORTANT PART

| Hook behavior                          | Command | Safe |
|----------------------------------------|---------|------|
| stdout `permissionDecision: deny`      | blocked | yes  |
| stdout `permissionDecision: allow`     | runs    | yes  |
| blocks 6s then allows                  | runs    | yes  |
| **killed by configured `timeout`**     | **RUNS**| NO   |
| **exit 1 + stderr, empty stdout**      | **RUNS**| NO   |
| exit 2 + stderr                        | blocked | yes  |

Two fail-OPEN paths, and both are the "something broke" paths. Therefore
`hooks/pretooluse.py` MUST:

1. Wrap everything in a top-level `except BaseException` -> stderr + `exit(2)`.
2. Enforce its OWN deadline (`HOOK_DEADLINE_S`, 240s) strictly inside the
   harness `timeout` (600s in settings/action.json), and `exit(2)` on expiry.
   The hook must never be the thing the harness kills.
3. Never `exit(1)`. Never `exit(0)` without valid decision JSON on stdout.

A blocked command is recorded in the run's `permission_denials[]`, and
`permissionDecisionReason` is shown to the model, which then explains the
block to the user instead of retrying.

## Other CLI facts confirmed by the same probes

- `--mcp-config '{}'` is REJECTED: `mcpServers: expected record, received undefined`.
  The correct empty value is `'{"mcpServers":{}}'`.
- `-p` without stdin warns and stalls ~3s. Always redirect `< /dev/null`
  (or keep stdin open deliberately for `--input-format stream-json`).
- `--setting-sources ''` cleanly suppresses user/project/local settings, so the
  daemon's `--settings` file is the only source. Confirmed the ~20 configured
  MCP servers do not load under `--strict-mcp-config`.
- Runs complete with `ANTHROPIC_API_KEY` unset -> OAuth subscription path, as required.
