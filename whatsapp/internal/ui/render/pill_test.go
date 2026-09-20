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
		// The time always sits on a transparent caption under the bubble -
		// see TestALoneTimestampRowIsTransparent - so a one-line message is
		// the capsule plus that caption, not the capsule alone.
		if len(rows) != 2 {
			t.Fatalf("fromMe=%v: %d rows for one line of text, want 2 (capsule, time caption)", fromMe, len(rows))
		}
		plain := StripEscapes(rows[0])
		l, r := st.Shape.Caps()
		if !strings.Contains(plain, l) || !strings.Contains(plain, r) {
			t.Errorf("fromMe=%v: no half-circle caps: %q", fromMe, plain)
		}
		if strings.Contains(plain, "12:00") {
			t.Errorf("fromMe=%v: the time is inside the bubble, want it on its own caption: %q", fromMe, plain)
		}
		if strings.ContainsAny(plain, "▄▀▗▖▝▘") {
			t.Errorf("fromMe=%v: half-block stair corners are back: %q", fromMe, plain)
		}
		caption := StripEscapes(rows[1])
		if !strings.Contains(caption, "12:00") {
			t.Errorf("fromMe=%v: the caption does not carry the time: %q", fromMe, caption)
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
	// itself is every row except that one.
	card, caption := rows[:len(rows)-1], rows[len(rows)-1]
	l, r := st.Shape.Caps()
	for i, row := range card {
		plain := StripEscapes(row)
		// The round cap glyph renders wider than the flat sides used between
		// rows: a card of more than one row wearing it only on the first and
		// last stepped out past its own straight sides. Every row of a
		// multi-row card goes flat instead, cap included - see the CardEdges
		// doc comment on Options.
		if strings.Contains(plain, l) || strings.Contains(plain, r) {
			t.Errorf("row %d of %d carries a round cap; a multi-row card should be flat all the way down: %q", i, len(card), plain)
		}
		if strings.Count(row, "48;2;") == 0 {
			t.Errorf("row %d lost its bubble fill: %q", i, plain)
		}
		if w := VisibleWidth(row); w > 50 {
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
	for i, row := range rows {
		if w := VisibleWidth(row); w != w0 {
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

func TestReactionsAndTheTimeCaptionsAreBothTransparent(t *testing.T) {
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	m := domain.Message{
		ID: "M", TS: now, Text: "hi", FromMe: false,
		Reactions: []domain.Reaction{{Emoji: "👍"}, {Emoji: "❤️"}},
	}
	rows := Bubble(m, Options{Width: 60, Now: now, Styles: st, Padding: 1})
	// The time always sits on its own caption under the bubble, never sharing
	// a row with the reactions above it - see TestALoneTimestampRowIsTransparent -
	// so a reacted-to message is: text row, reaction caption, time caption.
	if len(rows) != 3 {
		t.Fatalf("%d rows, want a text row, a reaction caption and a time caption", len(rows))
	}
	reactionRow, timeRow := rows[1], rows[2]
	plain := StripEscapes(reactionRow)
	if !strings.Contains(plain, "👍") && !strings.Contains(plain, "❤") {
		t.Fatalf("the middle row does not carry the reactions: %q", plain)
	}
	if strings.Count(reactionRow, "48;2;") > 0 {
		t.Errorf("the reaction row still carries a background fill: %q", reactionRow)
	}
	if !strings.Contains(StripEscapes(timeRow), "12:00") {
		t.Fatalf("the last row does not carry the time: %q", StripEscapes(timeRow))
	}
	if strings.Count(timeRow, "48;2;") > 0 {
		t.Errorf("the time row still carries a background fill: %q", timeRow)
	}
	// The text row above them is unaffected - it is still a real, filled
	// bubble row.
	if strings.Count(rows[0], "48;2;") == 0 {
		t.Errorf("the text row lost its bubble fill: %q", rows[0])
	}
}
func TestAOneLinerWithATimeThatFitsAlsoGetsAFloatingCaption(t *testing.T) {
	// A short message and a long one must look the same: both a filled text
	// row and a transparent time caption underneath, not one carrying the
	// time inline just because it happened to fit and the other not.
	st := pillStyles(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	m := domain.Message{ID: "M", TS: now, Text: "hi", FromMe: true, Delivery: domain.Read}
	rows := Bubble(m, Options{Width: 60, Now: now, Styles: st, Padding: 1})
	if len(rows) != 2 {
		t.Fatalf("%d rows for a one-word message, want a text row and a time caption", len(rows))
	}
	if strings.Count(rows[0], "48;2;") == 0 {
		t.Errorf("a normal one-line bubble lost its fill: %q", rows[0])
	}
	caption := StripEscapes(rows[1])
	if !strings.Contains(caption, "12:00") {
		t.Errorf("the caption does not carry the time: %q", caption)
	}
	if strings.Count(rows[1], "48;2;") > 0 {
		t.Errorf("the time caption still carries a background fill: %q", rows[1])
	}
}
