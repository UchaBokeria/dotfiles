"""Extract suggested commands from an assistant answer.

Convention over structured output: the system prompt asks for a fenced
```archpilot-action block when (and only when) the answer implies a command
worth running. Parsing a fence costs nothing when the model doesn't emit one,
and degrades to plain prose rather than an error - whereas forcing a JSON
schema on every turn would tax informational answers too ("what's the weather"
should not pay for an actions array it will never use).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FENCE = re.compile(
    r"^[ \t]*```[ \t]*archpilot-action[ \t]*\n(.*?)^[ \t]*```[ \t]*$",
    re.DOTALL | re.MULTILINE,
)


@dataclass(frozen=True)
class Action:
    command: str

    @property
    def label(self) -> str:
        """Short single-line label for the widget button."""
        flat = " ".join(self.command.split())
        return flat if len(flat) <= 60 else flat[:57] + "..."


def parse(text: str) -> list[Action]:
    """Return the suggested actions in `text`, in order.

    Blank fences are dropped. Multi-line bodies are kept verbatim - the command
    still passes through policy before it can run, so parsing stays permissive
    and the gate stays strict.
    """
    actions = []
    for match in FENCE.finditer(text):
        command = match.group(1).strip()
        if command:
            actions.append(Action(command))
    return actions


def strip(text: str) -> str:
    """The answer with action fences removed, for display."""
    return re.sub(r"\n{3,}", "\n\n", FENCE.sub("", text)).strip()
