package theme

import (
	"fmt"
	"hash/fnv"
	"sync/atomic"

	"github.com/charmbracelet/lipgloss"
)

// generation counts palettes handed out, so the render cache can tell a
// re-themed style set from the one it cached against.
var generation atomic.Int64

// Styles are the named styles the interface draws with. No other package
// constructs a lipgloss style from a literal colour.
type Styles struct {
	Palette Palette

	App     lipgloss.Style
	Divider lipgloss.Style

	// Chat list
	ListTitle  lipgloss.Style
	ListRow    lipgloss.Style
	ListRowSel lipgloss.Style
	ListName   lipgloss.Style
	ListSnip   lipgloss.Style
	ListTime   lipgloss.Style
	ListBadge  lipgloss.Style
	ListPin    lipgloss.Style
	ListMute   lipgloss.Style
	ListFilter lipgloss.Style

	// Messages
	BubbleMine   lipgloss.Style
	BubbleTheirs lipgloss.Style
	BubbleSel    lipgloss.Style
	Sender       lipgloss.Style
	Timestamp    lipgloss.Style
	Quote        lipgloss.Style
	DaySep       lipgloss.Style
	MediaChip    lipgloss.Style
	Reaction     lipgloss.Style
	Link         lipgloss.Style
	Placeholder  lipgloss.Style

	// Delivery ticks
	TickPending   lipgloss.Style
	TickSent      lipgloss.Style
	TickDelivered lipgloss.Style
	TickRead      lipgloss.Style
	TickFailed    lipgloss.Style

	// Chrome
	Gutter      lipgloss.Style
	GutterCur   lipgloss.Style
	Status      lipgloss.Style
	StatusKey   lipgloss.Style
	StatusFocus lipgloss.Style
	// FocusEdge marks the pane that has the keyboard.
	FocusEdge  lipgloss.Style
	StatusWarn lipgloss.Style
	StatusErr  lipgloss.Style
	CmdLine    lipgloss.Style
	Search     lipgloss.Style
	Match      lipgloss.Style
	MatchCur   lipgloss.Style
	Composer   lipgloss.Style
	Cursor     lipgloss.Style
	Picker     lipgloss.Style
	PickerSel  lipgloss.Style
	Lock       lipgloss.Style

	Border lipgloss.Border
	// Solid bubbles are filled blocks with half-block edges rather than a box
	// drawn in line characters. The renderer draws their top and bottom rows
	// in the bubble's colour on the terminal's background, which is what gives
	// them soft corners instead of a frame.
	Solid bool
	// SenderColors tell apart the people in a group. One colour for every
	// name makes a busy group read as one long monologue.
	SenderColors []lipgloss.Style
	Generation   int64
}

// SenderStyle picks the colour for a person in a group, the same one every
// time: it is chosen from the name, so it survives restarts and scrolling.
func (s Styles) SenderStyle(name string) lipgloss.Style {
	if len(s.SenderColors) == 0 || name == "" {
		return s.Sender
	}
	h := fnv.New32a()
	_, _ = h.Write([]byte(name))
	return s.SenderColors[int(h.Sum32()%uint32(len(s.SenderColors)))]
}

// Border resolves a configured border name.
func Border(name string) (lipgloss.Border, error) {
	switch name {
	case "rounded":
		return lipgloss.RoundedBorder(), nil
	case "thick":
		return lipgloss.ThickBorder(), nil
	case "double":
		return lipgloss.DoubleBorder(), nil
	case "ascii":
		return lipgloss.Border{
			Top: "-", Bottom: "-", Left: "|", Right: "|",
			TopLeft: "+", TopRight: "+", BottomLeft: "+", BottomRight: "+",
		}, nil
	case "solid":
		// Quadrants at the corners and half blocks along the edges. Drawn in
		// the bubble's own colour, they round the block off by half a cell,
		// which is as close to a curve as a terminal grid gets.
		return lipgloss.Border{
			Top: "▄", Bottom: "▀", Left: " ", Right: " ",
			TopLeft: "▗", TopRight: "▖", BottomLeft: "▝", BottomRight: "▘",
		}, nil
	case "none", "":
		return lipgloss.HiddenBorder(), nil
	default:
		return lipgloss.Border{}, fmt.Errorf(
			"%q is not a border (solid, rounded, thick, double, ascii, none)", name)
	}
}

