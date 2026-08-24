"""Vim editor tests. No GTK involved - the engine is deliberately standalone."""

import pytest

from archpilot.vim import INSERT, NORMAL, VISUAL, VimBuffer

SENTENCE = "hello brave new world"


def buf(text=SENTENCE, cursor=0, mode=NORMAL):
    return VimBuffer(text=text, cursor=cursor, mode=mode)


def feed(b, keys):
    """Feed a string of single-key presses; returns the last action."""
    action = ""
    for k in keys:
        action = b.feed(k)
    return action


# --------------------------------------------------------------------------
# Motions
# --------------------------------------------------------------------------
@pytest.mark.parametrize("keys,expected", [
    ("l", 1), ("lll", 3), ("3l", 3),
    ("w", 6), ("ww", 12), ("2w", 12),
    ("$", 20), ("$h", 19),
    ("$b", 16), ("$0", 0),
    ("e", 4), ("ee", 10),
])
def test_motions_land_where_vim_lands(keys, expected):
    b = buf()
    feed(b, keys)
    assert b.cursor == expected


def test_h_stops_at_the_start():
    b = buf(cursor=0)
    feed(b, "hhhh")
    assert b.cursor == 0


def test_l_stops_on_the_last_character_in_normal_mode():
    """Normal mode sits ON a character, so `$` is len-1, not len."""
    b = buf()
    feed(b, "l" * 99)
    assert b.cursor == len(SENTENCE) - 1


def test_caret_goes_to_first_non_blank():
    b = buf(text="   indented", cursor=9)
    feed(b, "^")
    assert b.cursor == 3


def test_find_and_till():
    b = buf()
    feed(b, "fb")
    assert b.cursor == SENTENCE.index("brave")
    b2 = buf()
    feed(b2, "tb")
    assert b2.cursor == SENTENCE.index("brave") - 1


def test_find_with_a_count():
    b = buf(text="a.b.c.d")
    feed(b, "2f.")
    assert b.cursor == 3


def test_find_that_misses_leaves_the_cursor_alone():
    b = buf()
    feed(b, "fz")
    assert b.cursor == 0


def test_gg_and_G():
    b = buf(cursor=10)
    feed(b, "gg")
    assert b.cursor == 0
    feed(b, "G")
    assert b.cursor == len(SENTENCE) - 1


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------
def test_dw_deletes_a_word():
    b = buf()
    feed(b, "dw")
    assert b.text == "brave new world"


def test_dw_with_a_count():
    b = buf()
    feed(b, "d2w")
    assert b.text == "new world"


def test_db_deletes_backwards():
    b = buf(cursor=12)
    feed(b, "db")
    assert b.text == "hello new world"


def test_de_is_inclusive():
    b = buf()
    feed(b, "de")
    assert b.text == " brave new world"


def test_dd_clears_the_line():
    b = buf()
    feed(b, "dd")
    assert b.text == "" and b.cursor == 0


def test_D_deletes_to_end_of_line():
    b = buf(cursor=6)
    feed(b, "D")
    assert b.text == "hello "


def test_cw_deletes_and_enters_insert():
    b = buf()
    feed(b, "cw")
    assert b.text == "brave new world"
    assert b.mode == INSERT


def test_C_changes_to_end():
    b = buf(cursor=6)
    feed(b, "C")
    assert b.text == "hello " and b.mode == INSERT


def test_df_deletes_through_the_target():
    b = buf()
    feed(b, "dfb")
    assert b.text == "rave new world"


def test_yank_then_paste():
    b = buf()
    feed(b, "yw")
    assert b.register == "hello "
    feed(b, "$p")
    assert b.text.endswith("dhello ")


def test_yy_yanks_the_whole_line():
    b = buf()
    feed(b, "yy")
    assert b.register == SENTENCE
    assert b.text == SENTENCE, "yank must not modify the text"


def test_P_pastes_before_the_cursor():
    b = buf(text="world", cursor=0)
    b.register = "hello "
    feed(b, "P")
    assert b.text == "hello world"


