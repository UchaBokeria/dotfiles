from archpilot.commands import Intent, complete, help_lines, parse, resolve


def test_bare_commands():
    for name in ("new", "history", "sessions", "cancel", "quit", "help", "copy"):
        assert parse(name).kind == name


def test_aliases_resolve():
    assert resolve("q") == "quit"
    assert resolve("m") == "model"
    assert resolve("hist") == "history"


def test_unambiguous_prefix_resolves_like_vim():
    assert resolve("expo") == "export"
    assert resolve("sess") == "sessions"


def test_a_prefix_matching_two_commands_is_ambiguous():
    """`mod` could be model or mode, so it resolves to neither - as in vim."""
    assert resolve("mod") == ""
    assert resolve("mode") == "mode"
    assert resolve("model") == "model"


def test_ambiguous_prefix_is_rejected():
    # "c" could be copy or cancel
    assert resolve("c") == ""


def test_setting_a_model():
    intent = parse("model opus")
    assert intent.kind == "set"
    assert intent.args == {"field": "model", "value": "opus"}


def test_setting_effort_and_mode():
    assert parse("effort max").args["value"] == "max"
    assert parse("mode action").args["value"] == "action"


def test_rejecting_an_unknown_value():
    assert parse("model gpt").failed
    assert "unknown model" in parse("model gpt").message


def test_a_setting_without_a_value_explains_itself():
    intent = parse("effort")
    assert intent.failed and "usage:" in intent.message


def test_unknown_command():
    assert parse("frobnicate").failed


def test_empty_line():
    assert parse("   ").failed


def test_export_with_and_without_a_path():
    assert parse("export /tmp/a.md").args["path"] == "/tmp/a.md"
    assert parse("export").args["path"] == ""


def test_mcp_defaults_to_enabling():
    assert parse("mcp chrome").args == {"server": "chrome", "enable": True}
    assert parse("mcp chrome off").args["enable"] is False


def test_mcp_rejects_a_bad_state():
    assert parse("mcp chrome maybe").failed


def test_completion():
    assert "model" in complete("mo")
    assert complete("zz") == []


def test_help_lists_every_command():
    assert len(help_lines()) >= 10
    assert any(line.startswith(":model") for line in help_lines())


def test_intent_failed_flag():
    assert Intent("error", {}, "x").failed
    assert not Intent("new", {}).failed


def test_tab_commands():
    assert parse("tabnew").kind == "tab"
    assert parse("tabnew").args["action"] == "new"
    assert parse("tabclose").args["action"] == "close"
    assert resolve("tn") == "tabnew"


# --- the `:` suggestion list -------------------------------------------------

def test_an_empty_line_offers_every_command():
    from archpilot.commands import COMMANDS, suggestions
    assert len(suggestions("")) == len(COMMANDS)


def test_suggestions_narrow_as_you_type():
    from archpilot.commands import suggestions
    names = [name for name, _help in suggestions("ta")]
    assert names == ["tabclose", "tabnew"]


def test_each_suggestion_carries_its_help_text():
    from archpilot.commands import suggestions
    assert all(help_text for _name, help_text in suggestions(""))


def test_once_arguments_start_the_command_stops_being_filtered():
    """Filtering on the whole line would empty the list exactly when the user
    is midway through typing a value."""
    from archpilot.commands import suggestions
    assert [n for n, _h in suggestions("model haiku")] == ["model"]


def test_an_unknown_word_offers_nothing():
    from archpilot.commands import suggestions
    assert suggestions("zzz") == []


def test_no_command_name_contains_j_or_k():
    """j/k steer the suggestion list while the command word is being typed,
    which is only safe because no command needs those letters."""
    from archpilot.commands import COMMANDS
    assert not [n for n in COMMANDS if "j" in n or "k" in n]


def test_every_keybinding_row_is_a_pair_of_strings():
    from archpilot.commands import KEYBINDINGS
    for group, entries in KEYBINDINGS:
        assert isinstance(group, str) and group
        for keys, note in entries:
            assert keys and note


def test_describe_finds_help_through_an_alias():
    from archpilot.commands import describe
    assert describe("q") == describe("quit")
    assert describe("nonsense") == ""
