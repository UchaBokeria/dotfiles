"""Decide which context is worth paying for on a given prompt.

Attaching everything to every turn would be simpler, but terminal scrollback and
system stats are hundreds of tokens each, and on a subscription that is
rate-limit budget spent to answer "how do I write a for loop in fish".

Explicit directives always win over the heuristics.
"""

from __future__ import annotations

import re

DIRECTIVES = {
    ":term": "terminal", ":sys": "system", ":win": "window", ":sess": "sessions",
    # Clipboard and selection are directive-only on purpose - see clipboard.py.
    ":clip": "clipboard", ":sel": "selection",
}

#: Failure language - "this error", "why did it fail" - is the signal that the
#: user is talking about something already on screen. U41: bare deictics
#: (it/this/that/here/command/output) used to match generic prompts like
#: "it is sunny", injecting 120 lines of scrollback into every other turn.
#: Only failure words fire now; `:term` forces it explicitly.
_TERMINAL_HINTS = re.compile(
    r"\b(error|errors|failed|failing|failure|"
    r"traceback|exception|stack ?trace|why did|what went wrong|broke|broken|"
    r"stderr|exit code)\b",
    re.IGNORECASE,
)

_SYSTEM_HINTS = re.compile(
    r"\b(ram|memory|swap|disk|space|storage|full|cpu|load|battery|"
    r"systemd|service|unit|updates?|upgrade|pacman|pacnew|boot|uptime)\b",
    re.IGNORECASE,
)

_SESSION_HINTS = re.compile(
    r"\b(session|sessions|claude|agent|running|still going|done yet|finished)\b",
    re.IGNORECASE,
)


def split_directives(text: str) -> tuple[str, set[str]]:
    """Strip leading `:term` / `:sys` / `:win` / `:sess` directives.

    U23: verbatim when nothing is stripped, so prompt newlines survive.
    """
    wanted: set[str] = set()
    words = text.split()
    stripped = 0
    while words and words[0].lower() in DIRECTIVES:
        wanted.add(DIRECTIVES[words[0].lower()])
        words = words[1:]
        stripped += 1
    if not stripped:
        return text, wanted
    return " ".join(words), wanted


def wanted_for(text: str, explicit: set[str] | None = None) -> set[str]:
    chosen = set(explicit or ())
    if _TERMINAL_HINTS.search(text):
        chosen.add("terminal")
    if _SYSTEM_HINTS.search(text):
        chosen.add("system")
    if _SESSION_HINTS.search(text):
        chosen.add("sessions")
    return chosen
