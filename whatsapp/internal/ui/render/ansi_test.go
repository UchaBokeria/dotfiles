package render

import (
	"strings"
	"testing"
)

func TestStripEscapesHandlesColour(t *testing.T) {
	got := StripEscapes("\x1b[38;2;255;0;0mred\x1b[0m")
	if got != "red" {
		t.Errorf("StripEscapes = %q", got)
	}
}

func TestStripEscapesHandlesAHyperlink(t *testing.T) {
	// The bug this exists for: an OSC payload is a URL, so a stripper that
	// ends a sequence at the first letter eats "https" and leaves the rest of
	// the URL as visible text - making every width on the line wrong.
	link := Hyperlink("https://wacli.sh/docs", "wacli.sh")
	got := StripEscapes(link)

	if got != "wacli.sh" {
		t.Fatalf("StripEscapes = %q, want just the shown text", got)
	}
	if strings.Contains(got, "http") {
		t.Errorf("the URL leaked into the visible text: %q", got)
	}
}

func TestVisibleWidthOfAHyperlink(t *testing.T) {
	link := Hyperlink("https://example.com/a/very/long/path", "click")
	if got := VisibleWidth(link); got != 5 {
		t.Errorf("VisibleWidth = %d, want 5 - the length of the shown text", got)
	}
}

func TestVisibleWidthOfAStyledHyperlink(t *testing.T) {
	// Colour inside a link is the shape the renderer actually produces.
	inner := "\x1b[4mwacli.sh\x1b[0m"
	if got := VisibleWidth(Hyperlink("https://wacli.sh", inner)); got != 8 {
		t.Errorf("VisibleWidth = %d, want 8", got)
	}
}

func TestStripEscapesLeavesPlainTextAlone(t *testing.T) {
	for _, s := range []string{"", "hello", "გამარჯობა", "漢字"} {
		if got := StripEscapes(s); got != s {
			t.Errorf("StripEscapes(%q) = %q", s, got)
		}
	}
}

func TestStripEscapesSurvivesATruncatedSequence(t *testing.T) {
	// A sequence cut in half by a column slice must not send the stripper into
	// a loop or make it swallow the rest of the line.
	for _, s := range []string{"abc\x1b", "abc\x1b[", "abc\x1b]8;;http", "\x1b]8;;"} {
		got := StripEscapes(s)
		if strings.Contains(got, "\x1b") {
			t.Errorf("StripEscapes(%q) left an escape: %q", s, got)
		}
	}
}

func TestSplitLinksFindsURLs(t *testing.T) {
	cases := []struct {
		in   string
		want []string
	}{
		{"no links here", nil},
		{"see https://wacli.sh", []string{"https://wacli.sh"}},
		{"https://a.com and https://b.com", []string{"https://a.com", "https://b.com"}},
		{"go to www.example.com", []string{"https://www.example.com"}},
		{"http://plain.example", []string{"http://plain.example"}},
	}
	for _, c := range cases {
		var got []string
		for _, r := range SplitLinks(c.in) {
			if r.URL != "" {
				got = append(got, r.URL)
			}
		}
		if len(got) != len(c.want) {
			t.Errorf("SplitLinks(%q) found %v, want %v", c.in, got, c.want)
			continue
		}
		for i := range got {
			if got[i] != c.want[i] {
				t.Errorf("SplitLinks(%q) found %v, want %v", c.in, got, c.want)
			}
		}
	}
}

func TestSplitLinksLeavesTrailingPunctuationOut(t *testing.T) {
	// A link at the end of a sentence should not swallow the full stop.
	runs := SplitLinks("read https://wacli.sh.")
	var url, tail string
	for _, r := range runs {
		if r.URL != "" {
			url = r.URL
		} else {
			tail += r.Text
		}
	}
	if url != "https://wacli.sh" {
		t.Errorf("url = %q", url)
	}
	if !strings.HasSuffix(tail, ".") {
		t.Errorf("the full stop was swallowed; the remainder was %q", tail)
	}
}

func TestSplitLinksKeepsBalancedBrackets(t *testing.T) {
	// A URL may legitimately contain brackets, so only an unbalanced closing
	// one is punctuation.
	runs := SplitLinks("see https://en.wikipedia.org/wiki/Go_(language)")
	if runs[len(runs)-1].URL != "https://en.wikipedia.org/wiki/Go_(language)" {
		t.Errorf("a balanced bracket was trimmed: %+v", runs)
	}

	runs = SplitLinks("(see https://wacli.sh)")
	for _, r := range runs {
		if r.URL != "" && strings.HasSuffix(r.URL, ")") {
			t.Errorf("an unbalanced bracket was kept: %q", r.URL)
		}
	}
}

