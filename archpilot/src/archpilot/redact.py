"""Best-effort secret scrubbing for text ArchPilot re-sends or re-displays.

Scope is deliberate: Claude/Codex own their transcript files and those are
out of reach. What IS in reach:

1. `replay_text()` — old turns re-sent to a (possibly different-vendor)
   engine on rewind/switch. A pasted password must not silently cross that
   boundary a second time.
2. History/session display labels — the GTK search rows and picker rows show
   prompt text on screen; scrubbed display avoids shoulder-surfing secrets.
3. Window-title context — browser tab titles routinely contain tokens
   (`?token=…`, SSO codes); the query part never helps the model.

This is pattern-based, not a guarantee. Anything it misses still lands where
the user originally sent it. The placeholder keeps line structure so wrapped
layouts do not shift.
"""

from __future__ import annotations

import re

PLACEHOLDER = "…redacted…"

#: `key = value`, `key: value`, `key=value` for the usual secret names.
_KEY_VALUE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|auth[_-]?token|"
    r"access[_-]?token|refresh[_-]?token|private[_-]?key|client[_-]?secret|"
    r"session[_-]?key)\b(\s*[:=]\s*)([\"']?)([^\"'\s,}]+)(\3)")

#: Bare long tokens: sk-…, ghp_…, xox*, AKIA…, eyJ… (JWT), LLM_… (Meta keys).
_BARE_TOKENS = re.compile(
    r"\b(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|gho_[A-Za-z0-9]{8,}|"
    r"xox[bap]-[A-Za-z0-9-]{8,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|"
    r"LLM_[A-Za-z0-9_-]{8,})\b")

#: PEM blocks, whole thing including armor lines.
_PEM = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL)

#: URL query strings: `?token=abc&next=/x` → `?…`. Applied to window titles
#: and bare URLs; the path usually matters, the query rarely does.
_QUERY = re.compile(r"\?[^\s\"'<>]*")


def scrub(text: str) -> str:
    """Replace likely secrets with a placeholder. Idempotent."""
    if not text:
        return text
    out = _PEM.sub(PLACEHOLDER, text)
    out = _KEY_VALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}{PLACEHOLDER}", out)
    out = _BARE_TOKENS.sub(PLACEHOLDER, out)
    return out


def scrub_url_query(text: str) -> str:
    """Strip URL query strings (tokens, SSO codes) from titles/URLs."""
    if not text:
        return text
    return _QUERY.sub("?…", text)
