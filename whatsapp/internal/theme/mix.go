package theme

import (
	"fmt"
	"math"
	"strconv"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Mix blends two #RRGGBB colours, t of the way from a to b.
//
// It exists so a derived role - a selected bubble lifted toward the accent -
// follows whatever palette is loaded instead of being a colour literal that is
// right for one wallpaper and wrong for the next. A malformed input returns a
// unchanged: a theme with one bad value should look slightly off, not crash.
func Mix(a, b string, t float64) string {
	ar, ag, ab, ok1 := parseHex(a)
	br, bg, bb, ok2 := parseHex(b)
	if !ok1 || !ok2 {
		return a
	}
	if t < 0 {
		t = 0
	}
	if t > 1 {
		t = 1
	}
	lerp := func(x, y int) int { return int(float64(x) + (float64(y)-float64(x))*t + 0.5) }
	return fmt.Sprintf("#%02X%02X%02X", lerp(ar, br), lerp(ag, bg), lerp(ab, bb))
}

func parseHex(s string) (int, int, int, bool) {
	s = strings.TrimPrefix(s, "#")
	if len(s) != 6 {
		return 0, 0, 0, false
	}
	v, err := strconv.ParseUint(s, 16, 32)
	if err != nil {
		return 0, 0, 0, false
	}
	return int(v >> 16 & 0xff), int(v >> 8 & 0xff), int(v & 0xff), true
}

// SelectedFill is a surface lifted toward the accent, far enough to read as
// chosen against its neighbours. The palette's own selection role is tuned for
// a highlight on the background, and on a bubble that is already off the
// background it all but disappears.
func (p Palette) SelectedFill(surface string) string { return Mix(surface, p.Accent, 0.28) }

// Card wraps rows in the configured shape: half circles at the ends of the
// first and last rows, half-block sides on the rows between, the fill behind
// all of it. One row is a pill. Rows must already be exactly width cells.
//
// It is the popups' version of a bubble, so the key menu, the context menu
// and the pickers share one silhouette with the conversation.
func (s Styles) Card(rows []string, fillHex string) []string {
	p := s.Palette
	fill := lipgloss.NewStyle().Foreground(lipgloss.Color(p.Fg)).Background(lipgloss.Color(fillHex))
	edge := lipgloss.NewStyle().Foreground(lipgloss.Color(fillHex))
	if !s.Glass {
		edge = edge.Background(lipgloss.Color(p.Bg))
	}
	l, r := s.Shape.Caps()
	out := make([]string, len(rows))
	for i, row := range rows {
		left, right := edge.Render(l), edge.Render(r)
		if s.Shape == ShapeSquare {
			left, right = fill.Render(" "), fill.Render(" ")
		} else if len(rows) > 2 && i != 0 && i != len(rows)-1 {
			left, right = edge.Render("▐"), edge.Render("▌")
		}
		out[i] = left + row + right
	}
	return out
}

// Contrast is the WCAG contrast ratio of two #RRGGBB colours, 1 to 21.
func Contrast(a, b string) float64 {
	la, ok1 := luminance(a)
	lb, ok2 := luminance(b)
	if !ok1 || !ok2 {
		return 21
	}
	if la < lb {
		la, lb = lb, la
	}
	return (la + 0.05) / (lb + 0.05)
}

func luminance(hex string) (float64, bool) {
	r, g, b, ok := parseHex(hex)
	if !ok {
		return 0, false
	}
	ch := func(v int) float64 {
		c := float64(v) / 255
		if c <= 0.03928 {
			return c / 12.92
		}
		return math.Pow((c+0.055)/1.055, 2.4)
	}
	return 0.2126*ch(r) + 0.7152*ch(g) + 0.0722*ch(b), true
}

// Readable moves fg toward toward - usually the palette's foreground - until it
// reaches min contrast against bg, or as close as the pair allows.
//
// A colour picked for its hue - a person's colour from the terminal's bright
// ANSI range - has no contrast guarantee on the surface it lands on. On a dark
// palette it is fine; on a light one a pale cyan initial on a pale chip simply
// vanishes. Correcting it here keeps the hue as far as legibility allows.
func Readable(fg, bg, toward string, min float64) string {
	if Contrast(fg, bg) >= min {
		return fg
	}
	for t := 0.1; t <= 1.0001; t += 0.1 {
		c := Mix(fg, toward, t)
		if Contrast(c, bg) >= min {
			return c
		}
	}
	return toward
}