# --------------------------------------------------------------------------
# Entering insert
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key,cursor,expected_cursor", [
    ("i", 5, 5), ("a", 5, 6), ("A", 5, len(SENTENCE)), ("I", 5, 0),
])
def test_insert_entry_points(key, cursor, expected_cursor):
    b = buf(cursor=cursor)
    feed(b, key)
    assert b.mode == INSERT and b.cursor == expected_cursor


def test_escape_leaves_insert_and_steps_back():
    b = buf(text="hi", cursor=2, mode=INSERT)
    b.feed("escape")
    assert b.mode == NORMAL and b.cursor == 1


def test_typing_inserts_at_the_cursor():
    b = buf(text="hllo", cursor=1, mode=INSERT)
    b.feed("e")
    assert b.text == "hello" and b.cursor == 2


def test_backspace_in_insert():
    b = buf(text="helllo", cursor=4, mode=INSERT)
    b.feed("backspace")
    assert b.text == "hello"


def test_ctrl_w_deletes_a_word_backwards():
    b = buf(text="hello brave", cursor=11, mode=INSERT)
    b.feed("ctrl-w")
    assert b.text == "hello "


def test_ctrl_u_clears_to_the_start():
    b = buf(text="hello brave", cursor=11, mode=INSERT)
    b.feed("ctrl-u")
    assert b.text == ""


# --------------------------------------------------------------------------
# Small edits
# --------------------------------------------------------------------------
def test_x_deletes_under_the_cursor():
    b = buf()
    feed(b, "x")
    assert b.text == "ello brave new world"


def test_x_with_a_count():
    b = buf()
    feed(b, "3x")
    assert b.text == "lo brave new world"


def test_s_substitutes():
    b = buf()
    feed(b, "s")
    assert b.text == "ello brave new world" and b.mode == INSERT


# --------------------------------------------------------------------------
# Undo / redo
# --------------------------------------------------------------------------
def test_undo_restores_text():
    b = buf()
    feed(b, "dw")
    feed(b, "u")
    assert b.text == SENTENCE


def test_redo_reapplies():
    b = buf()
    feed(b, "dw")
    feed(b, "u")
    b.feed("ctrl-r")
    assert b.text == "brave new world"


def test_undo_with_nothing_to_undo_is_safe():
    b = buf()
    feed(b, "uuu")
    assert b.text == SENTENCE


# --------------------------------------------------------------------------
# Modes and actions
# --------------------------------------------------------------------------
def test_enter_submits_from_both_modes():
    assert buf().feed("enter") == "submit"
    assert buf(mode=INSERT).feed("enter") == "submit"


def test_escape_in_normal_does_nothing():
    """As in vim. Closing on Esc made the window vanish on a habitual double-tap."""
    b = buf()
    assert b.feed("escape") == ""
    assert b.mode == NORMAL


def test_ZZ_closes_from_normal():
    """`q` now starts a macro, as in vim, so closing moved to ZZ."""
    b = buf()
    assert b.feed("Z") == ""
    assert b.feed("Z") == "close"


def test_a_single_Z_does_not_close():
    assert buf().feed("Z") == ""


def test_q_typed_in_insert_is_just_a_letter():
    b = buf(text="", mode=INSERT)
    assert b.feed("q") == ""
    assert b.text == "q"


def test_escape_from_visual_returns_to_normal_without_closing():
    b = buf()
    feed(b, "v")
    assert b.mode == VISUAL
    assert b.feed("escape") == ""
    assert b.mode == NORMAL


def test_visual_selection_tracks_the_cursor():
    b = buf()
    feed(b, "vww")
    start, end = b.selection()
    # visual is inclusive of the character under the cursor
    assert (start, end) == (0, 13)


def test_counts_are_shown_while_pending():
    b = buf()
    b.feed("2")
    assert b.snapshot()["pending"] == "2"
    b.feed("d")
    assert "d" in b.snapshot()["pending"]


def test_an_unknown_key_clears_pending_state():
    b = buf()
    feed(b, "2d")
    b.feed("\\")
    assert b.snapshot()["pending"] == ""


def test_clear_resets_into_insert():
    b = buf()
    feed(b, "dw")
    b.clear()
    assert b.text == "" and b.mode == INSERT and not b.undo_stack


