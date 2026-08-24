import json

import pytest

from archpilot import auth
from archpilot.problems import AUTH, MISSING

HOUR = 3600
NOW = 1_000_000.0


def creds(tmp_path, **oauth):
    path = tmp_path / ".credentials.json"
    path.write_text(json.dumps({"claudeAiOauth": oauth} if oauth else {}))
    return path


def test_a_healthy_login_reports_no_problem(tmp_path):
    path = creds(tmp_path, accessToken="tok",
                 expiresAt=int((NOW + HOUR) * 1000),
                 refreshTokenExpiresAt=int((NOW + 30 * 24 * HOUR) * 1000))
    assert auth.check(path, now=NOW) is None


def test_an_expired_access_token_is_not_a_problem(tmp_path):
    """The CLI refreshes it silently. Flagging this would nag hourly for
    something already handled."""
    path = creds(tmp_path, accessToken="tok",
                 expiresAt=int((NOW - HOUR) * 1000),
                 refreshTokenExpiresAt=int((NOW + 30 * 24 * HOUR) * 1000))
    assert auth.check(path, now=NOW) is None


def test_an_expired_refresh_token_does_need_a_login(tmp_path):
    path = creds(tmp_path, accessToken="tok",
                 refreshTokenExpiresAt=int((NOW - HOUR) * 1000))
    problem = auth.check(path, now=NOW)
    assert problem.kind == AUTH
    assert problem.command == "claude /login"


def test_no_credentials_file_at_all(tmp_path):
    assert auth.check(tmp_path / "nope.json", now=NOW).kind == AUTH


def test_a_corrupt_credentials_file_reads_as_signed_out(tmp_path):
    """Better to offer a login than to crash the daemon on malformed JSON."""
    path = tmp_path / ".credentials.json"
    path.write_text("{not json")
    assert auth.check(path, now=NOW).kind == AUTH


def test_credentials_without_the_subscription_block(tmp_path):
    """MCP server tokens live in the same file and prove nothing about the
    subscription login."""
    path = tmp_path / ".credentials.json"
    path.write_text(json.dumps({"mcpOAuth": {"some-server": {"accessToken": "x"}}}))
    assert auth.check(path, now=NOW).kind == AUTH


def test_a_missing_binary_outranks_the_credential_check(tmp_path):
    """Without `claude` on PATH, whether you are signed in is moot."""
    path = creds(tmp_path, accessToken="tok")
    problem = auth.check(path, binary="definitely-not-a-real-binary-xyz", now=NOW)
    assert problem.kind == MISSING


def test_a_missing_expiry_is_trusted_rather_than_assumed_stale(tmp_path):
    """Older credential files have no refresh expiry; assuming the worst would
    log the user out for no reason."""
    path = creds(tmp_path, accessToken="tok")
    assert auth.check(path, now=NOW) is None
