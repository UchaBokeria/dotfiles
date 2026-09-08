package vim

import "strings"

// Pos is a cursor position. Col counts runes, not bytes, so a Georgian or
// emoji-bearing draft indexes the way the user sees it.
type Pos struct {
	Line int
	Col  int
}

// Before reports whether p comes earlier than q.
func (p Pos) Before(q Pos) bool {
	if p.Line != q.Line {
		return p.Line < q.Line
	}
	return p.Col < q.Col
}

// MotionKind is how a range covers its endpoint, which is the difference
// between `dw` and `de`.
type MotionKind int

const (
	// Exclusive excludes the end position.
	Exclusive MotionKind = iota
	// Inclusive includes the character at the end position.
	Inclusive
	// Linewise covers whole lines.
	Linewise
)

// Span is a range of text.
type Span struct {
	From Pos
	To   Pos
	Kind MotionKind
}

// Normalised returns the span with From before To.
func (s Span) Normalised() Span {
	if s.To.Before(s.From) {
		s.From, s.To = s.To, s.From
	}
	return s
}

// Buffer is an editable multi-line text buffer with a cursor.
type Buffer struct {
	lines  [][]rune
	cursor Pos
}

// NewBuffer returns an empty buffer.
func NewBuffer() *Buffer {
	return &Buffer{lines: [][]rune{{}}}
}

// Text is the buffer's contents.
func (b *Buffer) Text() string {
	parts := make([]string, len(b.lines))
	for i, l := range b.lines {
		parts[i] = string(l)
	}
	return strings.Join(parts, "\n")
}

// SetText replaces the contents and clamps the cursor into the new text.
func (b *Buffer) SetText(s string) {
	raw := strings.Split(s, "\n")
	b.lines = make([][]rune, len(raw))
	for i, l := range raw {
		b.lines[i] = []rune(l)
	}
	if len(b.lines) == 0 {
		b.lines = [][]rune{{}}
	}
	b.clamp()
}

// Empty reports whether the buffer holds nothing.
func (b *Buffer) Empty() bool { return len(b.lines) == 1 && len(b.lines[0]) == 0 }

// Lines is the number of lines.
func (b *Buffer) Lines() int { return len(b.lines) }

// Line returns one line's text.
func (b *Buffer) Line(n int) string {
	if n < 0 || n >= len(b.lines) {
		return ""
	}
	return string(b.lines[n])
}

// LineLen is the number of runes on a line.
func (b *Buffer) LineLen(n int) int {
	if n < 0 || n >= len(b.lines) {
		return 0
	}
	return len(b.lines[n])
}

// Cursor is the cursor position.
func (b *Buffer) Cursor() Pos { return b.cursor }

// SetCursor moves the cursor, clamped into the text.
func (b *Buffer) SetCursor(p Pos) {
	b.cursor = p
	b.clamp()
}

// clamp keeps the cursor inside the buffer. Insert mode may sit one past the
// last character; normal mode may not, but the caller decides that, so the
// buffer allows it and the engine trims.
func (b *Buffer) clamp() {
	if len(b.lines) == 0 {
		b.lines = [][]rune{{}}
	}
	if b.cursor.Line < 0 {
		b.cursor.Line = 0
	}
	if b.cursor.Line >= len(b.lines) {
		b.cursor.Line = len(b.lines) - 1
	}
	if b.cursor.Col < 0 {
		b.cursor.Col = 0
	}
	if max := len(b.lines[b.cursor.Line]); b.cursor.Col > max {
		b.cursor.Col = max
	}
}

// rune at a position, or zero past the end of the line.
func (b *Buffer) at(p Pos) rune {
	if p.Line < 0 || p.Line >= len(b.lines) {
		return 0
	}
	if p.Col < 0 || p.Col >= len(b.lines[p.Line]) {
		return 0
	}
	return b.lines[p.Line][p.Col]
}

// Insert puts text at the cursor and leaves the cursor after it.
func (b *Buffer) Insert(s string) {
	if s == "" {
		return
	}
	for _, part := range strings.Split(s, "\n") {
		b.insertInline(part)
		if strings.Contains(s, "\n") {
			b.splitLine()
		}
	}
	// The loop above adds one split too many for text ending without a
	// newline, so undo the final one.
	if strings.Contains(s, "\n") {
		b.joinAtCursor()
	}
}

func (b *Buffer) insertInline(s string) {
	if s == "" {
		return
	}
	line := b.lines[b.cursor.Line]
	rs := []rune(s)
	out := make([]rune, 0, len(line)+len(rs))
	out = append(out, line[:b.cursor.Col]...)
	out = append(out, rs...)
	out = append(out, line[b.cursor.Col:]...)
	b.lines[b.cursor.Line] = out
	b.cursor.Col += len(rs)
}

