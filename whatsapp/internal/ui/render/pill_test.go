package render

import (
	"strings"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
)

func pillStyles(t *testing.T) theme.Styles {
	t.Helper()
	return withColour(t).WithDesign(theme.ShapePill, theme.NewIcons(theme.IconsNerd, nil))
}

func TestAOneLineMessageIsACapsule(t *testing.T) {
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	for _, fromMe := range []bool{true, false} {
		m := domain.Message{ID: "M", TS: now, Text: "hello", FromMe: fromMe, Delivery: domain.Read}
		rows := Bubble(m, Options{Width: 60, Now: now, Styles: st, Padding: 1})
		if len(rows) != 1 {
			t.Errorf("fromMe=%v: %d rows for one line of text, want 1", fromMe, len(rows))
			continue
		}
		plain := StripEscapes(rows[0])
		if !strings.Contains(plain, "") || !strings.Contains(plain, "") {
			t.Errorf("fromMe=%v: no half-circle caps: %q", fromMe, plain)
		}
		if !strings.Contains(plain, "12:00") {
			t.Errorf("fromMe=%v: the time is not inside the bubble: %q", fromMe, plain)
		}
		if strings.ContainsAny(plain, "▄▀▗▖▝▘") {
			t.Errorf("fromMe=%v: half-block stair corners are back: %q", fromMe, plain)
		}
	}
}

func TestALongMessageIsARoundedCard(t *testing.T) {
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	m := domain.Message{ID: "M", TS: now, Text: strings.Repeat("words that wrap ", 12), FromMe: true, Delivery: domain.Sent}
	rows := Bubble(m, Options{Width: 50, MaxBubble: 40, Now: now, Styles: st, Padding: 1})
	if len(rows) < 4 {
		t.Fatalf("%d rows, want a multi-row card with room for a caption of its own", len(rows))
	}
	// The last row is the lone timestamp, a caption under the card rather than
	// another row of it - see TestALoneTimestampRowIsTransparent - so the card
	// itself is every row except that one, and its own last row is what
	// carries the bottom cap.
	card, caption := rows[:len(rows)-1], rows[len(rows)-1]
	for i, r := range card {
		plain := StripEscapes(r)
		l, rr := st.Shape.Caps()
		capped := strings.Contains(plain, l) || strings.Contains(plain, rr)
		if (i == 0 || i == len(card)-1) != capped {
			t.Errorf("row %d capped=%v; only the first and last rows of the card end in half circles", i, capped)
		}
		if w := VisibleWidth(r); w > 50 {
			t.Errorf("row %d is %d wide in a 50-column pane", i, w)
		}
	}
	if strings.Count(caption, "48;2;") > 0 {
		t.Errorf("the timestamp caption still carries a background fill: %q", caption)
	}
	// Every row - card and caption alike - is the same width, or the card's
	// sides are ragged. Compared whole: a middle row's straight side is a
	// filled space, which a trim would count as margin.
	w0 := VisibleWidth(rows[0])
	for i, r := range rows {
		if w := VisibleWidth(r); w != w0 {
			t.Errorf("row %d is %d wide, the first is %d", i, w, w0)
		}
	}
}

func TestTheSelectedPillBubbleChangesFillNotShape(t *testing.T) {
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	m := domain.Message{ID: "M", TS: now, Text: "hello"}
	plain := Bubble(m, Options{Width: 60, Now: now, Styles: st, Padding: 1})
	sel := Bubble(m, Options{Width: 60, Now: now, Styles: st, Padding: 1, Selected: true})
	if plain[0] == sel[0] {
		t.Error("selection drew nothing different")
	}
	if StripEscapes(plain[0]) != StripEscapes(sel[0]) {
		t.Error("selection changed the bubble's shape")
	}
	if len(plain) != len(sel) {
		t.Error("selection added rows")
	}
}

