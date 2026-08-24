from pathlib import Path

from archpilot.session import IDLE, Session


def make():
    return Session.create(mode="ask", model="opus")


def test_session_gets_a_uuid_and_the_base_cwd():
    s = make()
    assert len(s.id) == 36 and s.id.count("-") == 4
    assert s.cwd.name == "archpilot"


def test_resume_hint_is_a_runnable_command():
    s = make()
    assert s.resume_hint == f"cd {s.cwd} && claude --resume {s.id}"


def test_transcript_path_matches_the_cli_slug_scheme():
    s = make()
    assert s.transcript.name == f"{s.id}.jsonl"
    assert s.transcript.parent.name == "-home-scriptkid--config--dotfiles-blackwall-archpilot"


def test_finish_turn_splits_answer_from_actions():
    s = make()
    s.finish_turn("Prune it.\n\n```archpilot-action\ndocker system prune -a\n```\n")
    assert s.actions[0].command == "docker system prune -a"
    assert "```" not in s.answer
    assert s.status == IDLE


def test_snapshot_is_flat_json_for_eww():
    s = make()
    s.finish_turn("Do it.\n\n```archpilot-action\nls\n```")
    snap = s.snapshot()
    assert snap["has_actions"] is True
    assert snap["actions"][0]["command"] == "ls"
    assert set(snap) >= {"mode", "model", "status", "answer", "actions", "resume"}
    # eww dot-access needs scalars at the top level, not nested dicts.
    assert all(not isinstance(v, dict) for v in snap.values())


def test_informational_answer_has_no_actions():
    s = make()
    s.finish_turn("It is 24 degrees and clear.")
    assert s.snapshot()["has_actions"] is False


def test_snapshot_flattens_action_slots_for_eww():
    s = make()
    s.finish_turn("go\n\n```archpilot-action\ndocker system prune -a\n```")
    snap = s.snapshot()
    assert snap["show_action0"] is True and snap["action0"] == "docker system prune -a"
    assert snap["show_action1"] is False and snap["action1"] == ""
    assert snap["action_count"] == 1


def test_snapshot_slots_are_empty_without_actions():
    s = make()
    s.finish_turn("It is 24 degrees.")
    snap = s.snapshot()
    assert all(snap[f"show_action{i}"] is False for i in range(3))
    assert snap["action_count"] == 0


def test_answer_height_grows_with_content():
    s = make()
    s.finish_turn("short")
    short = s.snapshot()["answer_height"]
    s.finish_turn("word " * 400)
    long = s.snapshot()["answer_height"]
    assert short < long
    assert short >= Session.MIN_ANSWER_PX


def test_answer_height_is_capped():
    s = make()
    s.finish_turn("line\n" * 500)
    assert s.snapshot()["answer_height"] == Session.MAX_ANSWER_PX


def test_empty_answer_uses_minimum_height():
    assert make().snapshot()["answer_height"] == Session.MIN_ANSWER_PX


def test_snapshot_carries_pango_markup():
    s = make()
    s.finish_turn("use **prune** to clear `images`")
    assert s.snapshot()["answer_markup"] == "use <b>prune</b> to clear <tt>images</tt>"


def test_long_answers_are_hard_wrapped_by_the_daemon():
    """eww 0.5.0 ignores :wrap on labels, so the wrapping must happen here."""
    s = make()
    s.finish_turn("word " * 200)
    markup = s.snapshot()["answer_markup"]
    assert len(markup.splitlines()) > 1
    assert all(len(line) <= Session.WRAP_COLS + 2 for line in markup.splitlines())


def test_height_matches_the_wrapped_line_count():
    s = make()
    s.finish_turn("word " * 200)
    snap = s.snapshot()
    lines = len(snap["answer_markup"].splitlines())
    assert snap["answer_height"] == min(Session.MAX_ANSWER_PX,
                                        lines * Session.LINE_PX + 12)


# --------------------------------------------------------------------------
# Context meter.
# --------------------------------------------------------------------------
RESULT = {
    "usage": {"input_tokens": 100, "cache_creation_input_tokens": 400,
              "cache_read_input_tokens": 9500, "output_tokens": 50},
    "modelUsage": {"claude-sonnet-5": {"contextWindow": 20000}},
}


