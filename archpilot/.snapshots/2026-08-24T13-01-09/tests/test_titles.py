from archpilot import titles


def test_a_name_round_trips(tmp_path):
    titles.rename("abc", "hyprland keybinds", root=tmp_path)
    assert titles.get("abc", root=tmp_path) == "hyprland keybinds"


def test_renaming_replaces_the_previous_name(tmp_path):
    titles.rename("abc", "first", root=tmp_path)
    titles.rename("abc", "second", root=tmp_path)
    assert titles.get("abc", root=tmp_path) == "second"


def test_an_empty_name_clears_it_rather_than_storing_blank(tmp_path):
    titles.rename("abc", "something", root=tmp_path)
    titles.rename("abc", "   ", root=tmp_path)
    assert titles.get("abc", root=tmp_path) == ""
    assert "abc" not in titles.load(root=tmp_path)


def test_whitespace_is_collapsed(tmp_path):
    assert titles.rename("abc", "  too   many\nspaces ", root=tmp_path) == "too many spaces"


def test_a_very_long_name_is_trimmed(tmp_path):
    stored = titles.rename("abc", "x" * 500, root=tmp_path)
    assert len(stored) == titles.MAX_TITLE


def test_names_are_kept_separately_per_session(tmp_path):
    titles.rename("one", "first chat", root=tmp_path)
    titles.rename("two", "second chat", root=tmp_path)
    assert titles.get("one", root=tmp_path) == "first chat"
    assert titles.get("two", root=tmp_path) == "second chat"


def test_an_unknown_session_has_no_name(tmp_path):
    assert titles.get("nope", root=tmp_path) == ""


def test_a_corrupt_file_does_not_crash(tmp_path):
    (tmp_path / "titles.json").write_text("{not json")
    assert titles.load(root=tmp_path) == {}
    assert titles.rename("abc", "recovered", root=tmp_path) == "recovered"


def test_renaming_without_a_session_id_is_ignored(tmp_path):
    assert titles.rename("", "orphan", root=tmp_path) == ""
    assert titles.load(root=tmp_path) == {}