// New builds the style set. An unknown border name falls back to rounded; the
// caller validates the name and reports it, so this never has to fail.
func New(p Palette, border string) Styles {
	b, err := Border(border)
	if err != nil {
		b = lipgloss.RoundedBorder()
	}
	// lipgloss.Color is a type, so wrap the conversion to keep the table below
	// readable.
	c := func(hex string) lipgloss.Color { return lipgloss.Color(hex) }

	s := Styles{
		Palette:    p,
		Border:     b,
		Solid:      border == "solid",
		Generation: generation.Add(1),
	}

	s.App = lipgloss.NewStyle().Foreground(c(p.Fg))
	s.Divider = lipgloss.NewStyle().Foreground(c(p.Edge))

	s.ListTitle = lipgloss.NewStyle().Foreground(c(p.Accent)).Bold(true)
	s.ListRow = lipgloss.NewStyle().Foreground(c(p.Fg))
	s.ListRowSel = lipgloss.NewStyle().Foreground(c(p.Fg)).Background(c(p.Selection)).Bold(true)
	s.ListName = lipgloss.NewStyle().Foreground(c(p.Fg))
	s.ListSnip = lipgloss.NewStyle().Foreground(c(p.Muted))
	s.ListTime = lipgloss.NewStyle().Foreground(c(p.Faint))
	s.ListBadge = lipgloss.NewStyle().Foreground(c(p.OnAccent)).Background(c(p.Accent)).Bold(true)
	s.ListPin = lipgloss.NewStyle().Foreground(c(p.Accent))
	s.ListMute = lipgloss.NewStyle().Foreground(c(p.Faint))
	s.ListFilter = lipgloss.NewStyle().Foreground(c(p.Accent))

	s.BubbleMine = lipgloss.NewStyle().Foreground(c(p.Fg)).Background(c(p.BubbleMine))
	s.BubbleTheirs = lipgloss.NewStyle().Foreground(c(p.Fg)).Background(c(p.BubbleTheirs))
	s.BubbleSel = lipgloss.NewStyle().Foreground(c(p.Accent))
	s.Sender = lipgloss.NewStyle().Foreground(c(p.Accent)).Bold(true)
	// The bright half of the terminal palette, which the theme generator
	// already tunes for legibility on this background. Red is left out: in a
	// chat client it reads as an error, not as a person.
	s.SenderColors = []lipgloss.Style{s.Sender}
	for _, i := range []int{10, 11, 12, 13, 14} {
		if hex := p.ANSI[i]; hex != "" {
			s.SenderColors = append(s.SenderColors,
				lipgloss.NewStyle().Foreground(c(hex)).Bold(true))
		}
	}
	s.Timestamp = lipgloss.NewStyle().Foreground(c(p.Faint))
	s.Quote = lipgloss.NewStyle().Foreground(c(p.Muted))
	s.DaySep = lipgloss.NewStyle().Foreground(c(p.Faint))
	s.MediaChip = lipgloss.NewStyle().Foreground(c(p.Link))
	s.Reaction = lipgloss.NewStyle().Foreground(c(p.Accent))
	// Colour only. The underline is added by the renderer as a plain escape,
	// because lipgloss renders an underlined string one rune at a time - see
	// render.underlineOn.
	s.Link = lipgloss.NewStyle().Foreground(c(p.Link))
	s.Placeholder = lipgloss.NewStyle().Foreground(c(p.Faint)).Italic(true)

	s.TickPending = lipgloss.NewStyle().Foreground(c(p.Faint))
	s.TickSent = lipgloss.NewStyle().Foreground(c(p.Muted))
	s.TickDelivered = lipgloss.NewStyle().Foreground(c(p.Muted))
	s.TickRead = lipgloss.NewStyle().Foreground(c(p.Accent))
	s.TickFailed = lipgloss.NewStyle().Foreground(c(p.Bad)).Bold(true)

	s.Gutter = lipgloss.NewStyle().Foreground(c(p.Faint))
	s.GutterCur = lipgloss.NewStyle().Foreground(c(p.Accent)).Bold(true)
	s.Status = lipgloss.NewStyle().Foreground(c(p.Muted)).Background(c(p.Raised))
	s.StatusFocus = lipgloss.NewStyle().Foreground(c(p.Bg)).Background(c(p.Accent)).Bold(true)
	s.FocusEdge = lipgloss.NewStyle().Foreground(c(p.Accent)).Bold(true)
	s.StatusKey = lipgloss.NewStyle().Foreground(c(p.OnAccent)).Background(c(p.Accent)).Bold(true)
	s.StatusWarn = lipgloss.NewStyle().Foreground(c(p.Warn)).Background(c(p.Raised))
	s.StatusErr = lipgloss.NewStyle().Foreground(c(p.Bad)).Background(c(p.Raised)).Bold(true)
	s.CmdLine = lipgloss.NewStyle().Foreground(c(p.Fg))
	s.Search = lipgloss.NewStyle().Foreground(c(p.Fg))
	s.Match = lipgloss.NewStyle().Foreground(c(p.Bg)).Background(c(p.Warn))
	s.MatchCur = lipgloss.NewStyle().Foreground(c(p.Bg)).Background(c(p.Accent)).Bold(true)
	s.Composer = lipgloss.NewStyle().Foreground(c(p.Fg))
	s.Cursor = lipgloss.NewStyle().Foreground(c(p.Bg)).Background(c(p.Cursor))
	s.Picker = lipgloss.NewStyle().Foreground(c(p.Fg)).Background(c(p.Raised))
	s.PickerSel = lipgloss.NewStyle().Foreground(c(p.Fg)).Background(c(p.Selection)).Bold(true)
	s.Lock = lipgloss.NewStyle().Foreground(c(p.Accent)).Bold(true)

	return s
}
