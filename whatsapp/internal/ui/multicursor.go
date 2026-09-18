package ui

import (
	"fmt"
	"sort"
	"strings"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
)

// Block selection and multiple cursors, in the input box.
//
// This is the pair of things a draft of more than one line wants and plain vim
// motions do not give: a column of text (<C-v>, then I or A or d) and the same
// edit at every occurrence of a word (<C-n>, then c or d or i). The bindings
// are the ones mg979/vim-visual-multi uses, which is what is in the author's
// Neovim.
//
// While either is active wa handles the keys itself rather than feeding the
// vim engine. The engine has no block mode and no notion of a second cursor,
// and teaching it both to serve a two-line message draft would be a much
// larger change than the feature is worth.

// blockSel is a column selection: an anchor, and the cursor as the other end.
type blockSel struct {
	active bool
	anchor vim.Pos
	// col is the column the live end wants, which is not always the column
	// the cursor could reach. Moving down through a short line clamps the
	// cursor to that line's end; the block must keep its own edge, as vim's
	// does, or a delete takes text from the wrong columns of every line.
	col int
}

// multiSel is a set of cursors, one per occurrence of a word.
type multiSel struct {
	active bool
	// word is what <C-n> matched, so the next press can find the one after.
	word string
	// cursors are in document order. The first is the one the buffer's own
	// cursor tracks; the rest are mirrors.
	cursors []vim.Pos
	// inserting says the typed keys go into the buffer at every cursor.
	inserting bool
}

// multiActive reports whether either takes the keyboard.
func (a *App) multiActive() bool { return a.block.active || a.multi.active }

// startBlock begins a column selection at the cursor.
func (a *App) startBlock() error {
	buf, _ := a.activeBuffer()
	if buf == nil {
		return fmt.Errorf("nothing to select here")
	}
	a.endMulti()
	a.block = blockSel{active: true, anchor: buf.Cursor(), col: buf.Cursor().Col}
	a.setStatus("block select · I A d c y, <Esc> to leave")
	return nil
}

// startMulti selects the word under the cursor, or adds the next occurrence.
func (a *App) startMulti() error {
	buf, _ := a.activeBuffer()
	if buf == nil {
		return fmt.Errorf("nothing to select here")
	}
	a.block = blockSel{}

	if !a.multi.active {
		word, at, ok := wordAt(buf, buf.Cursor())
		if !ok {
			return fmt.Errorf("no word under the cursor")
		}
		a.multi = multiSel{active: true, word: word, cursors: []vim.Pos{at}}
		a.setStatus("1 cursor · <C-n> for the next, i c d I A, <Esc> to leave")
		return nil
	}

	next, ok := nextOccurrence(buf, a.multi.word, a.multi.cursors)
	if !ok {
		a.setStatus(fmt.Sprintf("%d cursors · no more occurrences of %q",
			len(a.multi.cursors), a.multi.word))
		return nil
	}
	a.multi.cursors = append(a.multi.cursors, next)
	sortCursors(a.multi.cursors)
	buf.SetCursor(next)
	a.setStatus(fmt.Sprintf("%s · i c d I A, <Esc> to leave",
		plural(len(a.multi.cursors), "cursor", "cursors")))
	return nil
}

// addCursorVertically puts another cursor one line up or down, at the same
// column. It is vim-visual-multi's <C-Down> and <C-Up>, and the quickest way
// to write the same thing on three lines.
func (a *App) addCursorVertically(delta int) error {
	buf, _ := a.activeBuffer()
	if buf == nil {
		return fmt.Errorf("nothing to put a cursor in")
	}
	a.block = blockSel{}

	if !a.multi.active {
		a.multi = multiSel{active: true, cursors: []vim.Pos{buf.Cursor()}}
	}
	last := a.multi.cursors[len(a.multi.cursors)-1]
	if delta < 0 {
		last = a.multi.cursors[0]
	}
	line := last.Line + delta
	if line < 0 || line >= buf.Lines() {
		a.setStatus(plural(len(a.multi.cursors), "cursor", "cursors") + " · no line that way")
		return nil
	}
	col := last.Col
	if n := buf.LineLen(line); col > n {
		col = n
	}
	next := vim.Pos{Line: line, Col: col}
	for _, c := range a.multi.cursors {
		if c == next {
			return nil
		}
	}
	a.multi.cursors = append(a.multi.cursors, next)
	sortCursors(a.multi.cursors)
	buf.SetCursor(next)
	a.setStatus(plural(len(a.multi.cursors), "cursor", "cursors") + " · i c d I A, <Esc> to leave")
	return nil
}