def test_dw_on_the_final_word_deletes_to_end_of_line():
    """The normal-mode clamp must not shorten an operator's range."""
    b = buf(text="what is docker prune", cursor=15)
    feed(b, "dw")
    assert b.text == "what is docker "


def test_de_on_the_final_word_also_reaches_the_end():
    b = buf(text="alpha beta", cursor=6)
    feed(b, "de")
    assert b.text == "alpha "


def test_cursor_motion_is_still_clamped():
    b = buf(text="alpha beta", cursor=6)
    feed(b, "w")
    assert b.cursor == len("alpha beta") - 1


# --------------------------------------------------------------------------
# Multi-line. The prompt grows to several lines like any modern chat input,
# so the editor has to be line-aware rather than treating it as one string.
# --------------------------------------------------------------------------
LINES = "first line\nsecond line\nthird"


def multi(cursor=0, mode=NORMAL):
    return VimBuffer(text=LINES, cursor=cursor, mode=mode)


def line_at(b):
    return b.text[b.line_start(b.cursor):b.line_end(b.cursor)]


def test_j_and_k_move_between_lines():
    b = multi()
    feed(b, "j")
    assert line_at(b) == "second line"
    feed(b, "j")
    assert line_at(b) == "third"
    feed(b, "k")
    assert line_at(b) == "second line"


def test_j_keeps_the_column():
    b = multi(cursor=6)          # "first |line"
    feed(b, "j")
    assert b.column(b.cursor) == 6


def test_j_clamps_on_a_shorter_line():
    b = multi(cursor=9)
    feed(b, "jj")                # "third" is shorter
    assert b.cursor <= b.line_end(b.cursor)


def test_zero_and_dollar_are_line_relative():
    b = multi()
    feed(b, "j$")
    assert b.cursor == b.line_end(b.cursor) - 1
    feed(b, "0")
    assert b.cursor == b.line_start(b.cursor)


def test_o_opens_a_line_below():
    b = multi()
    feed(b, "o")
    assert b.mode == INSERT
    assert b.text.startswith("first line\n\n")
    assert line_at(b) == ""


def test_O_opens_a_line_above():
    b = multi(cursor=11)         # on "second line"
    feed(b, "O")
    assert b.mode == INSERT
    assert b.text.splitlines()[1] == ""


def test_dd_removes_only_that_line():
    b = multi(cursor=11)
    feed(b, "dd")
    assert b.text == "first line\nthird"


def test_dd_on_the_last_line():
    b = multi(cursor=24)
    feed(b, "dd")
    assert b.text == "first line\nsecond line"


def test_cc_empties_the_line_but_keeps_it():
    b = multi(cursor=11)
    feed(b, "cc")
    assert b.text == "first line\n\nthird"
    assert b.mode == INSERT


def test_D_stops_at_the_end_of_the_line():
    b = multi(cursor=11 + 6)     # inside "second line"
    feed(b, "D")
    assert b.text == "first line\nsecond\nthird"


def test_A_appends_at_the_end_of_the_current_line():
    b = multi(cursor=11)
    feed(b, "A")
    assert b.cursor == b.line_end(11)


def test_shift_enter_inserts_a_newline_without_submitting():
    b = VimBuffer(text="hello", cursor=5, mode=INSERT)
    assert b.feed("newline") == ""
    assert b.text == "hello\n"


def test_enter_still_submits_from_insert():
    b = VimBuffer(text="hello", cursor=5, mode=INSERT)
    assert b.feed("enter") == "submit"


# --------------------------------------------------------------------------
# Visual mode. An operator applies to the selection immediately; waiting for a
# motion is what made it look broken.
# --------------------------------------------------------------------------
def test_visual_delete_removes_the_selection():
    """Visual is inclusive of the character under the cursor, so `vwd` takes
    the space and the first letter of the next word with it - as vim does."""
    b = buf()
    feed(b, "vw")
    feed(b, "d")
    assert b.text == "rave new world"
    assert b.mode == NORMAL


