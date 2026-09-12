package render

import (
	"strings"
	"testing"
)

// flatten joins a wrapped line back into the text it shows.
func flatten(runs []Run) string {
	var b strings.Builder
	for _, r := range runs {
		b.WriteString(r.Text)
	}
	return b.String()
}

func TestWrapLinksWrapsLikeWrap(t *testing.T) {
	// The two wrappers must agree, or turning links on would reflow the whole
	// conversation.
	cases := []string{
		"",
		"short",
		"the quick brown fox jumps over the lazy dog",
		"a https://example.com/some/path b c d e f g h i j k l",
		"averylongwordthatcannotpossiblyfitonasinglelineofthiswidth",
		"first line\nsecond line with https://a.com in it",
		"trailing spaces   ",
		"  leading spaces",
		"漢字 漢字 漢字 漢字 漢字 漢字 漢字 漢字",
	}
	for _, width := range []int{8, 20, 40} {
		for _, in := range cases {
			plain := Wrap(in, width)
			var linked []string
			for _, runs := range WrapLinks(in, width) {
				linked = append(linked, flatten(runs))
			}
			if len(plain) != len(linked) {
				t.Errorf("width %d, %q: %d lines vs %d\n plain=%q\nlinked=%q",
					width, in, len(plain), len(linked), plain, linked)
				continue
			}
			for i := range plain {
				if plain[i] != linked[i] {
					t.Errorf("width %d, %q line %d: %q vs %q", width, in, i, plain[i], linked[i])
				}
			}
		}
	}
}

func TestWrapLinksMarksAWholeURL(t *testing.T) {
	lines := WrapLinks("go to https://wacli.sh now", 40)
	if len(lines) != 1 {
		t.Fatalf("got %d lines", len(lines))
	}
	var found string
	for _, r := range lines[0] {
		if r.URL != "" {
			found = r.URL
		}
	}
	if found != "https://wacli.sh" {
		t.Errorf("url = %q", found)
	}
}

func TestWrapLinksKeepsASplitURLWhole(t *testing.T) {
	// A URL wider than the bubble has to be cut, but every piece must still
	// point at the whole URL: OSC 8 joins runs with the same target back into
	// one link, so the user can click either half.
	url := "https://example.com/a/very/long/path/that/will/not/fit/anywhere"
	lines := WrapLinks("see "+url, 20)
	if len(lines) < 3 {
		t.Fatalf("expected the URL to break over several lines, got %d", len(lines))
	}

	pieces := 0
	var rebuilt strings.Builder
	for _, line := range lines {
		for _, r := range line {
			if r.URL == "" {
				continue
			}
			if r.URL != url {
				t.Fatalf("a piece points at %q, not the whole URL", r.URL)
			}
			pieces++
			rebuilt.WriteString(r.Text)
		}
	}
	if pieces < 2 {
		t.Fatalf("the URL was not split; got %d pieces", pieces)
	}
	if rebuilt.String() != url {
		t.Errorf("the pieces rebuild %q, not the URL", rebuilt.String())
	}
}

func TestWrapLinksMergesAdjacentPlainRuns(t *testing.T) {
	// One run per word would wrap every word in its own escape sequence.
	lines := WrapLinks("a b c d e", 40)
	if len(lines[0]) != 1 {
		t.Errorf("plain text became %d runs: %+v", len(lines[0]), lines[0])
	}
}

func TestWrapLinksRespectsTheWidth(t *testing.T) {
	long := "https://example.com/" + strings.Repeat("x", 60)
	for _, width := range []int{10, 25, 33} {
		for _, line := range WrapLinks("look at "+long+" ok", width) {
			if w := VisibleWidth(flatten(line)); w > width {
				t.Errorf("width %d: a line is %d columns: %q", width, w, flatten(line))
			}
		}
	}
}

func TestWrapLinksFindsALinkAfterAnOpeningBracket(t *testing.T) {
	lines := WrapLinks("(https://wacli.sh)", 40)
	var url string
	for _, r := range lines[0] {
		if r.URL != "" {
			url = r.URL
		}
	}
	if url != "https://wacli.sh" {
		t.Errorf("url = %q", url)
	}
}
