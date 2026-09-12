package render

import (
	"strings"
	"testing"
	"time"

	"github.com/charmbracelet/lipgloss"
	"github.com/muesli/termenv"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
)

// The golden tests run without colour, which is what keeps them about layout.
// These are the opposite: they exist only to check the escape sequences, so
// they turn colour on for their own duration.
func withColour(t *testing.T) theme.Styles {
	t.Helper()
	old := lipgloss.ColorProfile()
	lipgloss.SetColorProfile(termenv.TrueColor)
	t.Cleanup(func() { lipgloss.SetColorProfile(old) })

	p, err := theme.Load("")
	if err != nil {
		t.Fatal(err)
	}
	return theme.New(p, "rounded")
}

func TestReopenAfterResets(t *testing.T) {
	got := ReopenAfterResets("a\x1b[0mb\x1b[0mc", "<OPEN>")
	if got != "a\x1b[0m<OPEN>b\x1b[0m<OPEN>c" {
		t.Errorf("got %q", got)
	}
	if got := ReopenAfterResets("plain", "<OPEN>"); got != "plain" {
		t.Errorf("nothing to reopen, got %q", got)
	}
	if got := ReopenAfterResets("a\x1b[0mb", ""); got != "a\x1b[0mb" {
		t.Errorf("no style to reopen, got %q", got)
	}
}

func TestStylePrefix(t *testing.T) {
	if got := StylePrefix("\x1b[31mX\x1b[0m", "X"); got != "\x1b[31m" {
		t.Errorf("got %q", got)
	}
	if got := StylePrefix("no sentinel", "X"); got != "" {
		t.Errorf("got %q", got)
	}
}

// bubbleBackground is the SGR the body of a bubble is drawn on.
func bubbleBackground(t *testing.T, st theme.Styles) string {
	t.Helper()
	open := StylePrefix(st.BubbleTheirs.Render("X"), "X")
	if open == "" {
		t.Fatal("the bubble style has no opening sequence")
	}
	return open
}

// lastStyleBefore walks a line and reports the style in force at the end.
func endsStyled(line, open string) bool {
	i := strings.LastIndex(line, open)
	if i < 0 {
		return false
	}
	// Nothing may reset after the last time the style was set, except the
	// reset that closes the line.
	rest := line[i+len(open):]
	return strings.Count(rest, "\x1b[0m") <= 1
}

func TestALinkDoesNotStripTheBubbleBackground(t *testing.T) {
	// Every styled span inside a bubble ends with a full reset. Left alone,
	// that reset takes the bubble's background with it, and the rest of the
	// row - padding and right border included - is drawn on the terminal's
	// own background inside what should be a filled box.
	st := withColour(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)

	lines := Bubble(domain.Message{Text: "see https://we.tl/t-ABC ok", TS: now}, Options{
		Width: 50, Links: true, Now: now, Styles: st,
	})
	open := bubbleBackground(t, st)

	body := lines[1]
	if !strings.Contains(body, "]8;;") {
		t.Fatalf("no hyperlink in %q", body)
	}
	if !endsStyled(body, open) {
		t.Errorf("the bubble style is not in force at the end of the row:\n%q", body)
	}
}

func TestAMarkerDoesNotStripTheBubbleBackground(t *testing.T) {
	st := withColour(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)

	lines := Bubble(domain.Message{Text: "hello", TS: now, Edited: true}, Options{
		Width: 40, Now: now, Styles: st,
	})
	open := bubbleBackground(t, st)

	for _, l := range lines {
		if !strings.Contains(l, "(edited)") {
			continue
		}
		if !endsStyled(l, open) {
			t.Errorf("the bubble style is not in force after the marker:\n%q", l)
		}
		return
	}
	t.Fatal("no (edited) row was drawn")
}

