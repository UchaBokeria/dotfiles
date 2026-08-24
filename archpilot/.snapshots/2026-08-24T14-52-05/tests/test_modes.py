"""Guards on the CLI flags. Several of these encode facts that cost a probe
to discover - see docs/hook-contract.md - so a regression here is expensive.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archpilot.modes import ACTION, ASK, build_argv

SETTINGS = Path("/tmp/archpilot-settings.json")


def argv(mode=ASK, **kw):
    kw.setdefault("session_id", "11111111-2222-3333-4444-555555555555")
    kw.setdefault("model", "opus")
    kw.setdefault("settings_file", SETTINGS)
    return build_argv(mode=mode, **kw)


def test_never_uses_bare_flag():
    """--bare forces ANTHROPIC_API_KEY auth, silently moving us onto billing."""
    assert "--bare" not in argv()


def test_empty_mcp_config_carries_the_mcpServers_key():
    """'{}' is rejected by the CLI: mcpServers expected record, got undefined."""
    args = argv()
    payload = args[args.index("--mcp-config") + 1]
    assert json.loads(payload) == {"mcpServers": {}}
    assert "--strict-mcp-config" in args


def test_ask_mode_cannot_write():
    """The write tools are removed outright, so ask cannot mutate regardless of
    permission mode. `plan` was dropped because its own system prompt made every
    answer open with "this is not a planning task"."""
    args = argv(ASK)
    assert args[args.index("--permission-mode") + 1] != "plan"
    assert "--disallowedTools" in args
    for tool in ("Write", "Edit", "NotebookEdit"):
        assert tool in args


def test_action_mode_accepts_edits_and_has_no_disallow_list():
    args = argv(ACTION)
    assert args[args.index("--permission-mode") + 1] == "acceptEdits"
    assert "--disallowedTools" not in args


def test_new_session_sets_id_and_resume_reattaches():
    new = argv(session_id="abc")
    assert "--session-id" in new and "--resume" not in new

    resumed = argv(session_id="abc", resume=True)
    assert "--resume" in resumed and "--session-id" not in resumed


def test_streaming_flags_present():
    args = argv()
    assert args[args.index("--input-format") + 1] == "stream-json"
    assert args[args.index("--output-format") + 1] == "stream-json"
    assert "--include-partial-messages" in args


def test_settings_are_isolated_from_user_config():
    args = argv()
    assert args[args.index("--setting-sources") + 1] == ""
    assert args[args.index("--settings") + 1] == str(SETTINGS)


def test_action_suggestion_convention_is_in_the_system_prompt():
    args = argv()
    prompt = args[args.index("--append-system-prompt") + 1]
    assert "archpilot-action" in prompt
    assert "never emit one for purely" in prompt.lower()


def test_prompt_forbids_an_answer_that_is_only_a_command():
    """A bare action block renders as a button with no explanation next to it."""
    args = argv()
    prompt = args[args.index("--append-system-prompt") + 1].lower()
    assert "never reply with an" in prompt
    assert "at least one sentence" in prompt


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        argv(mode="yolo")


# --------------------------------------------------------------------------
# Effort and the status-bar cycles.
# --------------------------------------------------------------------------
from archpilot.modes import EFFORT_CYCLE, MODEL_CYCLE, cycle


def test_effort_is_passed_through():
    args = argv(effort="low")
    assert args[args.index("--effort") + 1] == "low"


def test_effort_is_omitted_when_unset():
    assert "--effort" not in argv()


def test_unknown_effort_is_rejected():
    with pytest.raises(ValueError):
        argv(effort="tremendous")


@pytest.mark.parametrize("values", [MODEL_CYCLE, EFFORT_CYCLE])
def test_cycle_wraps(values):
    assert cycle(values, values[-1]) == values[0]
    assert cycle(values, values[0]) == values[1]


def test_cycle_recovers_from_an_unknown_current_value():
    assert cycle(EFFORT_CYCLE, "nonsense") == EFFORT_CYCLE[0]


def test_effort_cycle_is_ordered_cheapest_first():
    """The order is user-facing: clicking the chip should escalate, not jump."""
    assert EFFORT_CYCLE == ("low", "medium", "high", "xhigh", "max")


def test_machine_block_goes_into_the_system_prompt():
    """It rides in the cached prefix, so it is paid for once per session."""
    args = argv(machine="<machine>arch</machine>")
    prompt = args[args.index("--append-system-prompt") + 1]
    assert prompt.startswith("<machine>arch</machine>")
    assert "archpilot-action" in prompt


def test_no_machine_block_leaves_the_prompt_alone():
    prompt = argv()[argv().index("--append-system-prompt") + 1]
    assert not prompt.startswith("<machine>")


def test_model_cycle_starts_at_the_cheap_end():
    """haiku is the default, so cycling should escalate from there."""
    assert MODEL_CYCLE[0] == "haiku"


def test_prompt_forbids_talking_about_its_own_modes():
    """Answers were leaking "this is not a planning task" at the user."""
    prompt = argv()[argv().index("--append-system-prompt") + 1].lower()
    assert "never mention your own modes" in prompt
