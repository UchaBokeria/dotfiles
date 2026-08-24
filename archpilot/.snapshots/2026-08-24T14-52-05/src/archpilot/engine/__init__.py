"""Engine abstraction.

v1 has exactly one implementation, `claude_code.ClaudeCodeEngine`, which drives
the Claude Code CLI over stdio using the user's OAuth subscription credentials.

The seam exists so a direct Messages API backend can be slotted in later
without the daemon knowing. Nothing in this package may import an Anthropic
SDK - that would reintroduce the billing path this project exists to avoid.
"""

from .claude_code import ClaudeCodeEngine, EngineEvent

__all__ = ["ClaudeCodeEngine", "EngineEvent"]