def test_visual_yank_copies_without_deleting():
    b = buf()
    feed(b, "vw")
    feed(b, "y")
    assert b.text == SENTENCE
    assert b.register.startswith("hello")
    assert b.mode == NORMAL


def test_visual_change_enters_insert():
    b = buf()
    feed(b, "vw")
    feed(b, "c")
    assert b.mode == INSERT
    assert b.text == "rave new world"


def test_visual_selection_is_inclusive_of_the_cursor_character():
    b = buf()
    feed(b, "vl")
    assert b.selection() == (0, 2)


def test_escape_leaves_visual_without_editing():
    b = buf()
    feed(b, "vw")
    b.feed("escape")
    assert b.mode == NORMAL and b.text == SENTENCE


# --------------------------------------------------------------------------
# Line-visual, and the operations that were missing from the set.
# --------------------------------------------------------------------------
from archpilot.vim import VLINE


def test_V_enters_line_visual():
    b = multi()
    feed(b, "V")
    assert b.mode == VLINE


def test_V_selects_whole_lines_regardless_of_column():
    b = multi(cursor=4)          # mid-word on line one
    feed(b, "V")
    start, end = b.selection()
    assert start == 0
    assert b.text[start:end].rstrip("\n") == "first line"


def test_Vd_removes_the_line_and_closes_the_gap():
    b = multi(cursor=11)
    feed(b, "V")
    feed(b, "d")
    assert b.text == "first line\nthird"


def test_V_extends_over_several_lines():
    b = multi()
    feed(b, "Vj")
    feed(b, "d")
    assert b.text == "third"


def test_Vy_yanks_lines_without_deleting():
    b = multi()
    feed(b, "V")
    feed(b, "y")
    assert b.text == LINES
    assert b.register.startswith("first line")


def test_escape_leaves_line_visual():
    b = multi()
    feed(b, "V")
    b.feed("escape")
    assert b.mode == NORMAL and b.text == LINES


def test_r_replaces_one_character():
    b = buf(text="hello")
    feed(b, "rj")
    assert b.text == "jello"


def test_r_at_end_of_text_is_safe():
    b = buf(text="")
    feed(b, "rx")
    assert b.text == ""


def test_J_joins_the_next_line_with_a_space():
    b = buf(text="one\ntwo")
    feed(b, "J")
    assert b.text == "one two"


def test_J_strips_leading_whitespace_from_the_joined_line():
    b = buf(text="one\n    two")
    feed(b, "J")
    assert b.text == "one two"


def test_J_on_the_last_line_does_nothing():
    b = buf(text="only")
    feed(b, "J")
    assert b.text == "only"


def test_tilde_toggles_case_and_advances():
    b = buf(text="abc")
    feed(b, "~")
    assert b.text == "Abc" and b.cursor == 1


def test_tilde_with_a_count():
    b = buf(text="abcd")
    feed(b, "3~")
    assert b.text == "ABCd"


def test_undo_covers_the_new_operations():
    b = buf(text="one\ntwo")
    feed(b, "J")
    feed(b, "u")
    assert b.text == "one\ntwo"


# --------------------------------------------------------------------------
# Macros.
# --------------------------------------------------------------------------
def test_macro_records_and_replays():
    b = buf(text="one two three four")
    feed(b, "qadwq")                  # record dw into register a
    assert b.registers["a"] == ["d", "w"]
    assert b.text == "two three four"
    feed(b, "@a")
    assert b.text == "three four"


def test_the_closing_q_is_not_part_of_the_macro():
    b = buf(text="alpha beta")
    feed(b, "qbxq")
    assert b.registers["b"] == ["x"]


def test_at_at_repeats_the_last_macro():
    b = buf(text="a b c d e")
    feed(b, "qcdwq")
    feed(b, "@c")
    feed(b, "@@")
    assert b.text == "d e"


def test_replaying_an_empty_register_is_safe():
    b = buf(text="unchanged")
    feed(b, "@z")
    assert b.text == "unchanged"


def test_a_macro_cannot_recurse_into_itself():
    """Guarding this is what stops @a containing @a from hanging the window."""
    b = buf(text="one two three")
    b.registers["a"] = ["@", "a"]
    feed(b, "@a")
    assert b.text == "one two three"


