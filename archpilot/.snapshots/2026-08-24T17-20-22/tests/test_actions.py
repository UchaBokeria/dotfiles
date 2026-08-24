from archpilot.actions import Action, parse, strip

ANSWER_WITH_ACTION = """You can reclaim that space with docker's prune command.

```archpilot-action
docker system prune -a
```

It removes stopped containers and dangling images."""

WEATHER_ANSWER = "It's 24 degrees and clear in Tbilisi right now."

CODE_BLOCK_NOT_AN_ACTION = """Here's the config shape:

```toml
[ui]
on_submit = "toggle"
```
"""


def test_extracts_a_suggested_command():
    actions = parse(ANSWER_WITH_ACTION)
    assert [a.command for a in actions] == ["docker system prune -a"]


def test_informational_answer_yields_no_action():
    """The weather must not get a button. This is the whole design constraint."""
    assert parse(WEATHER_ANSWER) == []


def test_ordinary_code_fences_are_not_actions():
    assert parse(CODE_BLOCK_NOT_AN_ACTION) == []


def test_strip_removes_the_fence_from_displayed_text():
    shown = strip(ANSWER_WITH_ACTION)
    assert "docker system prune" not in shown
    assert "reclaim that space" in shown
    assert "```" not in shown


def test_multiline_commands_survive_intact():
    text = "```archpilot-action\ncd /tmp \\\n  && ls\n```"
    assert parse(text)[0].command == "cd /tmp \\\n  && ls"


def test_blank_fence_is_ignored():
    assert parse("```archpilot-action\n\n```") == []


def test_label_is_single_line_and_bounded():
    action = Action("cd /tmp \\\n  && " + "x" * 200)
    assert "\n" not in action.label
    assert len(action.label) <= 60


def test_multiple_actions_keep_their_order():
    text = ("```archpilot-action\nfirst\n```\n"
            "```archpilot-action\nsecond\n```")
    assert [a.command for a in parse(text)] == ["first", "second"]