def test_context_counts_cache_reads_as_occupancy():
    """Cache reads occupy the window exactly like fresh input does."""
    s = make()
    s.record_usage(RESULT)
    assert s.context_used == 10000
    assert s.context_total == 20000
    assert s.context_pct == 50


def test_output_tokens_do_not_count_toward_the_window():
    s = make()
    s.record_usage(RESULT)
    assert s.context_used == 100 + 400 + 9500


def test_context_label_is_empty_before_any_turn():
    s = make()
    assert s.context_label == "" and s.context_pct == 0


def test_context_warns_only_when_nearly_full():
    s = make()
    s.record_usage(RESULT)
    assert s.snapshot()["context_warn"] is False
    s.record_usage({"usage": {"input_tokens": 18000},
                    "modelUsage": {"m": {"contextWindow": 20000}}})
    assert s.snapshot()["context_warn"] is True


def test_malformed_usage_is_survivable():
    s = make()
    s.record_usage({})
    s.record_usage({"usage": None, "modelUsage": None})
    assert s.context_pct == 0


def test_percentage_is_capped():
    s = make()
    s.record_usage({"usage": {"input_tokens": 999999},
                    "modelUsage": {"m": {"contextWindow": 1000}}})
    assert s.context_pct == 100


# --------------------------------------------------------------------------
# Rate-limit windows. Claude Code reports the reset time but NOT the percentage
# consumed, so only the time is surfaced - a guessed percentage would be worse
# than none.
# --------------------------------------------------------------------------
import time as _time


def limit_event(kind, in_seconds, status="allowed"):
    return {"rate_limit_info": {"status": status, "rateLimitType": kind,
                                "resetsAt": int(_time.time()) + in_seconds}}


def test_five_hour_window_is_shown_as_a_wall_clock_time():
    """"resets 20:00" is easier to plan around than "2h14m left"."""
    s = make()
    resets = _time.time() + 8100
    s.record_limits(limit_event("five_hour", 8100))
    assert s.snapshot()["limit_5h"] == _time.strftime("%H:%M", _time.localtime(resets))


def test_a_window_more_than_a_day_out_gains_a_weekday():
    s = make()
    resets = _time.time() + 270000
    s.record_limits(limit_event("weekly", 270000))
    assert s.snapshot()["limit_week"] == _time.strftime("%a %H:%M", _time.localtime(resets))


def test_a_window_within_a_day_omits_the_weekday():
    s = make()
    s.record_limits(limit_event("five_hour", 3600))
    assert " " not in s.snapshot()["limit_5h"]


def test_both_windows_are_tracked_independently():
    s = make()
    s.record_limits(limit_event("five_hour", 600))
    s.record_limits(limit_event("weekly", 270000))
    snap = s.snapshot()
    assert snap["limit_5h"] and snap["limit_week"]
    assert snap["limit_5h"] != snap["limit_week"]


def test_an_elapsed_window_reads_now():
    s = make()
    s.record_limits(limit_event("five_hour", -50))
    assert s.snapshot()["limit_5h"] == "now"


def test_limit_warn_only_when_not_allowed():
    s = make()
    s.record_limits(limit_event("five_hour", 600, status="allowed"))
    assert s.snapshot()["limit_warn"] is False
    s.record_limits(limit_event("five_hour", 600, status="rejected"))
    assert s.snapshot()["limit_warn"] is True


def test_no_limits_yet_renders_nothing():
    snap = make().snapshot()
    assert snap["limit_5h"] == "" and snap["limit_week"] == ""


def test_context_left_is_human_scaled():
    s = make()
    s.record_usage({"usage": {"input_tokens": 40_000},
                    "modelUsage": {"m": {"contextWindow": 200_000}}})
    assert s.snapshot()["context_left"] == "160k"
    s.record_usage({"usage": {"input_tokens": 100_000},
                    "modelUsage": {"m": {"contextWindow": 1_200_000}}})
    assert s.snapshot()["context_left"] == "1.1M"


def test_context_left_never_goes_negative():
    s = make()
    s.record_usage({"usage": {"input_tokens": 999_999},
                    "modelUsage": {"m": {"contextWindow": 1000}}})
    assert s.snapshot()["context_left"] == "0"


# --------------------------------------------------------------------------
# Transcript. Turns accumulate rather than replacing each other.
# --------------------------------------------------------------------------
def two_turns():
    s = make()
    s.prompt = "first question"
    s.finish_turn("first answer")
    s.prompt = "second question"
    s.finish_turn("second answer")
    return s