func TestALinkIsOneEscapePairNotOnePerCharacter(t *testing.T) {
	// lipgloss renders an underlined string one rune at a time. A 900
	// character URL - and WhatsApp carries those - becomes thirty kilobytes of
	// escapes, redrawn on every keystroke.
	st := withColour(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)

	url := "https://example.com/" + strings.Repeat("x", 40)
	lines := Bubble(domain.Message{Text: url, TS: now}, Options{
		Width: 100, Links: true, Now: now, Styles: st,
	})

	joined := strings.Join(lines, "\n")
	if n := strings.Count(joined, "\x1b[0m"); n > len(lines)*3 {
		t.Errorf("%d resets across %d lines - the link was styled per character",
			n, len(lines))
	}
	if !strings.Contains(joined, underlineOn) {
		t.Error("the link is not underlined")
	}
}

func TestAPlainBubbleIsUnchanged(t *testing.T) {
	// The reopen pass must not touch a row with nothing styled inside it.
	st := withColour(t)
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)

	lines := Bubble(domain.Message{Text: "hello", TS: now}, Options{
		Width: 40, Now: now, Styles: st,
	})
	for _, l := range lines[:2] {
		if n := strings.Count(l, "\x1b[0m"); n != 1 {
			t.Errorf("%d resets in a plain row: %q", n, l)
		}
	}
}

func TestABubbleWithAReactionStaysSquare(t *testing.T) {
	// "❤️" is two runes wide by the rune tables and two cells on screen. The
	// bubble measured it as one, so every row of a reacted message came out a
	// column short and the box looked broken.
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)
	opts := Options{Width: 50, Now: now, Styles: plainStyles(t)}

	for _, emoji := range []string{"👍", "❤️", "✅", "🇬🇪", "👨‍👩‍👧"} {
		lines := Bubble(domain.Message{
			Text:      "wa socket probe 1",
			TS:        now,
			Reactions: []domain.Reaction{{Emoji: emoji, ByName: "Ucha"}},
		}, opts)

		want := VisibleWidth(lines[0])
		for i, l := range lines[:len(lines)-1] {
			if got := VisibleWidth(l); got != want {
				t.Errorf("%s: row %d is %d columns, the box is %d:\n%s",
					emoji, i, got, want, strings.Join(lines, "\n"))
				break
			}
		}
	}
}

func TestASolidBubbleHasSoftEdgesAndNoFrame(t *testing.T) {
	// Drawn with the fill as their background, a framed bubble's line
	// characters leave a square of colour around the frame. A solid bubble is
	// the fill itself, rounded off by half-block edges.
	p, err := theme.Load("")
	if err != nil {
		t.Fatal(err)
	}
	st := theme.New(p, "solid")
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)

	lines := Bubble(domain.Message{Text: "hello there", TS: now}, Options{
		Width: 40, Now: now, Styles: st,
	})
	plain := make([]string, len(lines))
	for i, l := range lines {
		plain[i] = StripEscapes(l)
	}

	if !strings.Contains(plain[0], "▗") || !strings.Contains(plain[0], "▖") {
		t.Errorf("top row = %q, want quadrant corners", plain[0])
	}
	if !strings.Contains(plain[len(plain)-1], "▝") {
		t.Errorf("bottom row = %q, want quadrant corners", plain[len(plain)-1])
	}
	for _, l := range plain {
		if strings.ContainsAny(l, "│╭╮╰╯") {
			t.Errorf("a solid bubble drew a frame: %q", l)
		}
	}
	if !strings.Contains(plain[1], "hello there") {
		t.Errorf("body = %q", plain[1])
	}
}

func TestSolidEdgesDoNotCarryTheFill(t *testing.T) {
	// The edge rows are half blocks in the bubble's colour on the terminal's
	// background. With the fill as their background too, the half of the cell
	// the glyph leaves empty is filled anyway and the soft edge is square.
	st := withColour(t)
	p, _ := theme.Load("")
	st = theme.New(p, "solid")
	now := time.Date(2026, 9, 9, 12, 0, 0, 0, time.UTC)

	lines := Bubble(domain.Message{Text: "hi", TS: now}, Options{Width: 40, Now: now, Styles: st})
	if strings.Contains(lines[0], "48;2;") {
		t.Errorf("the top edge has a background: %q", lines[0])
	}
	if !strings.Contains(lines[1], "48;2;") {
		t.Errorf("the body has no background: %q", lines[1])
	}
}
