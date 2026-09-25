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

# H12: the old pattern required a newline after the tag and a bare closing
# fence. Single-line ```` ```archpilot-action cmd``` ```` and trailing-text
# closings (``` done) silently lost the action while strip() left the fence
# visible — button and display disagreed. The closing tail is `[ \t]*`
# (horizontal only): with DOTALL, `.*$` spanned newlines and swallowed
# FOLLOWING fences into one match.
FENCE = re.compile(
    # Two closings: a fence starting a line (multi-line body), or trailing
    # backticks on the same line (single-line ```archpilot-action cmd```).
    r"^[ \t]*```[ \t]*archpilot-action[ \t]*"
    r"(?:\n(.*?)^[ \t]*```[^\n`]*$|[ \t]+([^`\n]+)[ \t]*```[^\n`]*$)",
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
        command = (match.group(1) if match.group(1) is not None
                   else match.group(2) or "").strip()
        if command:
            actions.append(Action(command))
    return actions


def strip(text: str) -> str:
    """The answer with action fences removed, for display."""
    return re.sub(r"\n{3,}", "\n\n", FENCE.sub("", text)).strip()
