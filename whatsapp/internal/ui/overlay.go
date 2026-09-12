package ui

import (
	"fmt"
	"strings"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// Overlay is a scrollable full-screen page: the key list and the log.
//
// It handles its own keys rather than going through the modal engine. An
// overlay that routes through the engine inherits every binding underneath it,
// which is how the first version of the help page ended up impossible to
// close: Esc was bound to clearing the search, and nothing closed the page.
type Overlay struct {
	title  string
	lines  []string
	offset int
	open   bool
}

// Open shows the overlay.
func (o *Overlay) Open(title string, lines []string) {
	o.title = title
	o.lines = lines
	o.offset = 0
	o.open = true
}

// Close hides it.
func (o *Overlay) Close() { o.open = false }

// IsOpen reports whether it is showing.
func (o *Overlay) IsOpen() bool { return o.open }

// Title is the heading.
func (o *Overlay) Title() string { return o.title }

// Lines is the content, for tests.
func (o *Overlay) Lines() []string { return o.lines }

// Offset is the first visible line, for tests.
func (o *Overlay) Offset() int { return o.offset }

// HandleKey consumes a keystroke. It reports whether the overlay is still
// open afterwards.
//
// Every plausible "get me out of here" key closes it: q, Esc, Ctrl-C, Enter.
// Being unable to leave a help page is worse than closing one by accident.
func (o *Overlay) HandleKey(k keys.Key, height int) bool {
	page := maxInt(1, height-2)

	switch {
	case k.Special == keys.Esc,
		k.Special == keys.CR,
		k.Mods == 0 && (k.Rune == 'q' || k.Rune == 'Q'),
		k.Mods&keys.Ctrl != 0 && (k.Rune == 'c' || k.Rune == '['):
		o.open = false
		return false

	case k.Mods == 0 && k.Rune == 'j', k.Special == keys.Down:
		o.scroll(1, height)
	case k.Mods == 0 && k.Rune == 'k', k.Special == keys.Up:
		o.scroll(-1, height)
	case k.Mods&keys.Ctrl != 0 && k.Rune == 'd':
		o.scroll(page/2, height)
	case k.Mods&keys.Ctrl != 0 && k.Rune == 'u':
		o.scroll(-page/2, height)
	case k.Mods&keys.Ctrl != 0 && k.Rune == 'f', k.Special == keys.PgDn:
		o.scroll(page, height)
	case k.Mods&keys.Ctrl != 0 && k.Rune == 'b', k.Special == keys.PgUp:
		o.scroll(-page, height)
	case k.Mods == 0 && k.Rune == 'G', k.Special == keys.End:
		o.offset = maxInt(0, len(o.lines)-page)
	case k.Mods == 0 && k.Rune == 'g', k.Special == keys.Home:
		o.offset = 0
	}
	return true
}

// Scroll moves the view, for the mouse wheel.
func (o *Overlay) Scroll(delta, height int) { o.scroll(delta, height) }

func (o *Overlay) scroll(delta, height int) {
	page := maxInt(1, height-2)
	o.offset = clampInt(o.offset+delta, 0, maxInt(0, len(o.lines)-page))
}

// View renders the page with a header and a footer saying how to leave, which
// is the part the first version was missing.
func (o *Overlay) View(st theme.Styles, width, height int) string {
	if height < 3 {
		return ""
	}
	body := height - 2

	var b strings.Builder
	head := fmt.Sprintf("%s  (%d lines)", o.title, len(o.lines))
	b.WriteString(st.ListFilter.Render(render.Pad(render.Truncate(head, width), width)))

	for i := 0; i < body; i++ {
		b.WriteString("\n")
		idx := o.offset + i
		if idx >= len(o.lines) {
			continue
		}
		b.WriteString(render.Truncate(o.lines[idx], width))
	}

	pos := "all"
	if len(o.lines) > body {
		switch {
		case o.offset == 0:
			pos = "top"
		case o.offset >= len(o.lines)-body:
			pos = "bot"
		default:
			pos = fmt.Sprintf("%d%%", o.offset*100/maxInt(1, len(o.lines)-body))
		}
	}
	foot := fmt.Sprintf(" j/k scroll   C-d/C-u page   g/G ends   q or Esc to close%s%s",
		strings.Repeat(" ", maxInt(1, width-58-len(pos))), pos)
	b.WriteString("\n")
	b.WriteString(st.Status.Render(render.Pad(render.Truncate(foot, width), width)))
	return b.String()
}
