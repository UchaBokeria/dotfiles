"""Engine abstraction.

Three implementations, one surface (start / send / events / cancel / stop):
  claude_code.ClaudeCodeEngine - one long-lived `claude -p` over stream-json,
                                  on the user's Claude subscription
  codex.CodexEngine            - one `codex exec --json` per turn, resumed by
                                  thread id, on the user's ChatGPT sign-in
  opencode.OpencodeEngine      - one `opencode run --format json` per turn,
                                  resumed by session id, on metered Meta keys
                                  (deliberate exception to the rule below)

The daemon holds whichever the session asks for and never needs to know which.
Nothing in this package may import an Anthropic or OpenAI SDK - that would
reintroduce the metered billing path this project exists to avoid.
"""

from .claude_code import ClaudeCodeEngine, EngineEvent
from .codex import CodexEngine
from .opencode import OpencodeEngine

__all__ = ["ClaudeCodeEngine", "CodexEngine", "OpencodeEngine", "EngineEvent"]
