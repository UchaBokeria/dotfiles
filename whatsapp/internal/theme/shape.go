package theme

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Shape is the edge language every chip, badge, field and bubble shares.
//
// The rice speaks one: tmux's status bar and waybar both round their segments
// into capsules with the Nerd Font half circles U+E0B6 and U+E0B4. A terminal
// client that draws square blocks beside them looks like a different machine.
// Apple's word for this is concentricity - rounded shapes near other rounded
// shapes should feel related - and a grid of cells can honour it only by using
// the same two glyphs everywhere.
type Shape int

const (
	// ShapePill ends every surface with a half circle. Needs a Nerd Font, or
	// kitty's built-in powerline glyphs.
	ShapePill Shape = iota
	// ShapeRounded uses the box-drawing arcs, which every monospace font has.
	ShapeRounded
	// ShapeSquare draws plain blocks, for fonts with neither.
	ShapeSquare
)

// ParseShape reads the configured name.
func ParseShape(name string) (Shape, error) {
	switch strings.ToLower(strings.TrimSpace(name)) {
	case "", "pill":
		return ShapePill, nil
	case "rounded", "round":
		return ShapeRounded, nil
	case "square", "flat":
		return ShapeSquare, nil
	}
	return ShapePill, fmt.Errorf("%q is not a shape (pill, rounded, square)", name)
}

func (s Shape) String() string {
	switch s {
	case ShapeRounded:
		return "rounded"
	case ShapeSquare:
		return "square"
	}
	return "pill"
}

// Caps are the glyphs that close a surface on the left and on the right.
//
// They are drawn in the surface's fill colour on the background behind it,
// which is what turns a strip of coloured cells into a capsule.
func (s Shape) Caps() (left, right string) {
	switch s {
	case ShapePill:
		return "", ""
	case ShapeRounded:
		// The half blocks read as a softened edge in any font; the arcs
		// themselves cannot be filled.
		return "▐", "▌"
	}
	return " ", " "
}

// Pill draws text on a fill with the shape's own ends.
//
// behind is the colour the pill sits on - the background, or a surface - so
// the caps can blend into it. Empty means the terminal's own background, which
// is what glass needs: nothing painted where the compositor should show.
func Pill(s Shape, text string, fg, fill, behind lipgloss.TerminalColor, bold bool) string {
	body := lipgloss.NewStyle().Foreground(fg).Background(fill).Bold(bold)
	edge := lipgloss.NewStyle().Foreground(fill)
	if behind != nil {
		edge = edge.Background(behind)
	}
	l, r := s.Caps()
	if s == ShapeSquare {
		return body.Render(" " + text + " ")
	}
	return edge.Render(l) + body.Render(text) + edge.Render(r)
}

// PillWidth is how many cells a pill around text of this width takes.
func PillWidth(textWidth int) int { return textWidth + 2 }