func TestPillBubblesAtEveryWidthStayInside(t *testing.T) {
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	for _, w := range []int{8, 10, 16, 24, 40, 120} {
		for _, m := range []domain.Message{
			{ID: "A", TS: now, Text: "x", FromMe: true, Delivery: domain.Failed},
			{ID: "B", TS: now, Text: strings.Repeat("long ", 40), SenderName: "Somebody With A Long Name"},
		} {
			for i, r := range Bubble(m, Options{Width: w, Now: now, Styles: st, Padding: 1, ShowSender: true, Marked: true}) {
				if VisibleWidth(r) > w {
					t.Errorf("width %d, message %s, row %d: %d wide", w, m.ID, i, VisibleWidth(r))
				}
			}
		}
	}
}

func TestTheDaySeparatorIsAChip(t *testing.T) {
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	out := StripEscapes(DaySeparator(now, Options{Width: 60, Now: now, Styles: st}, ""))
	if strings.Contains(out, "─") {
		t.Errorf("the day separator still draws a rule: %q", out)
	}
	if !strings.Contains(out, "Today") || !strings.Contains(out, "") {
		t.Errorf("the day separator is not a chip: %q", out)
	}
}

func TestALoneTimestampRowIsTransparent(t *testing.T) {
	// A message whose last line is too full for the time to share pushes the
	// time onto a row of its own. That row is a caption under the bubble, not
	// more of it - filling it in the bubble's own colour grew the bubble
	// downward for a line that is not conversation text.
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	m := domain.Message{ID: "M", TS: now, Text: strings.Repeat("x", 40), FromMe: true, Delivery: domain.Read}
	rows := Bubble(m, Options{Width: 50, MaxBubble: 44, Now: now, Styles: st, Padding: 1})
	last := rows[len(rows)-1]
	if !strings.Contains(StripEscapes(last), "12:00") {
		t.Fatalf("the last row does not carry the time: %q", StripEscapes(last))
	}
	fillCode := "48;2;"
	if strings.Count(last, fillCode) > 0 {
		t.Errorf("the lone timestamp row still carries a background fill: %q", last)
	}
}

func TestReactionsAndTheTimeShareATransparentCaption(t *testing.T) {
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	m := domain.Message{
		ID: "M", TS: now, Text: "hi", FromMe: false,
		Reactions: []domain.Reaction{{Emoji: "👍"}, {Emoji: "❤️"}},
	}
	rows := Bubble(m, Options{Width: 60, Now: now, Styles: st, Padding: 1})
	if len(rows) < 2 {
		t.Fatalf("%d rows, want at least a text row and a reaction row", len(rows))
	}
	last := rows[len(rows)-1]
	plain := StripEscapes(last)
	if !strings.Contains(plain, "👍") && !strings.Contains(plain, "❤") {
		t.Fatalf("the last row does not carry the reactions: %q", plain)
	}
	if strings.Count(last, "48;2;") > 0 {
		t.Errorf("the reaction row still carries a background fill: %q", last)
	}
	// The text row above it is unaffected - it is still a real, filled bubble
	// row.
	if strings.Count(rows[0], "48;2;") == 0 {
		t.Errorf("the text row lost its bubble fill: %q", rows[0])
	}
}

func TestAOneLinerWithATimeThatFitsKeepsItsFill(t *testing.T) {
	// The common case - a short message whose time shares its only row - must
	// not lose the bubble's own background: that would be every ordinary
	// message, not just the decoration under one.
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	m := domain.Message{ID: "M", TS: now, Text: "hi", FromMe: true, Delivery: domain.Read}
	rows := Bubble(m, Options{Width: 60, Now: now, Styles: st, Padding: 1})
	if len(rows) != 1 {
		t.Fatalf("%d rows for a one-word message", len(rows))
	}
	if strings.Count(rows[0], "48;2;") == 0 {
		t.Errorf("a normal one-line bubble lost its fill: %q", rows[0])
	}
}