// endMulti drops every extra cursor and the block.
func (a *App) endMulti() {
	a.block = blockSel{}
	a.multi = multiSel{}
}

// handleMultiKey is the whole keyboard while a block or several cursors are
// live.
func (a *App) handleMultiKey(k keys.Key) bool {
	buf, undo := a.activeBuffer()
	if buf == nil {
		a.endMulti()
		return false
	}

	if k.Mods == keys.Ctrl && (k.Special == keys.Down || k.Special == keys.Up) {
		delta := 1
		if k.Special == keys.Up {
			delta = -1
		}
		if err := a.addCursorVertically(delta); err != nil {
			a.setError(err.Error())
		}
		return true
	}
	// <C-n> keeps taking the next occurrence, which is the whole point of it.
	if k.Mods == keys.Ctrl && k.Rune == 'n' {
		if err := a.startMulti(); err != nil {
			a.setError(err.Error())
		}
		return true
	}

	if k.Special == keys.Esc && k.Mods == 0 {
		switch {
		case a.multi.inserting:
			a.multi.inserting = false
			a.engine.SetMode(vim.Normal)
			a.setStatus(plural(len(a.multi.cursors), "cursor", "cursors"))
		default:
			a.endMulti()
			a.setStatus("")
			a.engine.SetMode(vim.Normal)
		}
		return true
	}

	if a.multi.inserting {
		return a.multiInsertKey(buf, undo, k)
	}

	// Motions move the selection's live end, exactly as they do in vim's own
	// visual block.
	if name, ok := blockMotion(k); ok {
		a.draftMotion(name, 1)
		// Up and down keep the column the block wants; every other motion
		// sets it to wherever the cursor landed.
		if a.block.active && name != "up" && name != "down" {
			a.block.col = buf.Cursor().Col
		}
		return true
	}

	switch {
	case a.block.active:
		return a.blockCommand(buf, undo, k)
	case a.multi.active:
		return a.multiCommand(buf, undo, k)
	}
	return false
}

// blockMotion maps the keys that move a cursor while a selection is live.
func blockMotion(k keys.Key) (string, bool) {
	if k.Mods != 0 {
		return "", false
	}
	switch k.Special {
	case keys.Left:
		return "left", true
	case keys.Right:
		return "right", true
	case keys.Up:
		return "up", true
	case keys.Down:
		return "down", true
	}
	switch k.Rune {
	case 'h':
		return "left", true
	case 'l':
		return "right", true
	case 'j':
		return "down", true
	case 'k':
		return "up", true
	case 'w':
		return "word_next", true
	case 'b':
		return "word_prev", true
	case 'e':
		return "word_end", true
	case '0':
		return "line_start", true
	case '^':
		return "line_first_nonblank", true
	case '$':
		return "line_end", true
	}
	return "", false
}

