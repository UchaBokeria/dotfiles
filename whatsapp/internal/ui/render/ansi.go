package render

import (
	"net/url"
	"strings"
)

// Escape sequence handling.
//
// Two shapes matter here, and conflating them is a real bug rather than a
// pedantic one:
//
//   - CSI, "ESC [ … <letter>", which is how colour arrives. It ends at the
//     first letter.
//   - OSC, "ESC ] … ST", which is how a hyperlink arrives. Its payload is a
//     URL, so it is full of letters, and a stripper that stops at the first
//     one swallows half the link and leaves the rest as visible text.
//
// Getting this wrong makes every width measurement on a line containing a link
// wrong, which misaligns the bubble the link is in.

// StripEscapes removes escape sequences, leaving the text a terminal shows.
func StripEscapes(s string) string {
	if !strings.Contains(s, "\x1b") {
		return s
	}
	var b strings.Builder
	b.Grow(len(s))

	runes := []rune(s)
	for i := 0; i < len(runes); {
		if runes[i] != '\x1b' {
			b.WriteRune(runes[i])
			i++
			continue
		}
		i = skipEscape(runes, i)
	}
	return b.String()
}

// skipEscape returns the index just past the escape sequence starting at i.
func skipEscape(runes []rune, i int) int {
	// A lone ESC at the end of the string.
	if i+1 >= len(runes) {
		return i + 1
	}

	switch runes[i+1] {
	case '[': // CSI: ends at the first letter
		j := i + 2
		for j < len(runes) && !isLetter(runes[j]) {
			j++
		}
		return j + 1

	case ']': // OSC: ends at BEL or ST (ESC \)
		j := i + 2
		for j < len(runes) {
			if runes[j] == '\a' {
				return j + 1
			}
			if runes[j] == '\x1b' && j+1 < len(runes) && runes[j+1] == '\\' {
				return j + 2
			}
			j++
		}
		return j

	case 'P', 'X', '^', '_': // DCS, SOS, PM, APC: end at ST
		j := i + 2
		for j < len(runes) {
			if runes[j] == '\x1b' && j+1 < len(runes) && runes[j+1] == '\\' {
				return j + 2
			}
			j++
		}
		return j

	default:
		// A two-character escape.
		return i + 2
	}
}

