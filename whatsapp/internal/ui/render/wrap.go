// Package render turns messages into terminal lines.
//
// Nothing here knows about the store, the network, or key handling: it takes a
// domain.Message and a width and returns strings. That is what lets the layout
// be pinned down by golden files at several widths.
package render

import (
	"strings"

	"github.com/mattn/go-runewidth"
	"github.com/rivo/uniseg"
)

// VisibleWidth is how many terminal cells a string occupies, ignoring ANSI
// escapes. A CJK character takes two cells and a combining mark takes none, so
// counting runes would misalign every bubble that contains either.
func VisibleWidth(s string) int {
	return runewidth.StringWidth(stripANSI(s))
}

// stripANSI removes escape sequences so width measurement sees only text.
func stripANSI(s string) string {
	if !strings.Contains(s, "\x1b") {
		return s
	}
	var b strings.Builder
	for i := 0; i < len(s); {
		if s[i] == '\x1b' {
			// Skip to the end of the sequence: a letter terminates CSI.
			j := i + 1
			for j < len(s) && !isANSITerminator(s[j]) {
				j++
			}
			i = j + 1
			continue
		}
		b.WriteByte(s[i])
		i++
	}
	return b.String()
}

func isANSITerminator(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
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
		w := runewidth.StringWidth(cluster)
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
		w := runewidth.StringWidth(cluster)
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
	var (
		b    strings.Builder
		curW int
	)
	g := uniseg.NewGraphemes(s)
	for g.Next() {
		cluster := g.Str()
		w := runewidth.StringWidth(cluster)
		if curW+w > width-1 {
			break
		}
		b.WriteString(cluster)
		curW += w
	}
	return b.String() + "…"
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
