package vim

import "unicode"

// MotionResult is where a motion lands.
type MotionResult struct {
	To    Pos
	Kind  MotionKind
	Valid bool
}

// charClass groups runes the way vim's word motions do: a small word ends at
// a change of class, which is why `w` on "brown-fox" stops at the hyphen.
type charClass int

const (
	classBlank charClass = iota
	classWord
	classPunct
)

func classOf(r rune) charClass {
	switch {
	case r == 0 || unicode.IsSpace(r):
		return classBlank
	case unicode.IsLetter(r) || unicode.IsDigit(r) || r == '_':
		return classWord
	default:
		return classPunct
	}
}

// bigClass is the WORD variant: anything not blank is one class.
func bigClass(r rune) charClass {
	if classOf(r) == classBlank {
		return classBlank
	}
	return classWord
}

// Move computes a motion from the buffer's cursor.
//
// arg is the target character for f, F, t and T; count repeats the motion.
func Move(b *Buffer, name string, count int, arg rune) MotionResult {
	if count <= 0 {
		count = 1
	}
	pos := b.cursor
	kind := Exclusive

	for i := 0; i < count; i++ {
		var next Pos
		var ok bool
		next, kind, ok = moveOnce(b, name, pos, arg)
		if !ok {
			// A motion that cannot complete fails as a whole, as in vim: `3w`
			// at the end of the text does not move partway.
			if i == 0 {
				return MotionResult{To: pos, Kind: kind, Valid: false}
			}
			break
		}
		pos = next
	}
	return MotionResult{To: pos, Kind: kind, Valid: true}
}

func moveOnce(b *Buffer, name string, from Pos, arg rune) (Pos, MotionKind, bool) {
	switch name {
	case "left":
		if from.Col == 0 {
			return from, Exclusive, false
		}
		return Pos{from.Line, from.Col - 1}, Exclusive, true

	case "right":
		if from.Col >= b.LineLen(from.Line) {
			return from, Exclusive, false
		}
		return Pos{from.Line, from.Col + 1}, Exclusive, true

	case "up":
		if from.Line == 0 {
			return from, Linewise, false
		}
		return Pos{from.Line - 1, from.Col}, Linewise, true

	case "down":
		if from.Line >= b.Lines()-1 {
			return from, Linewise, false
		}
		return Pos{from.Line + 1, from.Col}, Linewise, true

	case "line_start":
		return Pos{from.Line, 0}, Exclusive, true

	case "line_first_nonblank":
		line := b.lines[from.Line]
		for i, r := range line {
			if !unicode.IsSpace(r) {
				return Pos{from.Line, i}, Exclusive, true
			}
		}
		return Pos{from.Line, 0}, Exclusive, true

	case "line_end":
		n := b.LineLen(from.Line)
		if n == 0 {
			return Pos{from.Line, 0}, Inclusive, true
		}
		return Pos{from.Line, n - 1}, Inclusive, true

	case "buffer_start":
		return Pos{0, 0}, Linewise, true

	case "buffer_end":
		return Pos{b.Lines() - 1, 0}, Linewise, true

	case "word_next":
		return wordNext(b, from, classOf)
	case "word_next_big":
		return wordNext(b, from, bigClass)
	case "word_prev":
		return wordPrev(b, from, classOf)
	case "word_prev_big":
		return wordPrev(b, from, bigClass)
	case "word_end":
		return wordEnd(b, from, classOf)
	case "word_end_big":
		return wordEnd(b, from, bigClass)
	case "word_end_prev":
		return wordEndPrev(b, from, classOf)

	case "find_char":
		return findChar(b, from, arg, +1, false)
	case "find_char_back":
		return findChar(b, from, arg, -1, false)
	case "till_char":
		return findChar(b, from, arg, +1, true)
	case "till_char_back":
		return findChar(b, from, arg, -1, true)

	case "match_pair":
		return matchPair(b, from)

	case "paragraph_next":
		return paragraph(b, from, +1)
	case "paragraph_prev":
		return paragraph(b, from, -1)
	case "sentence_next":
		return sentence(b, from, +1)
	case "sentence_prev":
		return sentence(b, from, -1)

	case "line":
		return from, Linewise, true
	}
	return from, Exclusive, false
}

// advance walks one rune forward through the buffer, crossing line ends.
func advance(b *Buffer, p Pos) (Pos, bool) {
	if p.Col < b.LineLen(p.Line) {
		return Pos{p.Line, p.Col + 1}, true
	}
	if p.Line < b.Lines()-1 {
		return Pos{p.Line + 1, 0}, true
	}
	return p, false
}

func retreat(b *Buffer, p Pos) (Pos, bool) {
	if p.Col > 0 {
		return Pos{p.Line, p.Col - 1}, true
	}
	if p.Line > 0 {
		return Pos{p.Line - 1, b.LineLen(p.Line - 1)}, true
	}
	return p, false
}

