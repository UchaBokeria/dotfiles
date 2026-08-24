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
    #: True while a blockwise selection is anchored to the end of each
    #: line, i.e. after `$`. vim calls this curswant = MAXCOL.
    block_to_eol: bool = False
    #: vim-visual-multi. Each entry is a (start, end) selection; every edit is
    #: applied to all of them. Empty means multicursor is off.
    multi: list = field(default_factory=list)
    #: The word ctrl-n is matching, so repeats find the NEXT one rather than
    #: re-deriving it from wherever the cursor drifted to.
    multi_pattern: str = ""
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
            # `$` makes the block ragged-right: every line runs to its own end,
            # not to the column the cursor happened to stop at. Without this,
            # `$A` on uneven lines appends in the middle of the longer ones.
            right = (end_of_line if self.block_to_eol
                     else min(start + c2 + 1, end_of_line))
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
            had_points = self.block_edit[0] if self.block_edit else None
            self._finish_block_edit()
            self._insert_saved = False        # this session's undo unit is closed
            self.mode = NORMAL
            self.cursor = self._clamp(self.cursor - 1)
            if had_points and len(had_points) > 1:
                # Leave insert but KEEP the cursors, so normal-mode commands
                # still apply to every line. A second escape drops them - the
                # same two-step vim-visual-multi uses, and the reason you can
                # type, escape, move, and type again on all lines.
                self.multi = [(point, point) for point in sorted(had_points)]
            return ""
        if key == "enter":
            return "submit"
        if key == "newline":       # shift+enter: a literal line break
            self._save_insert()
            self.text = self.text[:self.cursor] + "\n" + self.text[self.cursor:]
            self.cursor += 1
            return ""
        if key == "backspace":
            if self.block_edit:
                self._erase_everywhere()
                return ""
            if self.cursor > 0:
                self._save_insert()
                self.text = self.text[: self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
            return ""
        if key == "ctrl-u":
            self._delete_range(0, self.cursor, into_register=False)
            return ""
        if key in ("ctrl-w", "ctrl-backspace"):
            self._delete_range(self._word_back(self.cursor, False), self.cursor, False)
            return ""
        if key in ("left", "right", "home", "end"):
            self.cursor = {"left": max(0, self.cursor - 1),
                           "right": min(len(self.text), self.cursor + 1),
                           "home": 0, "end": len(self.text)}[key]
            return ""
        if len(key) == 1 and self.block_edit:
            self._type_everywhere(key)
            return ""
        if len(key) == 1:
            self._save_insert()
            self.text = self.text[: self.cursor] + key + self.text[self.cursor:]
            self.cursor += 1
        return ""

    def _type_everywhere(self, char: str) -> None:
        """Insert one character at every edit point, as it is typed.

        vim only replicates a block insert when you press escape, so until then
        the other lines sit unchanged and it looks like the block was ignored.
        Applying each keystroke everywhere immediately is what makes it feel
        like typing on three lines at once - which is the whole point.
        """
        points, count, kind = self.block_edit
        self._save_insert()
        text = self.text
        # Right to left, so the offsets still to be used stay valid.
        for point in sorted(points, reverse=True):
            at = max(0, min(point, len(text)))
            text = text[:at] + char + text[at:]
        self.text = text
        # The j-th point has j insertions before it, plus its own.
        moved = [point + index + 1
                 for index, point in enumerate(sorted(points))]
        self.block_edit = (moved, count, kind)
        self.cursor = moved[0]

    def _erase_everywhere(self) -> None:
        """Backspace at every edit point at once."""
        points, count, kind = self.block_edit
        ordered = sorted(points)
        # Refuse the whole thing rather than deleting on some lines only: a
        # backspace that lands unevenly is far worse than one that does nothing.
        if any(at <= 0 or self.text[at - 1] == "\n" for at in ordered):
            return
        self._save_insert()
        text = self.text
        for point in sorted(ordered, reverse=True):
            text = text[:point - 1] + text[point:]
        self.text = text
        moved = [point - index - 1 for index, point in enumerate(ordered)]
        self.block_edit = (moved, count, kind)
        self.cursor = moved[0]

    def _finish_block_edit(self) -> None:
        """Close a block insert.

        Nothing to replicate any more - every keystroke was applied to all the
        edit points as it was typed.
        """
        if not self.block_edit:
            return
        points, _count, _kind = self.block_edit
        self.block_edit = None
        self.cursor = self._clamp(points[0])

    def _reset_pending(self) -> None:
        self.pending = ""
        self.count = ""

    def _feed_normal(self, key: str) -> str:
        # A pending operator or find waiting for its argument.
        if self.pending:
            return self._resolve_pending(key)

        # Multicursor keys, which have to be seen before the ordinary ones:
        # `c` with cursors down the file means something different from `c`
        # with one.
        if key == "ctrl-n":
            return self.multi_add_next()
        if key in ("ctrl-up", "ctrl-down"):
            return self.multi_add_line(-1 if key == "ctrl-up" else 1)
        if self.multi:
            if key == "escape":
                self.multi_clear()
                return ""
            if key in ("c", "s", "d", "x", "y", "I", "A"):
                return self.multi_operator(key)
            if key == "i":
                return self.multi_operator("I")
            if key == "a":
                return self.multi_operator("A")
            if key in ("h", "l", "w", "W", "b", "B", "e", "E", "0", "^", "$"):
                return self.multi_motion(key)
            # Any other key ends the multicursor rather than doing something
            # surprising to every occurrence at once.
            self.multi_clear()

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
            if self.mode == VBLOCK and key not in ("j", "k"):
                # Any horizontal motion pins the block to a real column again;
                # only `$` leaves it ragged-right.
                self.block_to_eol = key == "$"
            target = self.motion(key, count)
            if target is not None:
                self.cursor = self._clamp(target)
            self._reset_pending()
            return ""

        # In visual mode an operator applies to the selection right away.
        # Falling through to the pending-operator path made `vwd` wait for a
        # motion that never came, which is why visual mode appeared dead.
        if self.mode == VBLOCK and key in ("d", "x", "c", "s", "y", "I", "A",
                                           "i", "a"):
            # Lowercase i and a are treated as I and A here. Strict vim keeps
            # them free for text objects (`iw`, `ab`), which this editor does
            # not implement - and reaching for `i` after ctrl-v is the obvious
            # thing to do, so leaving it to insert on a single line just looked
            # like the block selection had been thrown away.
            return self._block_operator({"i": "I", "a": "A"}.get(key, key))

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
            if len(key) != 1:
                return ""
            if self.mode == VBLOCK:
                # Replace every character in the rectangle, as vim does.
                # Replacing only the one under the cursor made block-r look
                # like it had ignored the selection entirely.
                ranges = self.block_ranges()
                self.mode = NORMAL
                self.block_to_eol = False
                if not ranges:
                    return ""
                self._save()
                text = self.text
                for start, end in reversed(ranges):
                    text = text[:start] + key * (end - start) + text[end:]
                self.text = text
                self.cursor = self._clamp(ranges[0][0])
                return ""
            if self.cursor < len(self.text):
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

    # -- multicursor (vim-visual-multi) ---------------------------------
    def word_bounds(self, index: int) -> tuple[int, int]:
        """Start and end of the word under `index`, or an empty range."""
        text = self.text
        if not text:
            return (0, 0)
        index = max(0, min(index, len(text) - 1))
        if not (text[index].isalnum() or text[index] == "_"):
            return (index, index)
        start = index
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1
        end = index
        while end < len(text) and (text[end].isalnum() or text[end] == "_"):
            end += 1
        return (start, end)

    def multi_add_next(self) -> str:
        """ctrl-n: select this word, then each following occurrence.

        The first press selects the word under the cursor; every press after
        that adds the next match, wrapping at the end. This is the half of
        vim-visual-multi people actually use - rename every occurrence of a
        name without a regex.
        """
        if not self.multi:
            start, end = self.word_bounds(self.cursor)
            if start == end:
                return ""
            self.multi = [(start, end)]
            self.multi_pattern = self.text[start:end]
            self.cursor = end - 1
            self.mode = NORMAL
            return ""

        word = self.multi_pattern
        if not word:
            return ""
        taken = {start for start, _end in self.multi}
        search_from = max(end for _start, end in self.multi)
        # Wrap once, so the last occurrence leads back round to the first.
        for probe in (search_from, 0):
            at = probe
            while (at := self.text.find(word, at)) != -1:
                if at not in taken and self._is_whole_word(at, len(word)):
                    self.multi.append((at, at + len(word)))
                    self.multi.sort()
                    self.cursor = at + len(word) - 1
                    return ""
                at += 1
        return ""

    def _is_whole_word(self, at: int, length: int) -> bool:
        before = self.text[at - 1] if at > 0 else " "
        after = (self.text[at + length] if at + length < len(self.text) else " ")
        return not (before.isalnum() or before == "_") and \
               not (after.isalnum() or after == "_")

    def multi_add_line(self, direction: int) -> str:
        """ctrl-up / ctrl-down: a cursor on the line above or below."""
        column = self.column(self.cursor)
        if not self.multi:
            self.multi = [(self.cursor, self.cursor)]
        anchor = self.multi[-1][0] if direction > 0 else self.multi[0][0]
        line = self.line_start(anchor)
        if direction < 0:
            if line == 0:
                return ""
            target = self.line_start(line - 1)
        else:
            end = self.line_end(anchor)
            if end >= len(self.text):
                return ""
            target = end + 1
        at = min(target + column, self.line_end(target))
        if all(at != start for start, _end in self.multi):
            self.multi.append((at, at))
            self.multi.sort()
            self.cursor = at
        return ""

    def multi_motion(self, key: str) -> str:
        """Move every cursor by the same motion, keeping them independent.

        Each one is measured from where IT sits, so `w` on three cursors puts
        each at the next word on its own line rather than dragging them all to
        one place.
        """
        moved, keep = [], self.cursor
        for start, end in self.multi:
            self.cursor = end if end > start else start
            target = self.motion(key, 1)
            at = self._clamp(start if target is None else target)
            moved.append((at, at))
        self.cursor = keep
        if moved:
            self.multi = sorted(set(moved))
            self.cursor = self.multi[0][0]
        return ""

    def multi_clear(self) -> None:
        self.multi = []
        self.multi_pattern = ""

    def multi_operator(self, key: str) -> str:
        """Apply one edit to every cursor.

        Deletions run right to left so the offsets of the earlier ones stay
        valid - the same reason blockwise delete does.
        """
        ranges = [r for r in sorted(self.multi) if r[1] >= r[0]]
        if not ranges:
            return ""

        if key == "y":
            self.register = "\n".join(self.text[a:b] for a, b in ranges)
            self.multi_clear()
            return ""

        if key in ("I", "A"):
            points = []
            for start, end in ranges:
                if key == "I":
                    points.append(start)
                elif end > start:
                    points.append(end)          # after a selection
                else:
                    # A bare cursor sits ON a character, so appending goes one
                    # past it - otherwise `$a` types before the last letter
                    # instead of after it.
                    points.append(min(start + 1, self.line_end(start)))
            self.block_edit = (points, len(points), key)
            self.multi_clear()
            self._insert_saved = False
            self.mode = INSERT
            self.cursor = points[0]
            return ""

        self._save()
        text = self.text
        for start, end in reversed(ranges):
            width = max(end - start, 1 if key in ("x", "s") else end - start)
            text = text[:start] + text[start + width:]
        self.register = "\n".join(self.text[a:b] for a, b in ranges)
        self.text = text

        removed, points = 0, []
        for start, end in ranges:
            points.append(start - removed)
            removed += max(end - start, 1 if key in ("x", "s") else end - start)
        self.cursor = self._clamp(points[0])
        self.multi_clear()
        if key in ("c", "s"):
            self.block_edit = (points, len(points), "c")
            self._insert_saved = False
            self.mode = INSERT
        return ""

    def select_all(self) -> None:
        """Visual selection over the whole buffer, as ctrl-a does elsewhere.

        Leaves the caret at the end so a following `d`, `c` or `y` reads the
        way it would after any other visual selection.
        """
        if not self.text:
            return
        self.mode = VISUAL
        self.anchor = 0
        self.cursor = self.last
        self.block_to_eol = False
        self._reset_pending()

    def _enter_vblock(self, _count: int) -> str:
        self.mode = VBLOCK
        self.anchor = self.cursor
        self.block_to_eol = False
        return ""

    def _block_operator(self, key: str) -> str:
        """d/x/c/y over the rectangle, or I/A to type on every line at once."""
        ranges = self.block_ranges()
        self.mode = NORMAL
        self.block_to_eol = False
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
            # Block change types on EVERY line, not just the first. Entering
            # insert without recording the edit points meant only line one got
            # what you typed, which looks like the block was ignored.
            removed = 0
            points = []
            for start, end in ranges:
                points.append(start - removed)
                removed += end - start
            self.block_edit = (points, len(points), "c")
            self._insert_saved = False
            self.mode = INSERT
            self.cursor = points[0]
            self._block_mark = len(self.text)
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