def test_turns_accumulate_instead_of_replacing():
    assert len(two_turns().turns) == 2


def test_transcript_reads_oldest_to_newest():
    body = two_turns().render_transcript()
    assert body.index("first answer") < body.index("second answer")


def test_viewport_is_anchored_to_the_newest_output():
    """eww cannot scroll programmatically, so the daemon renders a window over
    the conversation and pins it to the end - that is what "follows" the answer."""
    s = make()
    for i in range(40):
        s.prompt = f"q{i}"
        s.finish_turn(f"answer number {i}")
    assert "answer number 39" in s.render_transcript()
    assert "answer number 0" not in s.render_transcript()


def test_viewport_never_exceeds_its_line_budget():
    s = make()
    for i in range(40):
        s.prompt = f"q{i}"
        s.finish_turn(f"a{i}")
    assert len(s.render_transcript().splitlines()) <= Session.VIEWPORT_LINES


def test_scrolling_back_reveals_older_output():
    s = make()
    for i in range(30):
        s.prompt = f"q{i}"
        s.finish_turn(f"answer number {i}")
    newest = s.render_transcript()
    s.scroll(+12)
    older = s.render_transcript()
    assert older != newest
    assert s.scroll_offset > 0


def test_scroll_is_clamped_at_both_ends():
    s = two_turns()
    s.scroll(-500)
    assert s.scroll_offset == 0
    s.scroll(+500)
    assert s.scroll_offset == s.max_scroll()


def test_a_finished_turn_snaps_back_to_the_newest():
    s = make()
    for i in range(30):
        s.prompt = f"q{i}"
        s.finish_turn(f"a{i}")
    s.scroll(+10)
    assert s.scroll_offset > 0
    s.prompt = "new question"
    s.finish_turn("new answer")
    assert s.scroll_offset == 0
    assert "new answer" in s.render_transcript()


def test_streaming_output_is_visible_before_the_turn_ends():
    s = two_turns()
    body = s.render_transcript(live="partial answer arriving")
    assert "partial answer arriving" in body


def test_scrolled_back_is_reported_to_the_widget():
    s = make()
    for i in range(30):
        s.prompt = f"q{i}"
        s.finish_turn(f"a{i}")
    assert s.snapshot()["scrolled_back"] is False
    s.scroll(+5)
    assert s.snapshot()["scrolled_back"] is True


def test_transcript_includes_the_prompts():
    body = two_turns().render_transcript()
    assert "first question" in body and "second question" in body


def test_transcript_is_empty_before_any_turn():
    s = make()
    assert s.render_transcript() == ""
    assert s.snapshot()["has_transcript"] is False


def test_transcript_is_bounded():
    s = make()
    for i in range(Session.MAX_TURNS + 15):
        s.prompt = f"q{i}"
        s.finish_turn(f"a{i}")
    assert len(s.turns) == Session.MAX_TURNS


def test_an_empty_answer_does_not_create_a_turn():
    s = make()
    s.prompt = "hi"
    s.finish_turn("")
    assert s.turns == []


def test_transcript_markup_is_balanced():
    body = two_turns().render_transcript()
    for tag in ("span", "b", "tt", "i"):
        assert body.count(f"<{tag}") == body.count(f"</{tag}>")


def test_context_fraction_tracks_percentage():
    s = make()
    s.record_usage({"usage": {"input_tokens": 50_000},
                    "modelUsage": {"m": {"contextWindow": 200_000}}})
    snap = s.snapshot()
    assert snap["context_frac"] == 0.25
    assert snap["context_used"] == "50k" and snap["context_total"] == "200k"


# --------------------------------------------------------------------------
# Rewind and per-turn timing.
# --------------------------------------------------------------------------
def three_turns():
    s = make()
    for word in ("alpha", "beta", "gamma"):
        s.prompt = f"say {word}"
        s.finish_turn(word)
    return s


def test_rewind_removes_the_chosen_turn_and_everything_after_it():
    """Rewinding message 1 of 3 leaves message 0 only. The rewound message
    itself goes too - it is meant to end up back in the input looking unsent,
    the way Claude Code does it."""
    s = three_turns()
    kept, undone = s.rewind_to(1)
    assert [t["answer"] for t in kept] == ["alpha"]
    assert len(s.turns) == 1
    assert undone == "say beta"


