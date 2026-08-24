import pytest

from archpilot.context.relevance import split_directives, wanted_for


@pytest.mark.parametrize("prompt,expected", [
    ("why did that fail?", "terminal"),
    ("what does this error mean", "terminal"),
    ("fix the traceback above", "terminal"),
    ("how much ram is used right now?", "system"),
    ("my disk is full, what's eating space", "system"),
    ("are there pending pacman updates?", "system"),
    ("is that session done?", "sessions"),
])
def test_prompts_pull_the_context_they_need(prompt, expected):
    assert expected in wanted_for(prompt)


@pytest.mark.parametrize("prompt", [
    "how do I write a for loop in fish?",
    "what is the weather in Tbilisi",
    "explain the difference between TCP and UDP",
])
def test_generic_prompts_pull_nothing_expensive(prompt):
    """Scrollback and system stats cost hundreds of tokens; do not spend them here."""
    assert wanted_for(prompt) == set()


def test_explicit_directives_are_stripped_and_honoured():
    text, wanted = split_directives(":term :sys explain this")
    assert text == "explain this"
    assert wanted == {"terminal", "system"}


def test_directives_only_count_at_the_start():
    text, wanted = split_directives("explain :sys please")
    assert text == "explain :sys please"
    assert wanted == set()


def test_explicit_wins_even_when_heuristics_are_silent():
    assert "system" in wanted_for("hello there", {"system"})


# --------------------------------------------------------------------------
# Clipboard and selection are directive-only: a clipboard routinely holds
# secrets, so no phrasing should ever pull it in implicitly.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("prompt", [
    "explain this",
    "what does this mean",
    "copy this and fix it",
    "paste the clipboard",
    "what is in my clipboard",
    "summarise the selected text",
])
def test_no_prompt_wording_pulls_the_clipboard_in(prompt):
    assert "clipboard" not in wanted_for(prompt)
    assert "selection" not in wanted_for(prompt)


def test_clip_and_sel_directives_work():
    text, wanted = split_directives(":clip :sel explain this")
    assert text == "explain this"
    assert wanted == {"clipboard", "selection"}
