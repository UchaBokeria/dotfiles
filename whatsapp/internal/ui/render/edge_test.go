package render

import (
	"strings"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

func TestHighlightWithRegexCharactersAndOddPatterns(t *testing.T) {
	st := withColour(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	for _, c := range []struct{ text, pattern string }{
		{"price (in $) is [5.00]", "($)"},
		{"a.b.c", "."},
		{"short", "a pattern longer than the whole line"},
		{"🔥🔥 fire 🔥", "🔥"},
		{"ÀÉÎ upper", "àéî"},
		{"aaaa", "aa"},
	} {
		m := domain.Message{ID: "M", TS: now, Text: c.text}
		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("highlighting %q in %q panicked: %v", c.pattern, c.text, r)
				}
			}()
			out := Bubble(m, Options{Width: 60, Now: now, Styles: st, Highlight: c.pattern, HighlightFold: true})
			if !strings.Contains(StripEscapes(strings.Join(out, "\n")), c.text) {
				t.Errorf("highlighting %q changed the text %q", c.pattern, c.text)
			}
		}()
	}
}

func TestAMarkedAndSelectedBubbleKeepsItsShape(t *testing.T) {
	st := withColour(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	for _, fromMe := range []bool{true, false} {
		m := domain.Message{ID: "M", TS: now, Text: "hello", FromMe: fromMe}
		plain := Bubble(m, Options{Width: 40, Now: now, Styles: st})
		marked := Bubble(m, Options{Width: 40, Now: now, Styles: st, Marked: true, Selected: true})
		if len(plain) != len(marked) {
			t.Errorf("fromMe=%v: marking changed the row count %d -> %d", fromMe, len(plain), len(marked))
		}
		for i := range plain {
			if VisibleWidth(plain[i]) != VisibleWidth(marked[i]) {
				t.Errorf("fromMe=%v row %d: width %d -> %d", fromMe, i,
					VisibleWidth(plain[i]), VisibleWidth(marked[i]))
			}
		}
	}
}

func TestBubbleAtAbsurdWidths(t *testing.T) {
	st := withColour(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	m := domain.Message{ID: "M", TS: now, Text: strings.Repeat("word ", 50), FromMe: true, Delivery: domain.Read}
	for _, w := range []int{0, 1, 7, 8, 9, 12, 500} {
		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("width %d panicked: %v", w, r)
				}
			}()
			for i, l := range Bubble(m, Options{Width: w, Now: now, Styles: st, Marked: true, Highlight: "word"}) {
				if w >= 8 && VisibleWidth(l) > w {
					t.Errorf("width %d: row %d is %d wide", w, i, VisibleWidth(l))
				}
			}
		}()
	}
}