def test_rewinding_the_first_turn_empties_the_conversation():
    s = three_turns()
    kept, undone = s.rewind_to(0)
    assert kept == [] and s.turns == []
    assert undone == "say alpha"


def test_rewinding_the_last_turn_takes_just_that_one():
    s = three_turns()
    kept, undone = s.rewind_to(2)
    assert len(s.turns) == 2
    assert undone == "say gamma"


def test_rewind_out_of_range_is_ignored():
    s = three_turns()
    assert s.rewind_to(9) == ([], "")
    assert len(s.turns) == 3


def test_rewind_resets_the_viewport():
    s = three_turns()
    s.scroll(+5)
    s.rewind_to(0)
    assert s.scroll_offset == 0


def test_a_turn_records_how_long_it_took():
    import time as _t
    s = make()
    s.started_at = _t.time() - 2.5
    s.prompt = "q"
    s.finish_turn("a")
    assert 2.0 <= s.turns[-1]["took"] <= 3.5


def test_turn_views_expose_the_duration():
    import time as _t
    s = make()
    s.started_at = _t.time() - 1.0
    s.prompt = "q"
    s.finish_turn("a")
    assert s.turn_views()[-1]["took"] > 0


def test_a_turn_without_a_start_stamp_reports_zero():
    s = make()
    s.prompt = "q"
    s.finish_turn("a")
    assert s.turns[-1]["took"] == 0.0


def test_limit_percentage_is_time_remaining_in_the_window():
    import time as _t
    s = make()
    s.limits["five_hour"] = int(_t.time()) + int(2.5 * 3600)
    assert 49 <= s.limit_pct("five_hour") <= 51


def test_limit_percentage_without_data_is_zero():
    assert make().limit_pct("five_hour") == 0


# --- rewind replaces the tab, it does not add one ----------------------------

def _manager():
    from archpilot.session import SessionManager
    return SessionManager({})


def test_rewind_keeps_a_single_tab():
    """The bug: rewinding called new(), which appends. Instead of the
    conversation going back, a second tab appeared beside the untouched
    original - which is why it looked like rewind did nothing."""
    from archpilot.session import Session
    manager = _manager()
    old = manager.new(mode="ask", model="haiku")
    assert len(manager.tabs()) == 1

    fresh = Session.create(mode="ask", model="haiku")
    manager.replace_current(fresh)

    assert len(manager.tabs()) == 1
    assert manager.current is fresh
    assert old.id not in manager.sessions


def test_rewind_keeps_its_position_among_other_tabs():
    from archpilot.session import Session
    manager = _manager()
    first = manager.new(mode="ask", model="haiku")
    middle = manager.new(mode="ask", model="haiku")
    last = manager.new(mode="ask", model="haiku")
    manager.current = middle

    fresh = Session.create(mode="ask", model="haiku")
    manager.replace_current(fresh)

    assert [s.id for s in manager.tabs()] == [first.id, fresh.id, last.id]


def test_replacing_with_no_current_session_still_registers_it():
    from archpilot.session import Session
    manager = _manager()
    fresh = Session.create(mode="ask", model="haiku")
    manager.replace_current(fresh)
    assert manager.tabs() == [fresh]


# --- closing a specific tab --------------------------------------------------

def test_the_x_on_a_tab_closes_that_tab_not_the_focused_one():
    import asyncio
    manager = _manager()
    first = manager.new(mode="ask", model="haiku")
    second = manager.new(mode="ask", model="haiku")
    third = manager.new(mode="ask", model="haiku")
    manager.current = third

    asyncio.run(manager.close_tab(0))

    assert [s.id for s in manager.tabs()] == [second.id, third.id]
    assert manager.current is third, "closing another tab must not steal focus"


def test_closing_the_focused_tab_moves_focus():
    import asyncio
    manager = _manager()
    manager.new(mode="ask", model="haiku")
    second = manager.new(mode="ask", model="haiku")
    manager.current = second
    asyncio.run(manager.close_tab())
    assert manager.current is not second
    assert len(manager.tabs()) == 1


def test_closing_an_out_of_range_tab_does_nothing():
    import asyncio
    manager = _manager()
    only = manager.new(mode="ask", model="haiku")
    asyncio.run(manager.close_tab(7))
    assert manager.tabs() == [only]
