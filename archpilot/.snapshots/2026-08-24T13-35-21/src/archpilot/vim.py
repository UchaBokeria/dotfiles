"""A vim-mode line editor.

Deliberately free of any GTK import so the whole thing is testable without a
display. The GTK frontend owns a `VimBuffer`, feeds it keys, and renders
`text` / `cursor` / `mode`.

Scope is what a single-line prompt actually needs: motions, operators with
counts, visual selection, registers and undo. There are no windows, marks,
macros or ex commands, and `o`/`O` open nothing - on one line they behave as
append/insert, which is what a prompt box makes of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

#: Lines moved by ctrl-d / ctrl-u. vim uses half the window height;
#: the prompt is a handful of lines tall, so this is that scale.
HALF_PAGE = 5

NORMAL, INSERT, VISUAL, VLINE, VBLOCK = ("normal", "insert", "visual",
                                         "vline", "vblock")

WORD_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^`{|}~"


def _is_word(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _class_of(ch: str) -> int:
    if ch.isspace():
        return 0
    return 1 if _is_word(ch) else 2


@dataclass(frozen=True)
class Snapshot:
    text: str
    cursor: int


@dataclass
class VimBuffer:
    text: str = ""
    cursor: int = 0
    mode: str = NORMAL
    register: str = ""
    anchor: int = 0                      # visual-mode selection origin
    pending: str = ""                    # partial command, e.g. "d" or "2f"
    count: str = ""                      # digits typed before a command
    undo_stack: list = field(default_factory=list)
    #: True once the current insert session has pushed its undo point.
    #: vim undoes a whole insert session at a time, not a letter at a
    #: time - which is what makes `u` after a paste remove the paste
    #: rather than peeling it off one character per keypress.
    _insert_saved: bool = False
    redo_stack: list = field(default_factory=list)
    #: Macro recording: q{reg} starts, q stops, @{reg} replays, @@ repeats.
    registers: dict = field(default_factory=dict)
    recording: str = ""
    #: Pending block insert: (line_starts, column, "I"|"A") while typing after
    #: ctrl-v I/A, replayed onto the other lines when insert mode ends.
    block_edit: tuple | None = None
    recorded: list = field(default_factory=list)
    last_macro: str = ""
    _replaying: bool = False

    # -- helpers ---------------------------------------------------------
    @property
    def last(self) -> int:
        """Rightmost index the cursor may occupy in the current mode.

        Normal mode sits *on* a character, insert mode sits *between* them -
        the classic off-by-one that makes `$` and `A` land differently.
        """
        if self.mode != NORMAL:
            return len(self.text)
        return max(0, len(self.text) - 1)

    def line_start(self, index: int) -> int:
        return self.text.rfind("\n", 0, index) + 1

    def line_end(self, index: int) -> int:
        found = self.text.find("\n", index)
        return len(self.text) if found < 0 else found

    def column(self, index: int) -> int:
        return index - self.line_start(index)

    def line_count(self) -> int:
        return self.text.count("\n") + 1

    def _line_move(self, index: int, delta: int) -> int:
        """Move `delta` lines, keeping the column where possible."""
        col = self.column(index)
        target = index
        for _ in range(abs(delta)):
            if delta > 0:
                end = self.line_end(target)
                if end >= len(self.text):
                    break
                target = end + 1
            else:
                start = self.line_start(target)
                if start == 0:
                    break
                target = self.line_start(start - 1)
        start = self.line_start(target)
        return min(start + col, self.line_end(start))

    def _clamp(self, index: int) -> int:
        return max(0, min(index, self.last))

    def _save(self) -> None:
        self.undo_stack.append(Snapshot(self.text, self.cursor))
        del self.undo_stack[:-100]
        self.redo_stack.clear()

    def _save_insert(self) -> None:
        """One undo point for an entire insert session.

        Saving per keystroke meant undoing a pasted paragraph took as many `u`
        presses as it had characters.
        """
        if not self._insert_saved:
            self._save()
            self._insert_saved = True

    def begin_insert(self) -> None:
        """Open a new insert session, so the next edit starts a new undo unit."""
        self._insert_saved = False

    def insert_text(self, text: str) -> None:
        """Insert a whole string as ONE undo unit - what a paste should be."""
        if not text:
            return
        if self.mode == INSERT:
            self._save_insert()
        else:
            self._save()
        self.text = self.text[:self.cursor] + text + self.text[self.cursor:]
        self.cursor += len(text)

    def snapshot(self) -> dict:
        start, end = self.selection()
        return {
            "text": self.text,
            "cursor": self.cursor,
            "mode": self.mode,
            "pending": self.count + self.pending,
            "sel_start": start,
            "sel_end": end,
        }

    def block_ranges(self) -> list[tuple[int, int]]:
        """The rectangle, as one (start, end) per covered line.

        Columns come from the anchor and the cursor; short lines contribute a
        clipped range rather than being skipped, which is what makes `I` line
        up on ragged text.
        """
        if self.mode != VBLOCK:
            return []
        lo, hi = sorted((self.anchor, self.cursor))
        c1, c2 = sorted((self.column(self.anchor), self.column(self.cursor)))
        ranges = []
        start = self.line_start(lo)
        while start <= self.line_start(hi):
            end_of_line = self.line_end(start)
            left = min(start + c1, end_of_line)
            right = min(start + c2 + 1, end_of_line)
            ranges.append((left, right))
            if end_of_line >= len(self.text):
                break
            start = self.line_start(end_of_line + 1)
        return ranges

    def selection(self) -> tuple[int, int]:
        if self.mode == VBLOCK:
            ranges = self.block_ranges()
            return (ranges[0][0], ranges[-1][1]) if ranges else (0, 0)
        if self.mode not in (VISUAL, VLINE):
            return (0, 0)
        lo, hi = sorted((self.anchor, self.cursor))
        if self.mode == VLINE:
            # Line-wise: snap out to whole lines, including the trailing break
            # so `Vd` closes the gap the way vim does.
            return (self.line_start(lo), min(self.line_end(hi) + 1, len(self.text)))
        return (lo, min(hi + 1, len(self.text)))

    # -- motions ---------------------------------------------------------
    def _word_forward(self, index: int, big: bool) -> int:
        n = len(self.text)
        if index >= n:
            return n
        if big:
            while index < n and not self.text[index].isspace():
                index += 1
        else:
            start_class = _class_of(self.text[index])
            while index < n and _class_of(self.text[index]) == start_class and start_class:
                index += 1
        while index < n and self.text[index].isspace():
            index += 1
        return index

    def _word_back(self, index: int, big: bool) -> int:
        index -= 1
        while index > 0 and self.text[index].isspace():
            index -= 1
        if index <= 0:
            return 0
        if big:
            while index > 0 and not self.text[index - 1].isspace():
                index -= 1
        else:
            cls = _class_of(self.text[index])
            while index > 0 and _class_of(self.text[index - 1]) == cls:
                index -= 1
        return index

    def _word_end(self, index: int, big: bool) -> int:
        n = len(self.text)
        index += 1
        while index < n and self.text[index].isspace():
            index += 1
        if index >= n:
            return max(0, n - 1)
        if big:
            while index + 1 < n and not self.text[index + 1].isspace():
                index += 1
        else:
            cls = _class_of(self.text[index])
            while index + 1 < n and _class_of(self.text[index + 1]) == cls:
                index += 1
        return index

    def _find(self, ch: str, forward: bool, till: bool, count: int) -> int | None:
        index = self.cursor
        for _ in range(count):
            if forward:
                found = self.text.find(ch, index + 1)
            else:
                found = self.text.rfind(ch, 0, index)
            if found < 0:
                return None
            index = found
        if till:
            index += -1 if forward else 1
        return index

    def motion(self, key: str, count: int, arg: str = "",
               for_operator: bool = False) -> int | None:
        """Target index for a motion key, or None if it does not apply.

        `for_operator` skips the normal-mode clamp. As a cursor move, `w` may
        not go past the last character; as the range of `dw` on the final word
        it must reach the end of the line, or a character survives the delete.
        """
        text = self.text
        if key == "h":
            return max(0, self.cursor - count)
        if key in ("l", " "):
            return self._clamp(self.cursor + count)
        if key == "0":
            return self.line_start(self.cursor)
        if key == "^":
            start = self.line_start(self.cursor)
            line = text[start:self.line_end(self.cursor)]
            return start + (len(line) - len(line.lstrip()))
        if key == "$":
            end = self.line_end(self.cursor)
            return end if for_operator or self.mode != NORMAL else max(self.line_start(self.cursor), end - 1)
        if key in ("j", "k"):
            return self._line_move(self.cursor, count if key == "j" else -count)
        if key in ("w", "W"):
            index = self.cursor
            for _ in range(count):
                index = self._word_forward(index, key == "W")
            return index if for_operator else min(index, self.last)
        if key in ("b", "B"):
            index = self.cursor
            for _ in range(count):
                index = self._word_back(index, key == "B")
            return index
        if key in ("e", "E"):
            index = self.cursor
            for _ in range(count):
                index = self._word_end(index, key == "E")
            return index if for_operator else min(index, self.last)
        if key in ("f", "F", "t", "T") and arg:
            return self._find(arg, key in ("f", "t"), key in ("t", "T"), count)
        return None

    # -- editing ---------------------------------------------------------
    def _delete_range(self, start: int, end: int, into_register: bool = True) -> None:
        start, end = max(0, min(start, end)), min(len(self.text), max(start, end))
        if start == end:
            return
        self._save()
        if into_register:
            self.register = self.text[start:end]
        self.text = self.text[:start] + self.text[end:]
        self.cursor = self._clamp(start)

    def _apply_operator(self, operator: str, start: int, end: int) -> None:
        if operator == "y":
            self.register = self.text[min(start, end):max(start, end)]
            self.cursor = self._clamp(min(start, end))
            return
        self._delete_range(start, end)
        if operator == "c":
            self._insert_saved = False
            self.mode = INSERT
            self.cursor = self._clamp(min(start, end))

    def undo(self) -> None:
        if not self.undo_stack:
            return
        self.redo_stack.append(Snapshot(self.text, self.cursor))
        state = self.undo_stack.pop()
        self.text, self.cursor = state.text, self._clamp(state.cursor)

    def redo(self) -> None:
        if not self.redo_stack:
            return
        self.undo_stack.append(Snapshot(self.text, self.cursor))
        state = self.redo_stack.pop()
        self.text, self.cursor = state.text, self._clamp(state.cursor)

    # -- key entry -------------------------------------------------------
    def feed(self, key: str) -> str:
        """Consume one keypress. Returns an action for the frontend, or "".

        Actions: "submit", "close", "" (nothing for the caller to do).
        `key` is a single character, or a name like "escape"/"backspace"/
        "enter"/"ctrl-r"/"ctrl-u"/"ctrl-w".
        """
        # Record before dispatch so the macro captures what was actually typed,
        # but never while replaying - that would nest a macro inside itself.
        if self.recording and not self._replaying:
            self.recorded.append(key)
        if self.mode == INSERT:
            return self._feed_insert(key)
        return self._feed_normal(key)

    def play(self, register: str) -> str:
        """Replay a recorded macro. Returns the last action it produced."""
        keys = self.registers.get(register or self.last_macro, [])
        if not keys or self._replaying:
            return ""
        self.last_macro = register or self.last_macro
        self._replaying = True
        action = ""
        try:
            for key in list(keys)[:500]:      # a bounded replay cannot hang
                action = self.feed(key) or action
        finally:
            self._replaying = False
        return action

    def _feed_insert(self, key: str) -> str:
        if key == "escape":
            self._finish_block_edit()
            self._insert_saved = False        # this session's undo unit is closed
            self.mode = NORMAL
            self.cursor = self._clamp(self.cursor - 1)
            return ""
        if key == "enter":
            return "submit"
        if key == "newline":       # shift+enter: a literal line break
            self._save_insert()
            self.text = self.text[:self.cursor] + "\n" + self.text[self.cursor:]
            self.cursor += 1
            return ""
        if key == "backspace":
            if self.cursor > 0:
                self._save_insert()
                self.text = self.text[: self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
            return ""
        if key == "ctrl-u":
            self._delete_range(0, self.cursor, into_register=False)
            return ""
        if key == "ctrl-w":
            self._delete_range(self._word_back(self.cursor, False), self.cursor, False)
            return ""
        if key in ("left", "right", "home", "end"):
            self.cursor = {"left": max(0, self.cursor - 1),
                           "right": min(len(self.text), self.cursor + 1),
                           "home": 0, "end": len(self.text)}[key]
            return ""
        if len(key) == 1:
            self._save_insert()
            self.text = self.text[: self.cursor] + key + self.text[self.cursor:]
            self.cursor += 1
        return ""

    def _finish_block_edit(self) -> None:
        """Replicate what was typed on the first line onto the rest of the block."""
        if not self.block_edit:
            return
        points, _count, _kind = self.block_edit
        self.block_edit = None
        typed = self.text[points[0]:self.cursor]
        if not typed or len(points) < 2:
            return
        grown = len(typed)
        # Later lines have shifted by everything inserted before them.
        for index, point in enumerate(points[1:], start=1):
            at = point + grown * index
            if at > len(self.text):
                continue
            self.text = self.text[:at] + typed + self.text[at:]

    def _reset_pending(self) -> None:
        self.pending = ""
        self.count = ""

    def _feed_normal(self, key: str) -> str:
        # A pending operator or find waiting for its argument.
        if self.pending:
            return self._resolve_pending(key)

        if key == "escape":
            # Esc in normal mode is a no-op, as in vim. Closing on it made the
            # window vanish whenever you tapped Esc twice out of habit.
            if self.mode in (VISUAL, VLINE, VBLOCK):
                self.mode = NORMAL
            self._reset_pending()
            return ""



        if key.isdigit() and not (key == "0" and not self.count):
            self.count += key
            return ""

        count = int(self.count or 1)

        if key == "enter":
            self._reset_pending()
            return "submit"

        # motions
        if key in ("h", "l", "0", "^", "$", "w", "W", "b", "B", "e", "E", " ", "j", "k"):
            target = self.motion(key, count)
            if target is not None:
                self.cursor = self._clamp(target)
            self._reset_pending()
            return ""

        # In visual mode an operator applies to the selection right away.
        # Falling through to the pending-operator path made `vwd` wait for a
        # motion that never came, which is why visual mode appeared dead.
        if self.mode == VBLOCK and key in ("d", "x", "c", "s", "y", "I", "A"):
            return self._block_operator(key)

        if self.mode in (VISUAL, VLINE) and key in ("d", "x", "c", "s", "y"):
            start, end = self.selection()
            self.mode = NORMAL
            self._apply_operator("y" if key == "y" else
                                 "c" if key in ("c", "s") else "d", start, end)
            self._reset_pending()
            return ""

        if key == "q":
            if self.recording:
                # The trailing q is not part of the macro.
                self.registers[self.recording] = self.recorded[:-1]
                self.recording, self.recorded = "", []
                return ""
            self.pending = "q"
            return ""

        if key == "@":
            self.pending = "@"
            return ""

        if key in ("f", "F", "t", "T", "d", "c", "y", "g", "r", "Z"):
            self.pending = key
            return ""

        handler = {
            "i": self._enter_insert, "a": self._append, "I": self._insert_start,
            "A": self._append_end, "o": self._open_below, "O": self._open_above,
            "x": self._delete_char, "X": self._backspace_char,
            "s": self._substitute_char, "S": self._substitute_line,
            "D": self._delete_to_end, "C": self._change_to_end, "Y": self._yank_all,
            "p": self._paste_after, "P": self._paste_before,
            "u": self._undo_key, "ctrl-r": self._redo_key,
            "v": self._enter_visual, "V": self._enter_vline, "G": self._goto_end,
            "ctrl-v": self._enter_vblock,
            "ctrl-d": self._half_page_down, "ctrl-u": self._half_page_up,
            "J": self._join_lines, "~": self._toggle_case,
        }.get(key)
        if handler is not None:
            result = handler(count)
            self._reset_pending()
            return result or ""

        self._reset_pending()
        return ""

    def _resolve_pending(self, key: str) -> str:
        # vim accepts the count on either side of the operator: `2dw` and `d2w`
        # are the same edit. Digits arriving after the operator have to keep
        # accumulating rather than being treated as a motion.
        if key.isdigit() and not (key == "0" and not self.count):
            self.count += key
            return ""

        operator, self.pending = self.pending, ""
        count = int(self.count or 1)
        self.count = ""

        if operator == "Z":
            # ZZ closes, as in vim. A bare Z followed by anything else does not.
            return "close" if key == "Z" else ""

        if operator == "q":
            self.recording = key
            self.recorded = []
            return ""

        if operator == "@":
            return self.play("" if key == "@" else key)

        if operator == "r":
            if len(key) == 1 and self.cursor < len(self.text):
                self._save()
                self.text = (self.text[:self.cursor] + key
                             + self.text[self.cursor + 1:])
            return ""

        if operator in ("f", "F", "t", "T"):
            target = self.motion(operator, count, arg=key)
            if target is not None:
                self.cursor = self._clamp(target)
            return ""

        if operator == "g":
            if key == "g":
                self.cursor = 0
            elif key == "t":
                return "tab-next"
            elif key == "T":
                return "tab-prev"
            return ""

        # dd / cc / yy operate on the whole line
        if key == operator:
            start = self.line_start(self.cursor)
            end = self.line_end(self.cursor)
            if operator == "y":
                self.register = self.text[start:end]
                return ""
            if operator == "c":
                # cc keeps the line, empties it - that is the vim behaviour.
                self._delete_range(start, end)
                self._insert_saved = False
                self.mode = INSERT
                return ""
            # dd takes the trailing newline with it, or the leading one on the
            # last line, so the surrounding lines close up.
            drop_end = min(end + 1, len(self.text))
            if drop_end == end and start > 0:
                start -= 1
            self._delete_range(start, drop_end)
            self.cursor = self._clamp(self.line_start(self.cursor))
            return ""

        if key in ("f", "F", "t", "T"):
            # operator + find needs one more key; keep waiting
            self.pending = operator + key
            return ""
        if len(operator) == 2 and operator[1] in ("f", "F", "t", "T"):
            target = self.motion(operator[1], count, arg=key)
            if target is not None:
                end = target + 1 if operator[1] in ("f", "t") else target
                self._apply_operator(operator[0], self.cursor, end)
            return ""

        target = self.motion(key, count, for_operator=True)
        if target is None:
            return ""
        start, end = self.cursor, target
        # `e` and `f` are inclusive of the character they land on.
        if key in ("e", "E"):
            end += 1
        if end < start:
            start, end = end, start
        self._apply_operator(operator, start, end)
        return ""

    # -- normal-mode commands -------------------------------------------
    def _enter_insert(self, _count: int) -> str:
        self._insert_saved = False
        self.mode = INSERT
        return ""

    def _append(self, _count: int) -> str:
        self._insert_saved = False
        self.mode = INSERT
        self.cursor = min(len(self.text), self.cursor + 1)
        return ""

    def _insert_start(self, _count: int) -> str:
        self._insert_saved = False
        self.mode = INSERT
        start = self.line_start(self.cursor)
        line = self.text[start:self.line_end(self.cursor)]
        self.cursor = start + (len(line) - len(line.lstrip()))
        return ""

    def _append_end(self, _count: int) -> str:
        self._insert_saved = False
        self.mode = INSERT
        self.cursor = self.line_end(self.cursor)
        return ""

    def _open_below(self, _count: int) -> str:
        """Open a line below and start typing on it."""
        self._save()
        end = self.line_end(self.cursor)
        self.text = self.text[:end] + "\n" + self.text[end:]
        self._insert_saved = False
        self.mode = INSERT
        self.cursor = end + 1
        return ""

    def _open_above(self, _count: int) -> str:
        self._save()
        start = self.line_start(self.cursor)
        self.text = self.text[:start] + "\n" + self.text[start:]
        self._insert_saved = False
        self.mode = INSERT
        self.cursor = start
        return ""

    def _delete_char(self, count: int) -> str:
        self._delete_range(self.cursor, self.cursor + count)
        return ""

    def _backspace_char(self, count: int) -> str:
        self._delete_range(max(0, self.cursor - count), self.cursor)
        return ""

    def _substitute_char(self, count: int) -> str:
        self._delete_range(self.cursor, self.cursor + count)
        self._insert_saved = False
        self.mode = INSERT
        return ""

    def _substitute_line(self, _count: int) -> str:
        self._save()
        self.register = self.text
        self.text, self.cursor, self.mode = "", 0, INSERT
        return ""

    def _delete_to_end(self, _count: int) -> str:
        self._delete_range(self.cursor, self.line_end(self.cursor))
        return ""

    def _change_to_end(self, _count: int) -> str:
        self._delete_range(self.cursor, self.line_end(self.cursor))
        self._insert_saved = False
        self.mode = INSERT
        return ""

    def _yank_all(self, _count: int) -> str:
        self.register = self.text
        return ""

    def _paste_after(self, count: int) -> str:
        if not self.register:
            return ""
        self._save()
        at = min(len(self.text), self.cursor + 1)
        self.text = self.text[:at] + self.register * count + self.text[at:]
        self.cursor = self._clamp(at + len(self.register) * count - 1)
        return ""

    def _paste_before(self, count: int) -> str:
        if not self.register:
            return ""
        self._save()
        self.text = self.text[: self.cursor] + self.register * count + self.text[self.cursor:]
        self.cursor = self._clamp(self.cursor + len(self.register) * count - 1)
        return ""

    def _undo_key(self, _count: int) -> str:
        self.undo()
        return ""

    def _redo_key(self, _count: int) -> str:
        self.redo()
        return ""

    def _enter_visual(self, _count: int) -> str:
        self.mode = VISUAL
        self.anchor = self.cursor
        return ""

    def _half_page(self, direction: int) -> str:
        """Move the cursor half a screen, as ctrl-d / ctrl-u do in vim.

        The buffer has no idea how tall the view is, so it moves by lines and
        lets the frontend scroll to wherever the cursor ended up. That keeps
        the cursor and the viewport from ever disagreeing.
        """
        column = self.cursor - self.line_start(self.cursor)
        for _ in range(HALF_PAGE):
            line = (self.line_start(self.cursor) if direction < 0
                    else self.line_end(self.cursor))
            if direction < 0:
                if line == 0:
                    break
                self.cursor = self.line_start(line - 1)
            else:
                if line >= len(self.text):
                    break
                self.cursor = line + 1
        start = self.line_start(self.cursor)
        self.cursor = min(start + column, self.line_end(start))
        return ""

    def _half_page_down(self, _count: int) -> str:
        return self._half_page(1)

    def _half_page_up(self, _count: int) -> str:
        return self._half_page(-1)

    def _enter_vblock(self, _count: int) -> str:
        self.mode = VBLOCK
        self.anchor = self.cursor
        return ""

    def _block_operator(self, key: str) -> str:
        """d/x/c/y over the rectangle, or I/A to type on every line at once."""
        ranges = self.block_ranges()
        self.mode = NORMAL
        self._reset_pending()
        if not ranges:
            return ""

        if key == "y":
            self.register = "\n".join(self.text[a:b] for a, b in ranges)
            self.cursor = self._clamp(ranges[0][0])
            return ""

        if key in ("I", "A"):
            # Remember where each line's edit point is, then type once on the
            # first line; the rest are filled in when insert mode ends.
            column = 0 if key == "I" else 1
            points = [a if key == "I" else b for a, b in ranges]
            self.block_edit = (points, len(points), key)
            self._insert_saved = False
            self.mode = INSERT
            self.cursor = points[0]
            self._block_mark = len(self.text)
            return ""

        self._save()
        # Delete right to left so earlier offsets stay valid.
        text = self.text
        for start, end in reversed(ranges):
            text = text[:start] + text[end:]
        self.register = "\n".join(self.text[a:b] for a, b in ranges)
        self.text = text
        self.cursor = self._clamp(ranges[0][0])
        if key in ("c", "s"):
            self._insert_saved = False
            self.mode = INSERT
        return ""

    def _enter_vline(self, _count: int) -> str:
        self.mode = VLINE
        self.anchor = self.cursor
        return ""

    def _join_lines(self, _count: int) -> str:
        """J: pull the next line up, leaving a single space."""
        end = self.line_end(self.cursor)
        if end >= len(self.text):
            return ""
        self._save()
        stripped = self.text[end + 1:].lstrip(" \t")
        self.text = self.text[:end] + " " + stripped
        self.cursor = self._clamp(end)
        return ""

    def _toggle_case(self, count: int) -> str:
        if self.cursor >= len(self.text):
            return ""
        self._save()
        end = min(len(self.text), self.cursor + count)
        self.text = (self.text[:self.cursor]
                     + self.text[self.cursor:end].swapcase() + self.text[end:])
        self.cursor = self._clamp(end)
        return ""

    def _goto_end(self, _count: int) -> str:
        self.cursor = self.last
        return ""

    def clear(self) -> None:
        self.text, self.cursor = "", 0
        self._insert_saved = False
        self.mode = INSERT
        self._reset_pending()
        self.undo_stack.clear()
        self.redo_stack.clear()
