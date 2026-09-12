// Package render turns messages into terminal lines.
//
// Nothing here knows about the store, the network, or key handling: it takes a
// domain.Message and a width and returns strings. That is what lets the layout
// be pinned down by golden files at several widths.
package render

import (
	"strings"

	"github.com/rivo/uniseg"
)

// cells is how many terminal columns a string occupies.
//
// It has to be measured per grapheme cluster, not per rune. "❤️" is U+2764
// followed by the variation selector U+FE0F: rune widths give 1 + 0, every
// terminal draws 2, and the bubble around a reaction chip came out one column
// short. The same applies to a family emoji, which is several people joined by
// zero-width joiners and drawn as one glyph.
func cells(s string) int { return uniseg.StringWidth(s) }

// VisibleWidth is how many terminal cells a string occupies, ignoring ANSI
// escapes. A CJK character takes two cells and a combining mark takes none, so
// counting runes would misalign every bubble that contains either.
func VisibleWidth(s string) int {
	return cells(StripEscapes(s))
}

// Wrap breaks text to a width, preferring whitespace and hard-breaking a token
// that is too long to fit on its own.
//
// It splits on grapheme clusters, not runes: a flag emoji or a skin-tone
// modifier is several runes that must never be separated, and breaking one
// leaves visible mojibake rather than a wrapped line.
func Wrap(s string, width int) []string {
	if width <= 0 {
		return []string{s}
	}
	var out []string
	for _, para := range strings.Split(s, "\n") {
		out = append(out, wrapLine(para, width)...)
	}
	return out
}

func wrapLine(s string, width int) []string {
	if s == "" {
		return []string{""}
	}
	var (
		lines   []string
		cur     strings.Builder
		curW    int
		word    strings.Builder
		wordW   int
		spaces  strings.Builder
		spacesW int
	)

	flushWord := func() {
		if wordW == 0 {
			return
		}
		// The word fits after the pending spaces.
		if curW+spacesW+wordW <= width {
			cur.WriteString(spaces.String())
			curW += spacesW
			cur.WriteString(word.String())
			curW += wordW
		} else {
			if curW > 0 {
				lines = append(lines, cur.String())
				cur.Reset()
				curW = 0
			}
			// A word longer than the whole width has to be cut. Every chunk
			// but the last becomes a line of its own; the last stays current
			// so the following word can share the line with it.
			if wordW > width {
				chunks := hardBreak(word.String(), width)
				for i, chunk := range chunks {
					if i < len(chunks)-1 {
						lines = append(lines, chunk)
						continue
					}
					cur.WriteString(chunk)
					curW = VisibleWidth(chunk)
				}
			} else {
				cur.WriteString(word.String())
				curW = wordW
			}
		}
		word.Reset()
		wordW = 0
		spaces.Reset()
		spacesW = 0
	}

	g := uniseg.NewGraphemes(s)
	for g.Next() {
		cluster := g.Str()
		w := cells(cluster)
		if cluster == " " || cluster == "\t" {
			flushWord()
			spaces.WriteString(cluster)
			spacesW += w
			if w == 0 {
				spacesW++
			}
			continue
		}
		word.WriteString(cluster)
		wordW += w
	}
	flushWord()

	if curW > 0 || len(lines) == 0 {
		lines = append(lines, cur.String())
	}
	return lines
}

// hardBreak cuts a single long token into width-sized pieces on grapheme
// boundaries.
func hardBreak(s string, width int) []string {
	var (
		out  []string
		cur  strings.Builder
		curW int
	)
	g := uniseg.NewGraphemes(s)
	for g.Next() {
		cluster := g.Str()
		w := cells(cluster)
		if curW+w > width && curW > 0 {
			out = append(out, cur.String())
			cur.Reset()
			curW = 0
		}
		cur.WriteString(cluster)
		curW += w
	}
	if curW > 0 {
		out = append(out, cur.String())
	}
	return out
}

// cellWidth is how many columns one rune occupies. Used only where the input
// is already known to be a single rune, such as walking an escape sequence.
func cellWidth(r rune) int { return cells(string(r)) }

// Truncate shortens a string to a width, appending an ellipsis when it had to
// cut. Used for chat names and message snippets in the list.
func Truncate(s string, width int) string {
	if width <= 0 {
		return ""
	}
	if VisibleWidth(s) <= width {
		return s
	}
	if width == 1 {
		return "…"
	}
	// Escape sequences are carried through rather than counted. Cutting a
	// styled string by grapheme would count the letters of its colour codes as
	// text, so a header or a menu row came out short by however much styling
	// it happened to carry.
	return TakeColumns(s, width-1) + "…"
}

