import re

from archpilot.markup import to_pango


def test_bold_and_inline_code():
    assert to_pango("use **prune** with `-a`") == "use <b>prune</b> with <tt>-a</tt>"


def test_heading_becomes_bold():
    assert to_pango("## Remove images") == "<b>Remove images</b>"


def test_bullets_get_a_glyph():
    assert "•" in to_pango("- one\n- two")


def test_fenced_block_becomes_monospace():
    assert to_pango("```bash\ndocker ps\n```") == "<tt>docker ps</tt>"


def test_markup_metacharacters_are_escaped():
    """Pango drops the entire string on malformed markup, so this must hold."""
    out = to_pango("compare a < b && c > d")
    assert "&lt;" in out and "&gt;" in out and "&amp;" in out
    assert "<b" not in out


def test_user_supplied_tags_cannot_inject_markup():
    out = to_pango("run <span foreground='red'>x</span>")
    assert "<span" not in out
    assert "&lt;span" in out


def test_unmatched_asterisk_is_left_alone():
    assert to_pango("2 * 3 = 6") == "2 * 3 = 6"


def test_empty_input():
    assert to_pango("") == ""


def test_every_opened_tag_is_closed():
    text = "## Title\n\nUse **bold**, `code`, *italic* and:\n```\nls -la\n```"
    out = to_pango(text)
    for tag in ("b", "i", "tt"):
        assert out.count(f"<{tag}>") == out.count(f"</{tag}>")


def test_plain_text_survives_unchanged():
    assert to_pango("It is 24 degrees and clear.") == "It is 24 degrees and clear."


from archpilot.markup import wrap_pango


def visible(markup):
    return re.sub(r"<[^>]+>", "", markup)


def test_wraps_long_text_at_the_column_budget():
    out = wrap_pango("word " * 60, 40)
    assert len(out.splitlines()) > 1
    assert all(len(visible(line)) <= 40 for line in out.splitlines())


def test_wrapping_never_splits_a_tag():
    out = wrap_pango("start <b>a bold phrase here</b> end " + "filler " * 20, 20)
    assert "<b" not in visible(out)
    for line in out.splitlines():
        assert line.count("<") == line.count(">")


def test_tags_do_not_consume_column_budget():
    """A heavily tagged line must not wrap earlier than a plain one."""
    plain = wrap_pango("aaa bbb ccc ddd", 15)
    tagged = wrap_pango("<b>aaa</b> <b>bbb</b> <b>ccc</b> <b>ddd</b>", 15)
    assert len(plain.splitlines()) == len(tagged.splitlines())


def test_paragraph_breaks_are_preserved():
    assert wrap_pango("one\n\ntwo", 40).splitlines() == ["one", "", "two"]


def test_a_word_longer_than_the_budget_is_not_broken():
    out = wrap_pango("short " + "x" * 50, 20)
    assert "x" * 50 in out


def test_empty_input_wraps_to_empty():
    assert wrap_pango("", 40) == ""


def test_visible_text_is_preserved_exactly():
    src = to_pango("Use **prune** with `-a` to clear old images from the docker store")
    assert visible(wrap_pango(src, 25)).split() == visible(src).split()


from archpilot.markup import wrap_plain


def test_wrap_plain_respects_width():
    out = wrap_plain("alpha beta gamma delta epsilon zeta", 12)
    assert all(len(line) <= 12 for line in out.splitlines())


def test_wrap_plain_splits_an_unbreakable_path():
    """A long path must be split, not allowed to overflow and get ellipsised."""
    path = "/tmp/" + "a" * 200
    out = wrap_plain(f"touch {path}", 40)
    assert all(len(line) <= 40 for line in out.splitlines())
    assert "".join(out.split()) == f"touch{path}"


def test_wrap_plain_empty():
    assert wrap_plain("", 20) == ""


# --- clickable links ---------------------------------------------------------

def test_a_bare_url_becomes_an_anchor():
    from archpilot.markup import to_pango
    out = to_pango("see https://example.com/docs for more")
    assert '<a href="https://example.com/docs">https://example.com/docs</a>' in out


def test_trailing_punctuation_stays_outside_the_link():
    """Otherwise the full stop at the end of a sentence becomes part of the
    URL and the link 404s."""
    from archpilot.markup import to_pango
    out = to_pango("read https://example.com/page.")
    assert '>https://example.com/page</a>.' in out


def test_a_closing_bracket_is_not_swallowed():
    from archpilot.markup import to_pango
    out = to_pango("(https://example.com/a)")
    assert '>https://example.com/a</a>)' in out


def test_an_ampersand_in_a_query_survives_escaping():
    from archpilot.markup import to_pango
    out = to_pango("https://x.dev/s?q=1&r=2")
    assert 'href="https://x.dev/s?q=1&amp;r=2"' in out
    assert "&r=2" not in out.replace("&amp;", "&amp;")


def test_other_schemes_are_left_alone():
    from archpilot.markup import to_pango
    assert "<a" not in to_pango("ftp://example.com and file:///etc/passwd")


def test_linkify_needs_already_escaped_input():
    """It inserts markup, so it must run after escaping - this pins the order
    the renderer depends on."""
    from archpilot.markup import to_pango
    out = to_pango("<script>alert(1)</script> https://ok.dev/x")
    assert "&lt;script&gt;" in out
    assert '<a href="https://ok.dev/x">' in out


def test_a_url_inside_a_code_fence_is_not_linkified():
    """Code is shown verbatim; turning part of it into a link would misrepresent
    what the command actually is."""
    from archpilot.markup import to_pango
    out = to_pango("```\ncurl https://example.com/x\n```")
    assert "<a href=" not in out
