"""Newline-delimited JSON protocol spoken over the daemon's unix socket.

Deliberately dumb: one JSON object per line, no framing beyond "\n". That keeps
eww's `deflisten` able to consume the event stream directly, and keeps the
daemon frontend-agnostic - eww is just the first client.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

# --- client -> daemon ---------------------------------------------------
OP_PROMPT = "prompt"        # {text, session?, mode?, model?, attachments?}
OP_SUBSCRIBE = "subscribe"  # {eww?: bool} -> stream of events
OP_APPROVE = "approve"      # {id, decision: allow|deny}
OP_TOGGLE = "toggle"
OP_CANCEL = "cancel"        # {session?}
OP_SESSIONS = "sessions"    # -> index of Claude Code sessions
OP_STATE = "state"          # -> one state snapshot, then close
OP_TAB = "tab"              # {action: new|next|prev|close|select, index}
OP_DRAFT = "draft"          # {text} keep the unsent input across a toggle
OP_REWIND = "rewind"        # {index} - continue from that message onward
OP_PICKER = "picker"        # {kind: history|sessions} - daemon runs rofi
OP_SCROLL = "scroll"        # {delta} lines; positive = back in time
OP_WIDGET = "widget"        # {action: hide|show} - ask the DAEMON to move it
OP_NEW = "new"              # drop the current session, start fresh
OP_SET = "set"              # {field: mode|model|effort, value|cycle}
OP_RUN_ACTION = "run_action"  # {index} run a suggested action by position
OP_ATTACH = "attach"        # {paths[]} staged for the next prompt
OP_DETACH = "detach"        # {path} drop one staged attachment
OP_OPEN_SESSION = "open_session"  # {session_id, cwd} reopen a past chat
OP_RENAME = "rename"        # {session_id, title} name a past chat
OP_ASK_PERMISSION = "ask_permission"  # from hooks/pretooluse.py
OP_ASK_PASSWORD = "ask_password"    # from hooks/askpass.py
OP_PASSWORD = "password"            # {value} answer from the widget

# --- daemon -> client ---------------------------------------------------
EV_DELTA = "delta"                  # {text} streaming assistant text
EV_TURN_END = "turn_end"            # {text, actions[]}
EV_APPROVAL_REQUEST = "approval_request"  # {id, command, reason}
EV_STATE = "state"                  # full widget state snapshot
EV_PASSWORD_REQUEST = "password_request"  # {prompt}
EV_ERROR = "error"                  # {message}
EV_RESTORE_INPUT = "restore_input"  # {text} put it back in the input, unsent


def encode(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def decode(line: bytes | str) -> dict[str, Any]:
    if isinstance(line, bytes):
        line = line.decode("utf-8", errors="replace")
    return json.loads(line)


async def read_lines(reader: asyncio.StreamReader):
    """Yield decoded JSON objects, skipping anything unparseable.

    A malformed line is skipped rather than fatal: one bad frame from a client
    must not take the daemon's connection handler down.
    """
    while True:
        raw = await reader.readline()
        if not raw:
            return
        raw = raw.strip()
        if not raw:
            continue
        try:
            yield decode(raw)
        except json.JSONDecodeError:
            continue
