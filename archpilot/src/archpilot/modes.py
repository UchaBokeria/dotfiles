"""Ask vs Action, expressed as CLI flags rather than prompt text.

The distinction is enforced by the engine, not by asking the model nicely:
  ask    - `--permission-mode plan` makes writing structurally impossible
  action - `--permission-mode acceptEdits` plus the PreToolUse approval gate

Flags here were validated against Claude Code 2.1.237; see docs/hook-contract.md
for the ones that bit (notably `--mcp-config '{}'` being invalid).
"""

from __future__ import annotations

from pathlib import Path

ASK = "ask"
ACTION = "action"
MODES = (ASK, ACTION)

#: Cycle orders for the clickable status-bar chips.
MODEL_CYCLE = ("haiku", "sonnet", "opus")
#: Reasoning effort. Lower is cheaper and faster; on a subscription that is
#: rate-limit budget, so this is worth having one click away.
EFFORT_CYCLE = ("low", "medium", "high", "xhigh", "max")


CLAUDE = "claude"
CODEX = "codex"
#: Cycle order for the engine chip and ctrl+alt+tab.
ENGINE_CYCLE = (CLAUDE, CODEX)

#: Codex has no PreToolUse hook to route through, so on that engine the sandbox
#: IS the mode: ask cannot write anywhere, action can write only inside the
#: session's working directory. Nothing ever passes
#: --dangerously-bypass-approvals-and-sandbox.
CODEX_SANDBOX = {"ask": "read-only", "action": "workspace-write"}

#: Reasoning levels every current Codex model accepts, for when the model
#: catalogue does not say. `max` clamps to the strongest of these.
CODEX_EFFORTS = ("low", "medium", "high", "xhigh")


def cycle(values: tuple[str, ...], current: str) -> str:
    """Next value after `current`, wrapping. Unknown values restart the cycle."""
    try:
        return values[(values.index(current) + 1) % len(values)]
    except ValueError:
        return values[0]

#: Every ~20 configured MCP servers would otherwise load their tool schemas
#: into every single turn. On a subscription that is pure rate-limit waste, so
#: none load by default. The empty value MUST carry the mcpServers key -
#: '{}' is rejected outright.
#: Naming servers in config `[mcp] servers` opts those back in - that is how
#: you would enable e.g. the chrome or telegram integrations here.
_NO_MCP = ("--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}')


def mcp_args(servers: tuple[str, ...] = ()) -> list[str]:
    if not servers:
        return list(_NO_MCP)
    # Load the user's real MCP config but keep only the named servers.
    import json as _json
    from pathlib import Path as _Path
    try:
        raw = _json.loads((_Path.home() / ".claude.json").read_text())
        available = raw.get("mcpServers") or {}
    except (OSError, ValueError):
        available = {}
    chosen = {name: available[name] for name in servers if name in available}
    return ["--strict-mcp-config", "--mcp-config", _json.dumps({"mcpServers": chosen})]

#: Suppress user/project/local settings so the daemon's --settings file is the
#: only source of hooks. Prevents the user's own hooks firing on our turns.
_ISOLATED_SETTINGS = ("--setting-sources", "")

SYSTEM_PROMPT_SUFFIX = """
You are ArchPilot, a system-wide assistant embedded in an Arch Linux / Hyprland
desktop. Answers are rendered in a small on-screen widget, so be brief and
concrete. Prefer a direct answer over a preamble.

When your answer implies a concrete, safe command the user would plausibly want
to run right now, emit it as a fenced block tagged archpilot-action containing
only that command. Emit at most one such block, and never emit one for purely
informational answers (weather, definitions, explanations, status questions).

Always write at least one sentence of prose alongside it. Never reply with an
action block as the entire answer - the block is rendered as a button, so a
reply containing only a block shows the user a button with no explanation.

Never mention your own modes, tools, permissions or planning workflow. The user
sees a chat window, not a coding agent - "this is not a planning task" or "I
cannot edit files in this mode" is noise to them. Answer, or say plainly what
you would need in order to.
""".strip()


def system_prompt(machine: str = "") -> str:
    """The standing instructions, as both engines receive them."""
    return f"{machine}\n\n{SYSTEM_PROMPT_SUFFIX}" if machine else SYSTEM_PROMPT_SUFFIX


def build_argv(
    *,
    mode: str,
    session_id: str,
    model: str,
    settings_file: Path,
    resume: bool = False,
    effort: str | None = None,
    machine: str = "",
    mcp_servers: tuple[str, ...] = (),
) -> list[str]:
    """Assemble the `claude` argv for one session."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")

    argv = ["claude", "-p", "--model", model]

    # --session-id sets a NEW session's id (this is what makes the conversation
    # resumable from a terminal); --resume reattaches to an existing one.
    argv += ["--resume", session_id] if resume else ["--session-id", session_id]

    prompt = system_prompt(machine)

    # NOTE: --disable-slash-commands is deliberately absent. Without it
    # `/compact`, `/clear` and any installed skill or plugin command work from
    # this window exactly as they do in a terminal session.
    argv += [
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--verbose",
        "--append-system-prompt", prompt,
        "--settings", str(settings_file),
    ]
    if effort:
        if effort not in EFFORT_CYCLE:
            raise ValueError(f"unknown effort {effort!r}")
        argv += ["--effort", effort]

    argv += [*_ISOLATED_SETTINGS, *mcp_args(mcp_servers)]

    if mode == ASK:
        # Not `plan`: its system prompt made every answer begin "this is not a
        # planning task". The write tools are removed outright instead, so ask
        # still cannot modify anything, and the PreToolUse hook refuses any
        # mutating Bash rather than prompting for it.
        argv += ["--permission-mode", "manual"]
        argv += ["--disallowedTools", "Write", "Edit", "NotebookEdit"]
    else:
        argv += ["--permission-mode", "acceptEdits"]

    return argv


def codex_effort(effort: str, supported: tuple[str, ...] = ()) -> str:
    """The strongest level the model offers that does not exceed `effort`.

    ArchPilot's scale ends at `max`; not every Codex model goes that far
    (gpt-5.5 stops at xhigh), and an unsupported value fails the turn.
    """
    levels = tuple(supported) or CODEX_EFFORTS
    if effort in levels:
        return effort
    if effort not in EFFORT_CYCLE:
        raise ValueError(f"unknown effort {effort!r}")
    for candidate in reversed(EFFORT_CYCLE[: EFFORT_CYCLE.index(effort) + 1]):
        if candidate in levels:
            return candidate
    return levels[0]


def codex_argv(
    *,
    mode: str,
    cwd: Path,
    model: str = "",
    effort: str | None = None,
    thread_id: str = "",
    binary: str = "codex",
    supported: tuple[str, ...] = (),
) -> list[str]:
    """Assemble one turn's `codex exec` argv. The prompt arrives on stdin ("-")."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    sandbox = CODEX_SANDBOX[mode]

    argv = [binary, "exec"]
    if thread_id:
        # `exec resume` accepts neither --sandbox nor -C (codex-cli 0.154), so
        # the sandbox travels as a config override and the directory is the
        # process's own cwd.
        argv += ["resume", "-c", f'sandbox_mode="{sandbox}"']
    else:
        argv += ["--sandbox", sandbox, "-C", str(cwd)]
    argv += ["--json", "--skip-git-repo-check"]
    if model and model != "default":
        argv += ["-m", model]
    if effort:
        argv += ["-c", f'model_reasoning_effort="{codex_effort(effort, supported)}"']
    if thread_id:
        argv.append(thread_id)
    argv.append("-")
    return argv