func TestSplitLinksRoundTripsTheText(t *testing.T) {
	// Nothing may be lost or duplicated: what is shown must equal the input.
	for _, in := range []string{
		"plain text",
		"https://a.com",
		"before https://a.com after",
		"a https://a.com b https://b.com c",
		"trailing https://a.com.",
	} {
		var b strings.Builder
		for _, r := range SplitLinks(in) {
			b.WriteString(r.Text)
		}
		if b.String() != in {
			t.Errorf("round trip of %q gave %q", in, b.String())
		}
	}
}

func TestFirstLink(t *testing.T) {
	if got := FirstLink("a https://one.com b https://two.com"); got != "https://one.com" {
		t.Errorf("FirstLink = %q", got)
	}
	if got := FirstLink("nothing here"); got != "" {
		t.Errorf("FirstLink = %q, want empty", got)
	}
}

func TestHyperlinkIsWellFormed(t *testing.T) {
	got := Hyperlink("https://wacli.sh", "text")
	if !strings.HasPrefix(got, "\x1b]8;;https://wacli.sh\x1b\\") {
		t.Errorf("bad opener: %q", got)
	}
	if !strings.HasSuffix(got, "\x1b]8;;\x1b\\") {
		t.Errorf("bad closer: %q", got)
	}
}

func TestHyperlinkOfNothing(t *testing.T) {
	if got := Hyperlink("", "text"); got != "text" {
		t.Errorf("a link with no URL should be plain text, got %q", got)
	}
}

func TestTakeAndDropColumns(t *testing.T) {
	s := "abcdef"
	if got := TakeColumns(s, 3); got != "abc" {
		t.Errorf("TakeColumns = %q", got)
	}
	if got := DropColumns(s, 3); got != "def" {
		t.Errorf("DropColumns = %q", got)
	}
	if got := TakeColumns(s, 0); got != "" {
		t.Errorf("TakeColumns(0) = %q", got)
	}
}

func TestTakeColumnsCountsCells(t *testing.T) {
	// Two double-width characters occupy four columns.
	if got := VisibleWidth(TakeColumns("漢字ab", 4)); got != 4 {
		t.Errorf("took %d columns of CJK, want 4", got)
	}
}

func TestTakeColumnsCarriesEscapesThrough(t *testing.T) {
	// The colour a prefix was drawn in must survive being cut, or splicing a
	// menu over a coloured line strips the colour from what is left.
	s := "\x1b[31mred text\x1b[0m"
	got := TakeColumns(s, 3)
	if !strings.Contains(got, "\x1b[31m") {
		t.Errorf("the colour was dropped: %q", got)
	}
	if StripEscapes(got) != "red" {
		t.Errorf("visible text = %q", StripEscapes(got))
	}
}

func TestColumnsAroundAHyperlink(t *testing.T) {
	// Splicing must not cut a link in half at a byte boundary inside the URL.
	s := "go " + Hyperlink("https://wacli.sh", "here") + " now"
	if got := VisibleWidth(s); got != len("go here now") {
		t.Fatalf("VisibleWidth = %d, want %d", got, len("go here now"))
	}
	if got := StripEscapes(TakeColumns(s, 5)); got != "go he" {
		t.Errorf("TakeColumns = %q", got)
	}
}

func TestSplitLinksFindsALinkInsideBrackets(t *testing.T) {
	// A link pasted in parentheses is one whitespace-delimited word. If the
	// opening bracket is treated as part of it, the link is not recognised at
	// all - which is how it read before the leading punctuation came off.
	runs := SplitLinks("(see https://wacli.sh) and [https://b.com]")

	var urls, shown []string
	for _, r := range runs {
		if r.URL != "" {
			urls = append(urls, r.URL)
			shown = append(shown, r.Text)
		}
	}
	if len(urls) != 2 || urls[0] != "https://wacli.sh" || urls[1] != "https://b.com" {
		t.Fatalf("urls = %v", urls)
	}
	for _, s := range shown {
		if strings.ContainsAny(s, "()[]") {
			t.Errorf("punctuation stayed in the link text: %q", s)
		}
	}
}

func TestSplitLinksBracketsRoundTrip(t *testing.T) {
	for _, in := range []string{
		"(https://a.com)",
		"[https://a.com]",
		"\"https://a.com\"",
		"(see https://en.wikipedia.org/wiki/Go_(language)) done",
	} {
		var b strings.Builder
		for _, r := range SplitLinks(in) {
			b.WriteString(r.Text)
		}
		if b.String() != in {
			t.Errorf("round trip of %q gave %q", in, b.String())
		}
	}
}