func isLetter(r rune) bool {
	return (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z')
}

// Hyperlink wraps text so the terminal makes it clickable.
//
// Terminals that do not understand OSC 8 ignore the sequence and show the text
// unchanged, so this is safe to emit blindly. tmux forwards it from 3.4
// onwards; before that the link is simply not clickable, which is what it
// would have been anyway.
func Hyperlink(url, text string) string {
	if url == "" || text == "" {
		return text
	}
	return "\x1b]8;;" + url + "\x1b\\" + text + "\x1b]8;;\x1b\\"
}

// SplitLinks breaks text into runs, marking which are URLs.
//
// Splitting on whitespace is deliberate: a URL is one word, and anything
// cleverer starts guessing about trailing punctuation in ways that surprise
// people who paste a link inside a sentence.
type Run struct {
	Text string
	URL  string
}

// SplitLinks finds the URLs in a string.
func SplitLinks(s string) []Run {
	if !strings.Contains(s, "://") && !strings.Contains(s, "www.") {
		return []Run{{Text: s}}
	}

	var (
		out  []Run
		cur  strings.Builder
		word strings.Builder
	)
	flushWord := func() {
		w := word.String()
		word.Reset()
		if w == "" {
			return
		}
		lead, url, text, trail := linkOf(w)
		if url == "" {
			cur.WriteString(w)
			return
		}
		cur.WriteString(lead)
		if cur.Len() > 0 {
			out = append(out, Run{Text: cur.String()})
			cur.Reset()
		}
		out = append(out, Run{Text: text, URL: url})
		cur.WriteString(trail)
	}

	for _, r := range s {
		if r == ' ' || r == '\t' || r == '\n' {
			flushWord()
			cur.WriteRune(r)
			continue
		}
		word.WriteRune(r)
	}
	flushWord()

	if cur.Len() > 0 {
		out = append(out, Run{Text: cur.String()})
	}
	return out
}

// linkOf decides whether a word is a link, returning any opening punctuation
// before it, the URL, the text to show, and any trailing punctuation.
//
// The punctuation on both sides has to come off: a link pasted inside brackets
// or quotes - "(https://example.com)" - is one whitespace-delimited word, and
// treating the brackets as part of it both breaks the URL and stops it being
// recognised as one at all.
func linkOf(word string) (leading, url, text, trailing string) {
	body := word
	for len(body) > 0 && strings.IndexByte("([{<\"'", body[0]) >= 0 {
		body = body[1:]
	}
	leading = word[:len(word)-len(body)]

	lower := strings.ToLower(body)
	if !strings.HasPrefix(lower, "http://") &&
		!strings.HasPrefix(lower, "https://") &&
		!strings.HasPrefix(lower, "www.") {
		return "", "", "", ""
	}

	// A link at the end of a sentence collects the full stop. Brackets are
	// kept when they balance, because a URL may legitimately contain them.
	trimmed := body
	for len(trimmed) > 0 {
		last := trimmed[len(trimmed)-1]
		if strings.IndexByte(".,;:!?", last) >= 0 {
			trimmed = trimmed[:len(trimmed)-1]
			continue
		}
		if last == ')' && strings.Count(trimmed, "(") < strings.Count(trimmed, ")") {
			trimmed = trimmed[:len(trimmed)-1]
			continue
		}
		if last == ']' && strings.Count(trimmed, "[") < strings.Count(trimmed, "]") {
			trimmed = trimmed[:len(trimmed)-1]
			continue
		}
		break
	}
	if trimmed == "" {
		return "", "", "", ""
	}

	url = trimmed
	if strings.HasPrefix(strings.ToLower(trimmed), "www.") {
		url = "https://" + trimmed
	}
	return leading, url, trimmed, body[len(trimmed):]
}

// FirstLink returns the first URL in a string, or empty.
func FirstLink(s string) string {
	for _, r := range SplitLinks(s) {
		if r.URL != "" {
			return r.URL
		}
	}
	return ""
}

// TakeColumns returns the prefix of s occupying at most n display columns.
//
// Escape sequences are copied through rather than counted, so the colour a
// prefix was drawn in survives being cut. That matters wherever one rendered
// string is spliced into another - the context menu over the panes, and the
// highlight over a selection.
func TakeColumns(s string, n int) string {
	if n <= 0 {
		return ""
	}
	var b strings.Builder
	runes := []rune(s)
	width := 0

	for i := 0; i < len(runes); {
		if runes[i] == '\x1b' {
			end := skipEscape(runes, i)
			b.WriteString(string(runes[i:end]))
			i = end
			continue
		}
		w := cellWidth(runes[i])
		if width+w > n {
			break
		}
		b.WriteRune(runes[i])
		width += w
		i++
	}
	return b.String()
}

// DropColumns returns the suffix of s beyond n display columns.
func DropColumns(s string, n int) string {
	var b strings.Builder
	runes := []rune(s)
	width := 0

	for i := 0; i < len(runes); {
		if runes[i] == '\x1b' {
			end := skipEscape(runes, i)
			// Escapes before the cut still apply to what follows it.
			b.WriteString(string(runes[i:end]))
			i = end
			continue
		}
		w := cellWidth(runes[i])
		if width >= n {
			b.WriteRune(runes[i])
		}
		width += w
		i++
	}
	return b.String()
}

// underlineOn is written by hand rather than asked of lipgloss.
//
// lipgloss renders an underlined string one rune at a time, wrapping each in
// its own escape pair. That turns a 900-character URL into thirty kilobytes of
// output, and - because every one of those pairs ends in a full reset - it
// strips the bubble's background from every character after the first. The
// reset that closes the colour style turns the underline off again, so nothing
// has to switch it off explicitly.
const underlineOn = "\x1b[4m"

// ReopenAfterResets re-establishes a style after every reset inside a string.
//
// A row of a bubble is drawn in one style, with a background. Anything styled
// inside it - a link, a quote, the "(edited)" marker - ends with a full reset,
// and from that point the row's own colours are gone: the rest of the line,
// padding included, is drawn on the terminal's default background inside what
// is supposed to be a filled box. Putting the row's opening sequence back
// after each inner reset is what keeps the box one colour.
func ReopenAfterResets(s, open string) string {
	if open == "" || !strings.Contains(s, reset) {
		return s
	}
	return strings.ReplaceAll(s, reset, reset+open)
}

const reset = "\x1b[0m"

// StylePrefix is the opening escape sequence a style emits.
//
// lipgloss has no way to ask for it, so it is recovered by rendering a
// sentinel and taking what came before it. The sentinel is a character no
// style can rewrite.
func StylePrefix(rendered, sentinel string) string {
	i := strings.Index(rendered, sentinel)
	if i < 0 {
		return ""
	}
	return rendered[:i]
}

// Breadcrumbs turns a URL into something readable at a glance.
//
// A raw URL in a status line is unreadable: the scheme, the host, a long path
// and a query string all run together, and the part that says what the link
// actually is sits in the middle. Splitting it the way a browser's breadcrumb
// bar does puts the host first and the last path segment - the part that names
// the thing - at the end, where the eye stops.
func Breadcrumbs(rawURL string, width int) string {
	u, err := url.Parse(rawURL)
	if err != nil || u.Host == "" {
		return Truncate(rawURL, width)
	}

	parts := []string{strings.TrimPrefix(u.Host, "www.")}
	for _, seg := range strings.Split(strings.Trim(u.Path, "/"), "/") {
		if seg == "" {
			continue
		}
		if unescaped, err := url.PathUnescape(seg); err == nil {
			seg = unescaped
		}
		parts = append(parts, seg)
	}
	if u.RawQuery != "" {
		parts = append(parts, "?")
	}

	// Dropping from the middle keeps the two informative ends: which site, and
	// which page. Trimming from the right loses the page; trimming from the
	// left loses the site.
	host, rest := parts[0], parts[1:]
	elided := false

	compose := func() string {
		out := append([]string{host}, rest...)
		if elided {
			out = append([]string{host, "…"}, rest...)
		}
		return strings.Join(out, breadcrumbSep)
	}
	for len(rest) > 1 && VisibleWidth(compose()) > width {
		rest = rest[1:]
		elided = true
	}
	return Truncate(compose(), width)
}

// breadcrumbSep is what separates the parts of a link.
const breadcrumbSep = " › "

// Links lists every URL in a string, in the order they appear.
func Links(s string) []string {
	var out []string
	for _, r := range SplitLinks(s) {
		if r.URL != "" {
			out = append(out, r.URL)
		}
	}
	return out
}
