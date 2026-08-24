"""Is Claude Code signed in? Answered without spending a turn.

Discovering you are logged out by sending a prompt and getting nothing back is
the worst version of this. Claude Code keeps its subscription token in
`~/.claude/.credentials.json`, so the widget can check before the user types.

The distinction that matters: `expiresAt` covers the short-lived ACCESS token
and lapsing is completely normal - the CLI refreshes it silently. Only
`refreshTokenExpiresAt` passing means a real re-login. Treating the first as a
problem would nag the user every hour for something already handled.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from .problems import AUTH, MISSING, Problem

CREDENTIALS = Path.home() / ".claude" / ".credentials.json"

SIGNED_OUT = Problem(
    AUTH, "Not signed in",
    "Claude Code has no subscription credentials yet.", "claude /login")

EXPIRED = Problem(
    AUTH, "Sign-in expired",
    "Your Claude login has run out and needs renewing.", "claude /login")

NO_BINARY = Problem(
    MISSING, "Claude Code not found",
    "The `claude` command is not on PATH, so nothing can run.", "")


def _credentials(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def check(path: Path | None = None, *, binary: str = "claude",
          now: float | None = None) -> Problem | None:
    """The reason the next turn would fail, or None if it should work."""
    if not shutil.which(binary):
        return NO_BINARY

    path = path or CREDENTIALS
    oauth = _credentials(path).get("claudeAiOauth") or {}
    if not oauth.get("accessToken"):
        return SIGNED_OUT

    # Milliseconds in the file; seconds in `now`.
    refresh_expiry = oauth.get("refreshTokenExpiresAt")
    if refresh_expiry and (now or time.time()) >= refresh_expiry / 1000:
        return EXPIRED
    return None