def test_recording_state_is_visible():
    b = buf()
    feed(b, "qa")
    assert b.recording == "a"
    feed(b, "q")
    assert b.recording == ""


# --------------------------------------------------------------------------
# Visual block. The point of it is editing several lines at once.
# --------------------------------------------------------------------------
from archpilot.vim import VBLOCK

BLOCK = "aaa\nbbb\nccc"


def block(cursor=0):
    return VimBuffer(text=BLOCK, cursor=cursor)


def test_ctrl_v_enters_block_mode():
    b = block()
    b.feed("ctrl-v")
    assert b.mode == VBLOCK


def test_block_covers_one_range_per_line():
    b = block()
    b.feed("ctrl-v")          # a named key, not a string of characters
    feed(b, "jj")
    assert b.block_ranges() == [(0, 1), (4, 5), (8, 9)]


def test_block_widens_with_the_cursor():
    b = block()
    for key in ("ctrl-v", "j", "j", "l"):
        b.feed(key)
    assert all(end - start == 2 for start, end in b.block_ranges())


def test_block_I_types_on_every_line():
    b = block()
    for key in ("ctrl-v", "j", "j", "I"):
        b.feed(key)
    feed(b, "X-")
    b.feed("escape")
    assert b.text == "X-aaa\nX-bbb\nX-ccc"


def test_block_A_appends_on_every_line():
    b = VimBuffer(text="one\ntwo\nsix", cursor=0)
    for key in ("ctrl-v", "j", "j", "A"):
        b.feed(key)
    b.feed("!")
    b.feed("escape")
    assert b.text == "o!ne\nt!wo\ns!ix"


def test_block_delete_removes_the_rectangle():
    b = block()
    for key in ("ctrl-v", "j", "j", "l", "d"):
        b.feed(key)
    assert b.text == "a\nb\nc"


def test_block_yank_joins_the_rows():
    b = block()
    for key in ("ctrl-v", "j", "j"):
        b.feed(key)
    b.feed("y")
    assert b.register == "a\nb\nc"
    assert b.text == BLOCK


def test_block_change_enters_insert():
    b = block()
    for key in ("ctrl-v", "j", "j", "c"):
        b.feed(key)
    assert b.mode == INSERT


def test_block_clips_on_short_lines():
    """A ragged block must not run past the end of a short line."""
    b = VimBuffer(text="longer\nab\nlonger", cursor=0)
    for key in ("ctrl-v", "j", "j", "l", "l", "l", "l"):
        b.feed(key)
    for start, end in b.block_ranges():
        assert end <= b.line_end(start)


def test_escape_leaves_block_mode():
    b = block()
    b.feed("ctrl-v")
    b.feed("escape")
    assert b.mode == NORMAL and b.text == BLOCK


def test_a_single_line_block_behaves_like_a_normal_edit():
    b = block()
    for key in ("ctrl-v", "l", "d"):
        b.feed(key)
    assert b.text == "a\nbbb\nccc"


# --- blockwise visual, the way ctrl-v behaves in vim -------------------------

BLOCK_TEXT = "alpha one\nbravo two\ncharlie three"


def _block(keys, typed=""):
    buf = VimBuffer(mode=NORMAL)
    buf.text = BLOCK_TEXT
    buf.cursor = BLOCK_TEXT.index("charlie")      # bottom line, column 0
    for key in keys:
        buf.feed(key)
    for char in typed:
        buf.feed(char)
    if typed:
        buf.feed("escape")
    return buf


def test_ctrl_v_enters_blockwise_not_linewise():
    assert _block(["ctrl-v"]).mode == VBLOCK


def test_k_extends_the_block_up_a_line_at_a_time():
    assert len(_block(["ctrl-v", "k"]).block_ranges()) == 2
    assert len(_block(["ctrl-v", "k", "k"]).block_ranges()) == 3


def test_the_block_is_a_column_rectangle_not_a_linear_run():
    """Each covered line contributes its own slice; the text between lines is
    outside the selection."""
    ranges = _block(["ctrl-v", "k", "k", "l"]).block_ranges()
    assert ranges == [(0, 2), (10, 12), (20, 22)]
    assert [BLOCK_TEXT[a:b] for a, b in ranges] == ["al", "br", "ch"]