// blockCommand is what the block's own keys do.
func (a *App) blockCommand(buf *vim.Buffer, undo *vim.Undo, k keys.Key) bool {
	if k.Mods != 0 {
		return true
	}
	live := buf.Cursor()
	live.Col = a.block.col
	top, bottom, left, right := blockBounds(a.block.anchor, live)

	switch k.Rune {
	case 'I', 'A':
		// Insert down the left edge, or append down the right: the two things
		// a column selection is for.
		col := left
		if k.Rune == 'A' {
			col = right + 1
		}
		cursors := make([]vim.Pos, 0, bottom-top+1)
		for line := top; line <= bottom; line++ {
			c := col
			if n := buf.LineLen(line); c > n {
				if k.Rune == 'I' {
					// A short line has no column there to insert before; vim
					// skips it, and so does this.
					continue
				}
				c = n
			}
			cursors = append(cursors, vim.Pos{Line: line, Col: c})
		}
		if len(cursors) == 0 {
			return true
		}
		a.block = blockSel{}
		a.multi = multiSel{active: true, cursors: cursors, inserting: true}
		buf.SetCursor(cursors[0])
		undo.Checkpoint()
		a.engine.SetMode(vim.Insert)
		a.setStatus(plural(len(cursors), "cursor", "cursors") + " · type, <Esc> to leave")
		return true

	case 'd', 'x', 'c':
		undo.Checkpoint()
		// Bottom upwards: deleting a line above would move the ones below.
		for line := bottom; line >= top; line-- {
			n := buf.LineLen(line)
			if left >= n {
				continue
			}
			to := right
			if to >= n {
				to = n - 1
			}
			buf.Delete(vim.Span{
				From: vim.Pos{Line: line, Col: left},
				To:   vim.Pos{Line: line, Col: to},
				Kind: vim.Inclusive,
			})
		}
		buf.SetCursor(vim.Pos{Line: top, Col: left})
		if k.Rune == 'c' {
			cursors := make([]vim.Pos, 0, bottom-top+1)
			for line := top; line <= bottom; line++ {
				c := left
				if n := buf.LineLen(line); c > n {
					c = n
				}
				cursors = append(cursors, vim.Pos{Line: line, Col: c})
			}
			a.block = blockSel{}
			a.multi = multiSel{active: true, cursors: cursors, inserting: true}
			a.engine.SetMode(vim.Insert)
			a.setStatus("changing " + plural(len(cursors), "line", "lines"))
			return true
		}
		a.endMulti()
		a.setStatus("block deleted")
		return true

	case 'y':
		var b strings.Builder
		for line := top; line <= bottom; line++ {
			n := buf.LineLen(line)
			if left >= n {
				b.WriteString("\n")
				continue
			}
			to := right + 1
			if to > n {
				to = n
			}
			b.WriteString(string([]rune(buf.Line(line))[left:to]) + "\n")
		}
		a.endMulti()
		if err := a.copyText(strings.TrimRight(b.String(), "\n")); err != nil {
			a.setError(err.Error())
		}
		return true
	}
	return true
}

// multiCommand is what the extra cursors' own keys do.
func (a *App) multiCommand(buf *vim.Buffer, undo *vim.Undo, k keys.Key) bool {
	if k.Mods != 0 {
		return true
	}
	switch k.Rune {
	case 'i', 'a', 'I', 'A':
		// i types before each occurrence, a after it. I and A are the same
		// thing at the ends of the word, which is what vim-visual-multi does.
		word := len([]rune(a.multi.word))
		for idx := range a.multi.cursors {
			switch k.Rune {
			case 'a', 'A':
				a.multi.cursors[idx].Col += word
			}
		}
		a.multi.inserting = true
		buf.SetCursor(a.multi.cursors[0])
		undo.Checkpoint()
		a.engine.SetMode(vim.Insert)
		a.setStatus(plural(len(a.multi.cursors), "cursor", "cursors") + " · type, <Esc> to leave")
		return true

	case 'c', 'd', 'x':
		undo.Checkpoint()
		word := len([]rune(a.multi.word))
		// Last first: an earlier deletion shifts everything after it.
		for i := len(a.multi.cursors) - 1; i >= 0; i-- {
			p := a.multi.cursors[i]
			n := buf.LineLen(p.Line)
			to := p.Col + word - 1
			if to >= n {
				to = n - 1
			}
			if to < p.Col {
				continue
			}
			buf.Delete(vim.Span{From: p, To: vim.Pos{Line: p.Line, Col: to}, Kind: vim.Inclusive})
		}
		// Each deletion pulls everything after it on the same line to the
		// left, so the cursors that are left have to be pulled with it.
		shift := map[int]int{}
		for i := range a.multi.cursors {
			line := a.multi.cursors[i].Line
			a.multi.cursors[i].Col -= shift[line]
			shift[line] += word
		}
		if k.Rune == 'c' {
			a.multi.inserting = true
			buf.SetCursor(a.multi.cursors[0])
			a.engine.SetMode(vim.Insert)
			a.setStatus("changing " + plural(len(a.multi.cursors), "occurrence", "occurrences"))
			return true
		}
		a.endMulti()
		a.setStatus("deleted")
		return true
	}
	return true
}

// multiInsertKey types into every cursor at once.
func (a *App) multiInsertKey(buf *vim.Buffer, undo *vim.Undo, k keys.Key) bool {
	switch {
	case k.Special == keys.BS && k.Mods == 0:
		a.multiEdit(buf, undo, "", true)
		return true
	case k.Special == keys.CR && k.Mods == 0:
		// A newline at several cursors turns one line into several and moves
		// every cursor below it; sending the message is the far likelier
		// intention, so this ends the multi-cursor instead.
		a.endMulti()
		return false
	}
	if r, ok := k.Printable(); ok {
		a.multiEdit(buf, undo, string(r), false)
		return true
	}
	return true
}

