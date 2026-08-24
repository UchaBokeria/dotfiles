"""Render a Markdown-ish answer as Pango markup for the eww label.

eww's label exposes a `markup` property, which is the only styling channel
available here - GTK labels have no Markdown renderer. Converting the common
inline forms is the difference between reading an answer and reading its
source, and it costs one regex pass.

Anything not understood is left as literal text, so a failure mode is "plain
but correct", never "broken markup". Pango is strict: an unbalanced tag makes
GTK drop the whole string, so escaping runs first and unmatched syntax is left
escaped rather than half-converted.
"""

from __future__ import annotations

import html
import re

_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?!\*)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*$", re.MULTILINE)
_BULLET = re.compile(r"^\s{0,3}[-*+]\s+", re.MULTILINE)


#: Bare http(s) links. Trailing punctuation is left out of the match so a URL
#: at the end of a sentence does not swallow the full stop. Runs AFTER escaping,
#: so what it sees is already Pango-safe text.
_URL = re.compile(r"(?<![\w>\"'])(https?://[^\s<>\"']+[^\s<>\"'.,;:!?)\]}])")


def linkify(escaped: str) -> str:
    """Wrap bare URLs in Pango anchors so they can be clicked.

    Input must already be escaped: this inserts markup, so running it on raw
    text would let a URL's own characters open tags Pango cannot parse.
    """
    def anchor(match: re.Match[str]) -> str:
        url = match.group(1)
        # html.escape(quote=False) leaves double quotes alone, and an
        # unescaped quote inside href="" would end the attribute early.
        return f'<a href="{url.replace(chr(34), "&quot;")}">{url}</a>'

    return _URL.sub(anchor, escaped)


def to_pango(text: str) -> str:
    if not text:
        return ""

    # Escape first. Every tag inserted after this point is one we control, so
    # user text can never open a tag Pango will choke on.
    out = html.escape(text, quote=False)

    blocks: list[str] = []

    def stash(match: re.Match[str]) -> str:
        blocks.append(match.group(1).rstrip("\n"))
        return f"\x00{len(blocks) - 1}\x00"

    out = _FENCE.sub(stash, out)

    out = _HEADING.sub(r"<b>\1</b>", out)
    out = _BOLD.sub(r"<b>\1</b>", out)
    out = _ITALIC.sub(r"<i>\1</i>", out)
    out = _INLINE_CODE.sub(r'<tt>\1</tt>', out)
    out = _BULLET.sub("  \N{BULLET} ", out)
    out = linkify(out)

    for index, block in enumerate(blocks):
        out = out.replace(f"\x00{index}\x00", f'<tt>{block}</tt>')

    return out.strip()


_TAG = re.compile(r"<[^>]+>")


def wrap_pango(markup: str, width: int) -> str:
    """Hard-wrap Pango markup at `width` visible columns.

    eww 0.5.0's label ignores :wrap, :limit_width and :show_truncated - verified
    by rendering all four combinations, which ellipsised identically. So the
    wrapping has to happen here, where we still know the text.

    Only visible characters count toward the column budget; markup tags are
    zero-width. Breaks land on spaces and never inside a tag. Tags may span the
    inserted newlines, which Pango allows, so nothing needs closing and
    reopening.
    """
    if not markup:
        return ""

    lines: list[str] = []
    for paragraph in markup.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue

        current: list[str] = []
        column = 0
        # Split into tags and the words between them, keeping both.
        for piece in re.split(r"(<[^>]+>|\s+)", paragraph):
            if not piece:
                continue
            if _TAG.fullmatch(piece):
                current.append(piece)  # zero visible width
                continue
            if piece.isspace():
                if current:
                    current.append(" ")
                    column += 1
                continue
            if column + len(piece) > width and column > 0:
                lines.append("".join(current).rstrip())
                current, column = [], 0
            current.append(piece)
            column += len(piece)
        lines.append("".join(current).rstrip())

    return "\n".join(lines)


def wrap_plain(text: str, width: int) -> str:
    """Hard-wrap plain text (no markup) at `width` columns.

    Used for the pending-approval command: a command you cannot read in full is
    a command you cannot meaningfully approve, so it must never be ellipsised.
    Long unbroken tokens (paths, URLs) are split rather than allowed to overflow.
    """
    if not text:
        return ""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            while len(word) > width:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:width])
                word = word[width:]
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= width:
                current += " " + word
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return "\n".join(lines)
