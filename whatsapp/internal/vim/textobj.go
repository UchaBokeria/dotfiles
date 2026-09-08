package vim

import "unicode"

// delimiters for the bracket-shaped text objects.
var objectDelims = map[string][2]rune{
	"paren":        {'(', ')'},
	"bracket":      {'[', ']'},
	"brace":        {'{', '}'},
	"angle":        {'<', '>'},
	"quote_double": {'"', '"'},
	"quote_single": {'\'', '\''},
	"quote_back":   {'`', '`'},
}

// TextObject resolves `iw`, `a"`, `ip` and friends against the cursor.
//
// around selects the `a` variant, which includes the delimiters, or for a word
// the trailing whitespace - matching vim, where `daw` leaves no double space.
func TextObject(b *Buffer, object string, around bool) (Span, bool) {
	switch object {
	case "word":
		return wordObject(b, around, classOf)
	case "word_big":
		return wordObject(b, around, bigClass)
	case "paragraph":
		return paragraphObject(b, around)
	case "sentence":
		return sentenceObject(b, around)
	}
	if d, ok := objectDelims[object]; ok {
		return delimitedObject(b, d[0], d[1], around)
	}
	return Span{}, false
}

func wordObject(b *Buffer, around bool, class func(rune) charClass) (Span, bool) {
	cur := b.cursor
	line := b.lines[cur.Line]
	if len(line) == 0 {
		return Span{}, false
	}
	col := clampInt(cur.Col, 0, len(line)-1)

	target := class(line[col])
	start, end := col, col
	for start > 0 && class(line[start-1]) == target {
		start--
	}
	for end+1 < len(line) && class(line[end+1]) == target {
		end++
	}

	if around {
		// Trailing whitespace first; if there is none, take the leading run,
		// which is what vim does at the end of a line.
		tail := end
		for tail+1 < len(line) && classOf(line[tail+1]) == classBlank {
			tail++
		}
		if tail != end {
			end = tail
		} else {
			for start > 0 && classOf(line[start-1]) == classBlank {
				start--
			}
		}
	}
	return Span{
		From: Pos{cur.Line, start},
		To:   Pos{cur.Line, end},
		Kind: Inclusive,
	}, true
}

func delimitedObject(b *Buffer, open, close rune, around bool) (Span, bool) {
	cur := b.cursor
	line := b.lines[cur.Line]
	if len(line) == 0 {
		return Span{}, false
	}
	col := clampInt(cur.Col, 0, len(line)-1)

	var start, end int
	if open == close {
		// Quotes have no nesting, so pair them off from the start of the line.
		// This is why `ci"` inside "a" and "b" edits the pair the cursor is in
		// rather than the span between them.
		positions := []int{}
		for i, r := range line {
			if r == open {
				positions = append(positions, i)
			}
		}
		if len(positions) < 2 {
			return Span{}, false
		}
		found := false
		for i := 0; i+1 < len(positions); i += 2 {
			if col <= positions[i+1] {
				start, end = positions[i], positions[i+1]
				found = true
				break
			}
		}
		if !found {
			return Span{}, false
		}
	} else {
		start = -1
		depth := 0
		for i := col; i >= 0; i-- {
			switch line[i] {
			case close:
				if i != col {
					depth++
				}
			case open:
				if depth == 0 {
					start = i
				} else {
					depth--
				}
			}
			if start >= 0 {
				break
			}
		}
		if start < 0 {
			return Span{}, false
		}
		end = -1
		depth = 0
		for i := start + 1; i < len(line); i++ {
			switch line[i] {
			case open:
				depth++
			case close:
				if depth == 0 {
					end = i
				} else {
					depth--
				}
			}
			if end >= 0 {
				break
			}
		}
		if end < 0 {
			return Span{}, false
		}
	}

	if around {
		return Span{
			From: Pos{cur.Line, start},
			To:   Pos{cur.Line, end},
			Kind: Inclusive,
		}, true
	}
	if end-start <= 1 {
		// Empty delimiters: an inner object with nothing in it.
		return Span{
			From: Pos{cur.Line, start + 1},
			To:   Pos{cur.Line, start},
			Kind: Exclusive,
		}, true
	}
	return Span{
		From: Pos{cur.Line, start + 1},
		To:   Pos{cur.Line, end - 1},
		Kind: Inclusive,
	}, true
}

func paragraphObject(b *Buffer, around bool) (Span, bool) {
	cur := b.cursor
	start, end := cur.Line, cur.Line
	for start > 0 && len(b.lines[start-1]) > 0 {
		start--
	}
	for end+1 < b.Lines() && len(b.lines[end+1]) > 0 {
		end++
	}
	if around {
		for end+1 < b.Lines() && len(b.lines[end+1]) == 0 {
			end++
		}
	}
	return Span{
		From: Pos{start, 0},
		To:   Pos{end, 0},
		Kind: Linewise,
	}, true
}

func sentenceObject(b *Buffer, around bool) (Span, bool) {
	cur := b.cursor
	line := b.lines[cur.Line]
	if len(line) == 0 {
		return Span{}, false
	}
	col := clampInt(cur.Col, 0, len(line)-1)

	start := 0
	for i := col; i > 0; i-- {
		if isSentenceEnd(line[i-1]) {
			start = i
			break
		}
	}
	for start < len(line) && unicode.IsSpace(line[start]) {
		start++
	}

	end := len(line) - 1
	for i := col; i < len(line); i++ {
		if isSentenceEnd(line[i]) {
			end = i
			break
		}
	}
	if around {
		for end+1 < len(line) && unicode.IsSpace(line[end+1]) {
			end++
		}
	}
	return Span{
		From: Pos{cur.Line, start},
		To:   Pos{cur.Line, end},
		Kind: Inclusive,
	}, true
}