func wordNext(b *Buffer, from Pos, class func(rune) charClass) (Pos, MotionKind, bool) {
	start := class(b.at(from))
	p := from
	// Leave the current run.
	if start != classBlank {
		for {
			next, ok := advance(b, p)
			if !ok {
				return p, Exclusive, p != from
			}
			p = next
			if class(b.at(p)) != start {
				break
			}
		}
	}
	// Skip whitespace to the next word.
	for class(b.at(p)) == classBlank {
		next, ok := advance(b, p)
		if !ok {
			return p, Exclusive, p != from
		}
		p = next
	}
	return p, Exclusive, p != from
}

func wordPrev(b *Buffer, from Pos, class func(rune) charClass) (Pos, MotionKind, bool) {
	p, ok := retreat(b, from)
	if !ok {
		return from, Exclusive, false
	}
	for class(b.at(p)) == classBlank {
		next, ok := retreat(b, p)
		if !ok {
			return p, Exclusive, true
		}
		p = next
	}
	target := class(b.at(p))
	for {
		prev, ok := retreat(b, p)
		if !ok || class(b.at(prev)) != target {
			break
		}
		p = prev
	}
	return p, Exclusive, true
}

func wordEnd(b *Buffer, from Pos, class func(rune) charClass) (Pos, MotionKind, bool) {
	p, ok := advance(b, from)
	if !ok {
		return from, Inclusive, false
	}
	for class(b.at(p)) == classBlank {
		next, ok := advance(b, p)
		if !ok {
			return p, Inclusive, true
		}
		p = next
	}
	target := class(b.at(p))
	for {
		next, ok := advance(b, p)
		if !ok || class(b.at(next)) != target {
			break
		}
		p = next
	}
	return p, Inclusive, true
}

func wordEndPrev(b *Buffer, from Pos, class func(rune) charClass) (Pos, MotionKind, bool) {
	p, ok := retreat(b, from)
	if !ok {
		return from, Inclusive, false
	}
	for class(b.at(p)) == classBlank {
		next, ok := retreat(b, p)
		if !ok {
			return p, Inclusive, true
		}
		p = next
	}
	return p, Inclusive, true
}

// findChar implements f, F, t and T. They never cross a line, as in vim.
func findChar(b *Buffer, from Pos, target rune, dir int, till bool) (Pos, MotionKind, bool) {
	if target == 0 {
		return from, Exclusive, false
	}
	line := b.lines[from.Line]
	for i := from.Col + dir; i >= 0 && i < len(line); i += dir {
		if line[i] != target {
			continue
		}
		col := i
		if till {
			col -= dir
		}
		kind := Inclusive
		if dir < 0 {
			kind = Exclusive
		}
		return Pos{from.Line, col}, kind, true
	}
	return from, Exclusive, false
}

var pairs = map[rune]struct {
	match rune
	dir   int
}{
	'(': {')', +1}, ')': {'(', -1},
	'[': {']', +1}, ']': {'[', -1},
	'{': {'}', +1}, '}': {'{', -1},
}

func matchPair(b *Buffer, from Pos) (Pos, MotionKind, bool) {
	line := b.lines[from.Line]
	// vim scans forward on the line for the first bracket.
	start := -1
	var open rune
	for i := from.Col; i < len(line); i++ {
		if _, ok := pairs[line[i]]; ok {
			start, open = i, line[i]
			break
		}
	}
	if start < 0 {
		return from, Inclusive, false
	}

	info := pairs[open]
	depth := 0
	p := Pos{from.Line, start}
	for {
		r := b.at(p)
		if r == open {
			depth++
		} else if r == info.match {
			depth--
			if depth == 0 {
				return p, Inclusive, true
			}
		}
		var ok bool
		if info.dir > 0 {
			p, ok = advance(b, p)
		} else {
			p, ok = retreat(b, p)
		}
		if !ok {
			return from, Inclusive, false
		}
	}
}

// paragraph moves to the next or previous blank line.
func paragraph(b *Buffer, from Pos, dir int) (Pos, MotionKind, bool) {
	line := from.Line + dir
	for line > 0 && line < b.Lines()-1 {
		if len(b.lines[line]) == 0 {
			return Pos{line, 0}, Exclusive, true
		}
		line += dir
	}
	if dir > 0 {
		return Pos{b.Lines() - 1, b.LineLen(b.Lines() - 1)}, Exclusive, true
	}
	return Pos{0, 0}, Exclusive, true
}

// sentence moves by sentence-ending punctuation followed by a space.
func sentence(b *Buffer, from Pos, dir int) (Pos, MotionKind, bool) {
	p := from
	for {
		var ok bool
		if dir > 0 {
			p, ok = advance(b, p)
		} else {
			p, ok = retreat(b, p)
		}
		if !ok {
			return p, Exclusive, p != from
		}
		if isSentenceEnd(b.at(p)) {
			next, ok := advance(b, p)
			if !ok {
				return p, Exclusive, true
			}
			for classOf(b.at(next)) == classBlank {
				n, ok := advance(b, next)
				if !ok {
					break
				}
				next = n
			}
			if next != from {
				return next, Exclusive, true
			}
		}
	}
}

func isSentenceEnd(r rune) bool { return r == '.' || r == '!' || r == '?' }