// splitLine breaks the current line at the cursor.
func (b *Buffer) splitLine() {
	line := b.lines[b.cursor.Line]
	head := append([]rune{}, line[:b.cursor.Col]...)
	tail := append([]rune{}, line[b.cursor.Col:]...)

	b.lines[b.cursor.Line] = head
	rest := append([][]rune{tail}, b.lines[b.cursor.Line+1:]...)
	b.lines = append(b.lines[:b.cursor.Line+1], rest...)
	b.cursor.Line++
	b.cursor.Col = 0
}

// joinAtCursor merges the cursor's line with the one before it.
func (b *Buffer) joinAtCursor() {
	if b.cursor.Line == 0 {
		return
	}
	prev := b.lines[b.cursor.Line-1]
	cur := b.lines[b.cursor.Line]
	b.cursor.Col = len(prev)
	b.lines[b.cursor.Line-1] = append(prev, cur...)
	b.lines = append(b.lines[:b.cursor.Line], b.lines[b.cursor.Line+1:]...)
	b.cursor.Line--
}

// Slice returns the text a span covers.
func (b *Buffer) Slice(s Span) string {
	s = s.Normalised()
	if s.Kind == Linewise {
		from, to := s.From.Line, s.To.Line
		if from < 0 {
			from = 0
		}
		if to >= len(b.lines) {
			to = len(b.lines) - 1
		}
		parts := make([]string, 0, to-from+1)
		for i := from; i <= to; i++ {
			parts = append(parts, string(b.lines[i]))
		}
		return strings.Join(parts, "\n") + "\n"
	}

	end := s.To
	if s.Kind == Inclusive {
		end.Col++
	}
	if s.From.Line == end.Line {
		line := b.lines[clampInt(s.From.Line, 0, len(b.lines)-1)]
		from := clampInt(s.From.Col, 0, len(line))
		to := clampInt(end.Col, from, len(line))
		return string(line[from:to])
	}

	var out strings.Builder
	first := b.lines[clampInt(s.From.Line, 0, len(b.lines)-1)]
	out.WriteString(string(first[clampInt(s.From.Col, 0, len(first)):]))
	for i := s.From.Line + 1; i < end.Line && i < len(b.lines); i++ {
		out.WriteString("\n")
		out.WriteString(string(b.lines[i]))
	}
	if end.Line < len(b.lines) {
		last := b.lines[end.Line]
		out.WriteString("\n")
		out.WriteString(string(last[:clampInt(end.Col, 0, len(last))]))
	}
	return out.String()
}

// Delete removes a span, returns what it held, and leaves the cursor at the
// start of the removed range.
func (b *Buffer) Delete(s Span) string {
	s = s.Normalised()
	text := b.Slice(s)

	if s.Kind == Linewise {
		from := clampInt(s.From.Line, 0, len(b.lines)-1)
		to := clampInt(s.To.Line, from, len(b.lines)-1)
		b.lines = append(b.lines[:from], b.lines[to+1:]...)
		if len(b.lines) == 0 {
			b.lines = [][]rune{{}}
		}
		b.cursor = Pos{Line: clampInt(from, 0, len(b.lines)-1), Col: 0}
		b.clamp()
		return text
	}

	end := s.To
	if s.Kind == Inclusive {
		end.Col++
	}
	fromLine := clampInt(s.From.Line, 0, len(b.lines)-1)
	toLine := clampInt(end.Line, 0, len(b.lines)-1)

	first := b.lines[fromLine]
	last := b.lines[toLine]
	head := append([]rune{}, first[:clampInt(s.From.Col, 0, len(first))]...)
	tail := append([]rune{}, last[clampInt(end.Col, 0, len(last)):]...)

	merged := append(head, tail...)
	b.lines = append(b.lines[:fromLine], append([][]rune{merged}, b.lines[toLine+1:]...)...)
	b.cursor = Pos{Line: fromLine, Col: clampInt(s.From.Col, 0, len(merged))}
	b.clamp()
	return text
}

// Snapshot is a copy of the buffer's state, for undo.
type Snapshot struct {
	lines  [][]rune
	cursor Pos
}

// Snapshot copies the buffer.
func (b *Buffer) Snapshot() Snapshot {
	lines := make([][]rune, len(b.lines))
	for i, l := range b.lines {
		lines[i] = append([]rune{}, l...)
	}
	return Snapshot{lines: lines, cursor: b.cursor}
}

// Restore puts a snapshot back.
func (b *Buffer) Restore(s Snapshot) {
	lines := make([][]rune, len(s.lines))
	for i, l := range s.lines {
		lines[i] = append([]rune{}, l...)
	}
	if len(lines) == 0 {
		lines = [][]rune{{}}
	}
	b.lines = lines
	b.cursor = s.cursor
	b.clamp()
}

func (s Snapshot) text() string {
	parts := make([]string, len(s.lines))
	for i, l := range s.lines {
		parts[i] = string(l)
	}
	return strings.Join(parts, "\n")
}

func clampInt(v, lo, hi int) int {
	if hi < lo {
		return lo
	}
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}