// multiEdit applies one insertion or one backspace at every cursor.
//
// The cursors are worked through last first, so an edit never moves a position
// that has not been used yet; each cursor then carries the shift of the edits
// made before it on its own line.
func (a *App) multiEdit(buf *vim.Buffer, undo *vim.Undo, text string, backspace bool) {
	cursors := a.multi.cursors
	sortCursors(cursors)
	width := len([]rune(text))

	for i := len(cursors) - 1; i >= 0; i-- {
		p := cursors[i]
		buf.SetCursor(p)
		if backspace {
			if p.Col == 0 {
				continue
			}
			buf.Delete(vim.Span{
				From: vim.Pos{Line: p.Line, Col: p.Col - 1},
				To:   vim.Pos{Line: p.Line, Col: p.Col - 1},
				Kind: vim.Inclusive,
			})
			continue
		}
		buf.Insert(text)
	}

	// Every cursor moves by its own edit, plus the edits made before it on the
	// same line.
	shift := map[int]int{}
	for i := range cursors {
		line := cursors[i].Line
		if backspace {
			if cursors[i].Col > 0 {
				cursors[i].Col += shift[line] - 1
				shift[line]--
			} else {
				cursors[i].Col += shift[line]
			}
			continue
		}
		cursors[i].Col += shift[line] + width
		shift[line] += width
	}
	buf.SetCursor(cursors[0])
	a.multi.cursors = cursors
	_ = undo
}

// wordAt is the word under a position, and where it starts.
func wordAt(buf *vim.Buffer, p vim.Pos) (string, vim.Pos, bool) {
	line := []rune(buf.Line(p.Line))
	if len(line) == 0 {
		return "", p, false
	}
	col := p.Col
	if col >= len(line) {
		col = len(line) - 1
	}
	if !isWordRune(line[col]) {
		return "", p, false
	}
	start := col
	for start > 0 && isWordRune(line[start-1]) {
		start--
	}
	end := col
	for end+1 < len(line) && isWordRune(line[end+1]) {
		end++
	}
	return string(line[start : end+1]), vim.Pos{Line: p.Line, Col: start}, true
}

func isWordRune(r rune) bool {
	return r == '_' || r >= '0' && r <= '9' || r >= 'a' && r <= 'z' ||
		r >= 'A' && r <= 'Z' || r > 127
}

// nextOccurrence finds the next place the word appears that has no cursor yet,
// wrapping around the end of the draft.
func nextOccurrence(buf *vim.Buffer, word string, have []vim.Pos) (vim.Pos, bool) {
	if word == "" {
		return vim.Pos{}, false
	}
	taken := map[vim.Pos]bool{}
	for _, p := range have {
		taken[p] = true
	}
	last := have[len(have)-1]

	// From just after the last cursor to the end, then from the start: the
	// order <C-n> walks in.
	for pass := 0; pass < 2; pass++ {
		for line := 0; line < buf.Lines(); line++ {
			text := buf.Line(line)
			for col := 0; ; {
				i := strings.Index(text[col:], word)
				if i < 0 {
					break
				}
				at := vim.Pos{Line: line, Col: len([]rune(text[:col+i]))}
				col += i + len(word)
				if taken[at] {
					continue
				}
				after := at.Line > last.Line || (at.Line == last.Line && at.Col > last.Col)
				if (pass == 0) == after {
					return at, true
				}
			}
		}
	}
	return vim.Pos{}, false
}

func sortCursors(c []vim.Pos) {
	sort.Slice(c, func(i, j int) bool {
		if c[i].Line != c[j].Line {
			return c[i].Line < c[j].Line
		}
		return c[i].Col < c[j].Col
	})
}

// blockBounds is the rectangle two corners describe, in the order the edits
// want it: top line, bottom line, left column, right column.
func blockBounds(anchor, cursor vim.Pos) (top, bottom, left, right int) {
	top, bottom = anchor.Line, cursor.Line
	if top > bottom {
		top, bottom = bottom, top
	}
	left, right = anchor.Col, cursor.Col
	if left > right {
		left, right = right, left
	}
	return top, bottom, left, right
}