def test_insert_types_on_every_line():
    assert _block(["ctrl-v", "k", "k", "I"], "X").text == (
        "Xalpha one\nXbravo two\nXcharlie three")


def test_change_types_on_every_line_too():
    """Block c used to enter insert without recording the other lines' edit
    points, so only the first line got what you typed."""
    assert _block(["ctrl-v", "k", "k", "l", "l", "c"], "ZZ").text == (
        "ZZha one\nZZvo two\nZZrlie three")


def test_dollar_makes_the_block_ragged_right():
    """`$A` must append at the end of EACH line. Clipping to the cursor's
    column instead put the text mid-line on anything longer."""
    assert _block(["ctrl-v", "k", "k", "$", "A"], " END").text == (
        "alpha one END\nbravo two END\ncharlie three END")


def test_a_horizontal_motion_after_dollar_pins_the_column_again():
    assert _block(["ctrl-v", "k", "k", "$", "l"]).block_to_eol is False


def test_a_fresh_block_is_never_ragged():
    assert _block(["ctrl-v", "k"]).block_to_eol is False


def test_delete_removes_the_rectangle_only():
    assert _block(["ctrl-v", "k", "k", "l", "l", "d"]).text == (
        "ha one\nvo two\nrlie three")


def test_yank_keeps_the_rectangle_line_by_line():
    assert _block(["ctrl-v", "k", "k", "l", "y"]).register == "al\nbr\nch"


def test_word_motion_widens_the_block():
    ranges = _block(["ctrl-v", "k", "k", "w"]).block_ranges()
    assert all(b - a == 7 for a, b in ranges)


def test_leaving_block_mode_clears_the_ragged_flag():
    buf = _block(["ctrl-v", "k", "k", "$"])
    buf.feed("d")
    assert buf.block_to_eol is False


# --- multicursor (vim-visual-multi) ------------------------------------------

MULTI_TEXT = "foo bar foo baz foo"


def _multi(text, keys, typed="", cursor=0):
    buf = VimBuffer(mode=NORMAL)
    buf.text = text
    buf.cursor = cursor
    for key in keys:
        buf.feed(key)
    for char in typed:
        buf.feed(char)
    if typed:
        buf.feed("escape")
    return buf


def test_the_first_ctrl_n_selects_the_word_under_the_cursor():
    assert _multi(MULTI_TEXT, ["ctrl-n"]).multi == [(0, 3)]


def test_each_ctrl_n_adds_the_next_occurrence():
    assert _multi(MULTI_TEXT, ["ctrl-n", "ctrl-n"]).multi == [(0, 3), (8, 11)]
    assert _multi(MULTI_TEXT, ["ctrl-n"] * 3).multi == [(0, 3), (8, 11), (16, 19)]


def test_it_matches_whole_words_only():
    """Selecting `foo` must not also grab the `foo` inside `foobar`."""
    buf = _multi("foo foobar foo", ["ctrl-n", "ctrl-n"])
    assert buf.multi == [(0, 3), (11, 14)]


def test_the_search_wraps_round_to_earlier_occurrences():
    buf = _multi(MULTI_TEXT, ["ctrl-n", "ctrl-n"], cursor=16)
    assert len(buf.multi) == 2
    assert (16, 19) in buf.multi


def test_change_rewrites_every_occurrence():
    assert _multi(MULTI_TEXT, ["ctrl-n"] * 3 + ["c"], "QUX").text == (
        "QUX bar QUX baz QUX")


def test_insert_and_append_land_on_every_cursor():
    assert _multi(MULTI_TEXT, ["ctrl-n"] * 3 + ["I"], ">").text == (
        ">foo bar >foo baz >foo")
    assert _multi(MULTI_TEXT, ["ctrl-n"] * 3 + ["A"], "!").text == (
        "foo! bar foo! baz foo!")


def test_delete_removes_every_occurrence():
    assert _multi(MULTI_TEXT, ["ctrl-n", "ctrl-n", "d"]).text == " bar  baz foo"