// Pad right-pads a string to a width with spaces.
func Pad(s string, width int) string {
	if gap := width - VisibleWidth(s); gap > 0 {
		return s + strings.Repeat(" ", gap)
	}
	return s
}

// PadLeft left-pads a string to a width with spaces.
func PadLeft(s string, width int) string {
	if gap := width - VisibleWidth(s); gap > 0 {
		return strings.Repeat(" ", gap) + s
	}
	return s
}

// linkToken is one wrappable unit: a run of spaces, or a word that may be part
// of a URL.
type linkToken struct {
	text  string
	url   string
	space bool
}

// WrapLinks wraps text to a width while keeping track of which parts are URLs.
//
// Finding the links before wrapping is what lets a URL too long for the bubble
// stay a single link: every piece it breaks into carries the whole URL, and
// the terminal joins them back up because each piece is emitted with the same
// OSC 8 target. Doing it the other way round - wrap, then look for links in
// each line - loses any URL the wrap split, and never sees one that starts
// mid-line after an opening bracket.
//
// Wrapping the escape sequences themselves is not an option either: the
// wrapper counts columns, and an escape is invisible but not empty.
func WrapLinks(s string, width int) [][]Run {
	if width <= 0 {
		return [][]Run{{{Text: s}}}
	}
	var out [][]Run
	for _, para := range strings.Split(s, "\n") {
		out = append(out, wrapTokens(linkTokens(para), width)...)
	}
	return out
}

// linkTokens splits one paragraph into words and gaps, tagging the words that
// are URLs.
func linkTokens(para string) []linkToken {
	var toks []linkToken
	for _, run := range SplitLinks(para) {
		if run.URL != "" {
			// A URL never contains whitespace, so it is exactly one word.
			toks = append(toks, linkToken{text: run.Text, url: run.URL})
			continue
		}
		var (
			cur     strings.Builder
			curKind = -1 // -1 nothing yet, 0 word, 1 space
		)
		flush := func() {
			if cur.Len() > 0 {
				toks = append(toks, linkToken{text: cur.String(), space: curKind == 1})
				cur.Reset()
			}
		}
		g := uniseg.NewGraphemes(run.Text)
		for g.Next() {
			cluster := g.Str()
			kind := 0
			if cluster == " " || cluster == "\t" {
				kind = 1
			}
			if kind != curKind {
				flush()
				curKind = kind
			}
			cur.WriteString(cluster)
		}
		flush()
	}
	return toks
}

// wrapTokens is wrapLine over tokens rather than characters. The two follow
// the same rules - break at a gap, hard-break a token wider than the line -
// so that text wraps identically whether or not link detection is on.
func wrapTokens(toks []linkToken, width int) [][]Run {
	var (
		lines   [][]Run
		cur     []Run
		curW    int
		pending string
		pendW   int
	)

	appendRun := func(r Run) {
		// Merging keeps a line from becoming one run per word, which would
		// emit a separate escape sequence around every one of them.
		if n := len(cur); n > 0 && cur[n-1].URL == r.URL {
			cur[n-1].Text += r.Text
			return
		}
		cur = append(cur, r)
	}

	for _, tok := range toks {
		w := VisibleWidth(tok.text)
		if tok.space {
			pending += tok.text
			pendW += w
			continue
		}
		switch {
		case curW+pendW+w <= width:
			if pending != "" {
				appendRun(Run{Text: pending})
				curW += pendW
			}
			appendRun(Run{Text: tok.text, URL: tok.url})
			curW += w

		default:
			if curW > 0 {
				lines = append(lines, cur)
				cur = nil
				curW = 0
			}
			if w > width {
				chunks := hardBreak(tok.text, width)
				for i, chunk := range chunks {
					if i < len(chunks)-1 {
						lines = append(lines, []Run{{Text: chunk, URL: tok.url}})
						continue
					}
					appendRun(Run{Text: chunk, URL: tok.url})
					curW = VisibleWidth(chunk)
				}
			} else {
				appendRun(Run{Text: tok.text, URL: tok.url})
				curW = w
			}
		}
		pending = ""
		pendW = 0
	}

	// Trailing spaces are dropped: they would pad the line out and, in a
	// bubble, push the right border across.
	if len(cur) > 0 || len(lines) == 0 {
		lines = append(lines, cur)
	}
	return lines
}