func TestSplitLinksKeepsABalancedBracketInsideTheURL(t *testing.T) {
	got := FirstLink("(see https://en.wikipedia.org/wiki/Go_(language)) done")
	if got != "https://en.wikipedia.org/wiki/Go_(language)" {
		t.Errorf("FirstLink = %q", got)
	}
}

func TestVisibleWidthOfEmoji(t *testing.T) {
	// A reaction chip is emoji, and getting its width wrong shows up as a
	// bubble border one column out of place.
	cases := []struct {
		in   string
		want int
	}{
		{"👍", 2},
		{"❤️", 2}, // U+2764 with the emoji variation selector
		{"❤", 1},  // and without it
		{"✅", 2},
		{"😂 🔥", 5},
		{"👨‍👩‍👧", 2}, // one glyph, joined by zero-width joiners
		{"🇬🇪", 2},    // a flag is two regional indicators
		{"漢字", 4},
		{"abc", 3},
	}
	for _, c := range cases {
		if got := VisibleWidth(c.in); got != c.want {
			t.Errorf("VisibleWidth(%q) = %d, want %d", c.in, got, c.want)
		}
	}
}

func TestBreadcrumbs(t *testing.T) {
	cases := []struct {
		in    string
		width int
		want  string
	}{
		{"https://wacli.sh/docs/graphics", 60, "wacli.sh › docs › graphics"},
		{"https://www.example.com/a", 60, "example.com › a"},
		{"https://we.tl/t-ABC", 60, "we.tl › t-ABC"},
		{"https://example.com", 60, "example.com"},
		{"https://example.com/a%20b", 60, "example.com › a b"},
		{"https://example.com/x?q=1", 60, "example.com › x › ?"},
	}
	for _, c := range cases {
		if got := Breadcrumbs(c.in, c.width); got != c.want {
			t.Errorf("Breadcrumbs(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestBreadcrumbsDropFromTheMiddle(t *testing.T) {
	// The two ends are the informative ones: which site, and which page.
	got := Breadcrumbs("https://a.example.com/one/two/three/four/five/target", 30)

	if VisibleWidth(got) > 30 {
		t.Errorf("%q is %d columns", got, VisibleWidth(got))
	}
	if !strings.HasPrefix(got, "a.example.com") {
		t.Errorf("the host was trimmed away: %q", got)
	}
	if !strings.Contains(got, "target") {
		t.Errorf("the page was trimmed away: %q", got)
	}
	if !strings.Contains(got, "…") {
		t.Errorf("nothing says the middle is missing: %q", got)
	}
}

func TestBreadcrumbsOfSomethingUnparseable(t *testing.T) {
	if got := Breadcrumbs("not a url", 20); got != "not a url" {
		t.Errorf("got %q", got)
	}
	if got := Breadcrumbs("", 20); got != "" {
		t.Errorf("got %q", got)
	}
}

func TestBreadcrumbsNeverExceedTheWidth(t *testing.T) {
	long := "https://example.com/" + strings.Repeat("segment/", 20) + "end"
	for _, w := range []int{10, 20, 40, 80} {
		if got := Breadcrumbs(long, w); VisibleWidth(got) > w {
			t.Errorf("width %d: %q is %d columns", w, got, VisibleWidth(got))
		}
	}
}

func TestLinksListsThemInOrder(t *testing.T) {
	got := Links("see https://a.com then https://b.com")
	if len(got) != 2 || got[0] != "https://a.com" || got[1] != "https://b.com" {
		t.Errorf("Links = %v", got)
	}
	if got := Links("no links"); got != nil {
		t.Errorf("Links = %v", got)
	}
}

func TestTruncateKeepsStyling(t *testing.T) {
	// Cutting a styled string by grapheme counts the letters of its colour
	// codes as text, so anything styled came out short by however much
	// styling it happened to carry.
	s := "\x1b[31mred and long\x1b[0m"
	got := Truncate(s, 6)

	if w := VisibleWidth(got); w != 6 {
		t.Errorf("Truncate to 6 gave %d columns: %q", w, got)
	}
	if !strings.Contains(got, "\x1b[31m") {
		t.Errorf("the style was dropped: %q", got)
	}
	if !strings.HasSuffix(got, "…") {
		t.Errorf("no ellipsis: %q", got)
	}
}

func TestTruncateOfAHyperlink(t *testing.T) {
	s := "go " + Hyperlink("https://wacli.sh", "somewhere long") + " now"
	if w := VisibleWidth(Truncate(s, 10)); w != 10 {
		t.Errorf("got %d columns", w)
	}
}
