"""Recognising why a turn failed, and what the user can do about it.

A turn can fail for reasons that look identical from the outside - an empty
answer - but need completely different responses. Being logged out is fixable
in ten seconds; a rate limit means come back later; a network drop means retry.
Showing "error" for all three is what makes a tool feel broken.

Each rule maps evidence (stderr, the result event, an exception) to a Problem
carrying a plain sentence and, where one exists, a command that fixes it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

AUTH, LIMIT, NETWORK, MODEL, MISSING, CRASH, UNKNOWN = (
    "auth", "limit", "network", "model", "missing", "crash", "unknown")


@dataclass(frozen=True)
class Problem:
    kind: str
    title: str
    detail: str
    command: str = ""          # something the user can run to fix it
    retry: bool = False        # worth trying the same prompt again

    def as_dict(self) -> dict:
        return {"kind": self.kind, "title": self.title, "detail": self.detail,
                "command": self.command, "retry": self.retry}


#: Ordered: the first match wins, so put the specific patterns first.
RULES: tuple[tuple[re.Pattern[str], Problem], ...] = (
    # Phrasings taken from the installed CLI's own strings, not invented:
    # "Invalid API key", "Please run /login", "Not logged in",
    # "authentication_error", "OAuth token has been revoked".
    (re.compile(r"invalid api key|unauthor|not logged in|please run .?/login|"
                r"authentication_error|oauth token (?:has been |has )?"
                r"(?:expired|revoked|invalid)|no credentials|401",
                re.I),
     Problem(AUTH, "Not signed in",
             "Your Claude session has expired or was never set up.",
             "claude /login")),

    (re.compile(r"rate.?limit|quota exceeded|usage limit|429", re.I),
     Problem(LIMIT, "Rate limit reached",
             "You have used this window's allowance. The header shows when it resets.",
             "", False)),

    (re.compile(r"credit balance|billing|payment required|402", re.I),
     Problem(LIMIT, "Billing problem",
             "The account cannot spend right now - check the plan or balance.",
             "")),

    (re.compile(r"(?:network|connection|socket) (?:error|refused|reset|timed? ?out)|"
                r"temporary failure in name resolution|could not resolve|"
                r"getaddrinfo|econnrefused|502|503|504|overloaded_error|"
                r"overloaded|api_error", re.I),
     Problem(NETWORK, "Cannot reach Claude",
             "The request did not get through. This is usually the network or a "
             "service blip.", "", True)),

    # `unrecognized_model` is what the CLI actually emits on stderr, observed
    # as: [claude-code:unrecognized_model] {"model":"...","query_source":"sdk"}
    (re.compile(r"unrecognized_model|model (?:not found|unavailable)|"
                r"unknown model|not_found_error", re.I),
     Problem(MODEL, "Model unavailable",
             "That model is not available to this account. Try another with "
             "ctrl+tab.", "")),

    (re.compile(r"command not found|no such file or directory.*claude|"
                r"executable .*claude.* not found", re.I),
     Problem(MISSING, "Claude Code not found",
             "The `claude` binary is not on PATH for the daemon.",
             "which claude")),
)


def classify(*evidence: str) -> Problem | None:
    """First problem matching any of the given text, or None if it looks fine."""
    haystack = "\n".join(part for part in evidence if part)
    if not haystack.strip():
        return None
    for pattern, problem in RULES:
        if pattern.search(haystack):
            return problem
    return None


#: Result subtypes that mean the turn failed. `is_error` is the primary signal,
#: but these are checked too so a missing flag cannot hide a failure.
ERROR_SUBTYPES = ("error_during_execution", "error_max_turns", "error_max_budget_usd",
                  "error_max_structured_output_retries")


def failed(result: dict) -> bool:
    return bool(result.get("is_error")) or result.get("subtype") in ERROR_SUBTYPES


def from_result(result: dict, stderr: str = "") -> Problem | None:
    """Classify a finished turn.

    Only a FAILED turn is inspected. Scanning a successful answer for these
    words would fire on the answer's own subject matter - ask "how do I handle
    rate limits?" and the reply, quite correctly full of the phrase, would raise
    a rate-limit warning. Same for stderr, where a tool's harmless chatter can
    mention a connection reset. A panel that cries wolf gets ignored, and then
    it is worthless for the real thing.
    """
    if not failed(result):
        return None
    text = " ".join(str(result.get(key) or "") for key in
                    ("result", "error", "subtype", "api_error_status"))
    problem = classify(text, stderr)
    if problem:
        return problem
    return Problem(CRASH, "That turn failed",
                   (str(result.get("result") or "").strip()
                    or "Claude Code reported an error with no detail."),
                   "", True)
