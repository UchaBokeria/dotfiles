package vim

import (
	"strings"
	"unicode"
)

// Apply performs an operator over a span, recording yanked or deleted text in
// the register. It reports whether the caller should now enter insert mode,
// which is the only thing that distinguishes `c` from `d`.
func Apply(b *Buffer, op string, s Span, regs *Registers, reg rune) (enterInsert bool) {
	s = s.Normalised()

	switch op {
	case "yank":
		text := b.Slice(s)
		if regs != nil {
			regs.Yank(reg, text, s.Kind == Linewise)
		}
		// A yank leaves the cursor at the start of the range, as in vim.
		b.SetCursor(s.From)
		return false

	case "delete", "change":
		text := b.Delete(s)
		if regs != nil {
			regs.Set(reg, text, s.Kind == Linewise)
		}
		if op == "change" && s.Kind == Linewise {
			// `cc` empties the line and leaves you on it, rather than removing
			// it outright.
			b.lines = append(b.lines, nil)
			copy(b.lines[s.From.Line+1:], b.lines[s.From.Line:])
			b.lines[s.From.Line] = []rune{}
			b.SetCursor(Pos{s.From.Line, 0})
		}
		return op == "change"

	case "lower", "upper", "toggle_case":
		transform(b, s, op)
		b.SetCursor(s.From)
		return false
	}
	return false
}

// transform rewrites the case of the text a span covers.
func transform(b *Buffer, s Span, op string) {
	text := b.Slice(s)
	var out string
	switch op {
	case "lower":
		out = strings.ToLower(text)
	case "upper":
		out = strings.ToUpper(text)
	case "toggle_case":
		out = strings.Map(func(r rune) rune {
			switch {
			case unicode.IsUpper(r):
				return unicode.ToLower(r)
			case unicode.IsLower(r):
				return unicode.ToUpper(r)
			}
			return r
		}, text)
	default:
		return
	}

	if s.Kind == Linewise {
		lines := strings.Split(strings.TrimSuffix(out, "\n"), "\n")
		for i, l := range lines {
			if s.From.Line+i < b.Lines() {
				b.lines[s.From.Line+i] = []rune(l)
			}
		}
		return
	}
	b.Delete(s)
	b.SetCursor(s.From)
	b.Insert(out)
	b.SetCursor(s.From)
}

// Put inserts register contents, as `p` and `P` do.
func Put(b *Buffer, c Content, after bool) {
	if c.Text == "" {
		return
	}
	if c.Linewise {
		line := b.cursor.Line
		if after {
			line++
		}
		body := strings.Split(strings.TrimSuffix(c.Text, "\n"), "\n")
		inserted := make([][]rune, 0, len(body))
		for _, l := range body {
			inserted = append(inserted, []rune(l))
		}
		line = clampInt(line, 0, b.Lines())
		tail := append([][]rune{}, b.lines[line:]...)
		b.lines = append(append(b.lines[:line], inserted...), tail...)
		b.SetCursor(Pos{line, 0})
		return
	}

	if after && b.LineLen(b.cursor.Line) > 0 {
		b.SetCursor(Pos{b.cursor.Line, b.cursor.Col + 1})
	}
	at := b.cursor
	b.Insert(c.Text)
	// vim leaves the cursor on the last pasted character.
	if b.cursor.Col > at.Col {
		b.SetCursor(Pos{b.cursor.Line, b.cursor.Col - 1})
	}
}

// SpanForMotion turns a motion into the range an operator should cover.
//
// The exclusive-to-inclusive distinction is the whole reason this is separate
// from Move: `dw` stops before the next word, `de` eats the last character.
func SpanForMotion(b *Buffer, m MotionResult, from Pos) Span {
	if m.Kind == Linewise {
		return Span{From: Pos{Line: from.Line}, To: Pos{Line: m.To.Line}, Kind: Linewise}
	}
	s := Span{From: from, To: m.To, Kind: m.Kind}
	if m.To.Before(from) {
		s.From, s.To = m.To, from
		if m.Kind == Exclusive {
			// Backwards exclusive: the character under the original cursor is
			// not included, and the one at the target is.
			s.Kind = Exclusive
		}
	}
	return s
}
