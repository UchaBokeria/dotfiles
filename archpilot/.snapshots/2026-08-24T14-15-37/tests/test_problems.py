from archpilot.problems import AUTH, LIMIT, MISSING, MODEL, NETWORK, classify, from_result


def test_logged_out_is_recognised_and_fixable():
    problem = classify("Invalid API key · Please run /login")
    assert problem.kind == AUTH
    assert problem.command == "claude /login"


def test_expired_oauth_reads_as_auth():
    assert classify("OAuth token expired").kind == AUTH


def test_rate_limit_is_not_offered_a_retry():
    problem = classify("rate_limit_error: usage limit reached")
    assert problem.kind == LIMIT and problem.retry is False


def test_network_problems_are_worth_retrying():
    for text in ("Connection refused", "getaddrinfo failed", "503 Service Unavailable"):
        problem = classify(text)
        assert problem.kind == NETWORK, text
        assert problem.retry is True


def test_unknown_model():
    assert classify("model not found: claude-nope").kind == MODEL


def test_missing_binary():
    assert classify("command not found: claude").kind == MISSING


def test_a_healthy_turn_has_no_problem():
    assert classify("Here is your answer.") is None
    assert classify("") is None
    assert from_result({"is_error": False, "result": "all good"}) is None


def test_is_error_without_a_recognised_cause_still_surfaces():
    problem = from_result({"is_error": True, "result": "something odd happened"})
    assert problem is not None
    assert "something odd" in problem.detail


def test_stderr_is_considered_too():
    """The useful text is often only on the child's stderr."""
    problem = from_result({"is_error": True, "result": ""},
                          stderr="Error: Invalid API key")
    assert problem.kind == AUTH


def test_a_successful_answer_about_rate_limits_is_not_a_rate_limit():
    """The trap this guards: scanning a good answer for these words fires on
    the answer's own subject. Asking how to handle rate limits must not raise
    a rate-limit warning."""
    good = {"is_error": False, "subtype": "success",
            "result": "To handle a 429 rate limit, back off exponentially..."}
    assert from_result(good) is None


def test_stderr_chatter_on_a_healthy_turn_is_ignored():
    assert from_result({"is_error": False, "subtype": "success", "result": "fine"},
                       stderr="warning: connection reset while fetching a mirror") is None


def test_an_error_subtype_counts_as_failure_even_without_the_flag():
    from archpilot.problems import from_result as fr
    problem = fr({"subtype": "error_max_turns", "result": "hit the turn cap"})
    assert problem is not None


def test_the_real_result_shape_from_a_failed_run_is_classified():
    """Observed live: the CLI sets is_error True while subtype stays "success",
    so subtype alone must never be the test for health."""
    problem = from_result(
        {"is_error": True, "subtype": "success",
         "result": "There's an issue with the selected model (xyz)."},
        stderr='[claude-code:unrecognized_model] {"model":"xyz"}')
    assert problem.kind == "model"


def test_the_first_matching_rule_wins():
    """Auth is checked before the generic network rule so a 401 mentioning a
    connection still reads as a sign-in problem."""
    assert classify("unauthorized while connecting").kind == AUTH


def test_problem_serialises_for_the_widget():
    payload = classify("Invalid API key").as_dict()
    assert set(payload) == {"kind", "title", "detail", "command", "retry"}


# --- phrasings taken from the installed CLI, not invented --------------------

def test_the_real_unrecognized_model_line_is_understood():
    """Observed on stderr from a real run with a bad --model. The guessed
    patterns ("model not found") did not match it."""
    from archpilot.problems import MODEL
    line = '[claude-code:unrecognized_model] {"model":"xyz","query_source":"sdk"}'
    assert classify(line).kind == MODEL


def test_a_revoked_oauth_token_needs_a_login():
    assert classify("OAuth token has been revoked").kind == AUTH


def test_the_cli_error_type_strings_map_to_something_useful():
    """These are the literal error types in the CLI binary."""
    from archpilot.problems import LIMIT, NETWORK
    assert classify("authentication_error").kind == AUTH
    assert classify("rate_limit_error").kind == LIMIT
    assert classify("overloaded_error").kind == NETWORK
    assert classify("not_found_error").kind == "model"