def test_yank_collects_every_occurrence():
    assert _multi(MULTI_TEXT, ["ctrl-n", "ctrl-n", "y"]).register == "foo\nfoo"


def test_escape_drops_the_cursors():
    assert _multi(MULTI_TEXT, ["ctrl-n", "ctrl-n", "escape"]).multi == []


def test_an_unrelated_key_ends_multicursor_rather_than_acting_on_all():
    """Better to lose the cursors than to apply something surprising to every
    occurrence at once. Motions and operators are handled; `~` is neither."""
    assert _multi(MULTI_TEXT, ["ctrl-n", "ctrl-n", "~"]).multi == []


def test_ctrl_down_stacks_cursors_down_the_lines():
    buf = _multi("one\ntwo\nthree", ["ctrl-down", "ctrl-down"])
    assert buf.multi == [(0, 0), (4, 4)] or len(buf.multi) == 3


def test_vertical_cursors_type_on_every_line():
    assert _multi("one\ntwo\nthree", ["ctrl-down", "ctrl-down", "I"], "#").text == (
        "#one\n#two\n#three")


def test_ctrl_up_does_nothing_on_the_first_line():
    buf = _multi("one\ntwo", ["ctrl-up"])
    assert len(buf.multi) <= 1


def test_a_cursor_on_a_non_word_character_starts_nothing():
    assert _multi("   ", ["ctrl-n"], cursor=1).multi == []


def test_word_bounds_finds_the_whole_identifier():
    buf = VimBuffer(mode=NORMAL)
    buf.text = "call some_name(x)"
    assert buf.word_bounds(7) == (5, 14)


# --- lowercase i / a in blockwise, and multicursor motions -------------------

def test_lowercase_i_types_on_every_line_of_a_block():
    """Strict vim reserves `i` for text objects, which this editor does not
    have. Reaching for `i` after ctrl-v is the obvious move, and having it
    insert on one line looked like the block had been thrown away."""
    assert _block(["ctrl-v", "k", "k", "i"], ">").text == (
        ">alpha one\n>bravo two\n>charlie three")


def test_lowercase_a_appends_on_every_line_of_a_block():
    assert _block(["ctrl-v", "k", "k", "a"], ">").text == (
        "a>lpha one\nb>ravo two\nc>harlie three")


def test_lowercase_and_uppercase_agree_in_block_mode():
    assert (_block(["ctrl-v", "k", "k", "i"], "X").text
            == _block(["ctrl-v", "k", "k", "I"], "X").text)
    assert (_block(["ctrl-v", "k", "k", "a"], "X").text
            == _block(["ctrl-v", "k", "k", "A"], "X").text)


def test_block_replace_covers_the_whole_rectangle():
    """`r` used to replace only the character under the cursor, so block-r
    looked like it had ignored the selection."""
    assert _block(["ctrl-v", "k", "k", "r", "X"]).text == (
        "Xlpha one\nXravo two\nXharlie three")


def test_a_motion_moves_every_cursor_independently():
    """`w` on three cursors goes to the next word on each one's own line, not
    to a single shared place."""
    buf = _multi("one two\nthree four\nfive six", ["ctrl-down", "ctrl-down", "w"])
    assert buf.multi == [(4, 4), (14, 14), (24, 24)]


def test_moving_then_typing_lands_on_every_cursor():
    assert _multi("one two\nthree four\nfive six",
                  ["ctrl-down", "ctrl-down", "w", "i"], "[").text == (
        "one [two\nthree [four\nfive [six")


def test_dollar_moves_every_cursor_to_its_own_line_end():
    # "one" ends at 2, "three" at 8, "five" at 13.
    buf = _multi("one\nthree\nfive", ["ctrl-down", "ctrl-down", "$"])
    assert [start for start, _end in buf.multi] == [2, 8, 13]


def test_lowercase_a_appends_after_each_ctrl_n_match():
    assert _multi(MULTI_TEXT, ["ctrl-n"] * 3 + ["a"], "!").text == (
        "foo! bar foo! baz foo!")
