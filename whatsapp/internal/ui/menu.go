package ui

import (
	"strings"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// MenuItem is one row of a context menu.
//
// A separator has an empty Label and no Run. Nothing here is ever a decorative
// entry: an item that cannot work is not added to the menu at all, because a
// greyed-out row that never becomes available is just a lie about what the
// program can do.
type MenuItem struct {
	Label string
	// Key is the equivalent keyboard shortcut, shown on the right.
	Key string
	// Danger marks a destructive item, drawn in the error colour.
	Danger bool
	Run    func() error
	// Separator draws a rule instead of a row.
	Separator bool
}

// Menu is the right-click popup.
type Menu struct {
	title string
	items []MenuItem
	cur   int
	open  bool
	// x and y are the top-left corner, already clamped onto the screen.
	x, y int
	w, h int
}

// Open shows a menu anchored at a screen position.
func (m *Menu) Open(title string, items []MenuItem, atX, atY, screenW, screenH int) {
	m.title = title
	m.items = items
	m.open = len(items) > 0
	m.cur = m.firstSelectable()

	m.w = render.VisibleWidth(title) + 4
	for _, it := range items {
		if w := render.VisibleWidth(it.Label) + render.VisibleWidth(it.Key) + 6; w > m.w {
			m.w = w
		}
	}
	if m.w > screenW-2 {
		m.w = maxInt(10, screenW-2)
	}
	m.h = len(items) + 2 // a title row and a bottom border

	// Flip rather than overflow: a menu opened near the right or bottom edge
	// otherwise renders half off the screen.
	m.x = atX
	if m.x+m.w > screenW {
		m.x = maxInt(0, screenW-m.w)
	}
	m.y = atY
	if m.y+m.h > screenH {
		m.y = maxInt(0, atY-m.h)
	}
	if m.y < 0 {
		m.y = 0
	}
}

// Close hides the menu.
func (m *Menu) Close() { m.open = false; m.items = nil }

// IsOpen reports whether it is showing.
func (m *Menu) IsOpen() bool { return m.open }

// Len is the number of rows, separators included.
func (m *Menu) Len() int { return len(m.items) }

// Index is the highlighted row.
func (m *Menu) Index() int { return m.cur }

// Bounds is the rectangle the menu occupies, for hit testing.
func (m *Menu) Bounds() (x, y, w, h int) { return m.x, m.y, m.w, m.h }

// Items lists the rows, for tests.
func (m *Menu) Items() []MenuItem { return m.items }

func (m *Menu) firstSelectable() int {
	for i, it := range m.items {
		if !it.Separator {
			return i
		}
	}
	return 0
}

// Move steps to the next selectable row, skipping separators.
func (m *Menu) Move(delta int) {
	if len(m.items) == 0 {
		return
	}
	i := m.cur
	for n := 0; n < len(m.items); n++ {
		i += delta
		if i < 0 {
			i = len(m.items) - 1
		}
		if i >= len(m.items) {
			i = 0
		}
		if !m.items[i].Separator {
			m.cur = i
			return
		}
	}
}

// SelectRow highlights the row at a screen y, for mouse motion.
func (m *Menu) SelectRow(screenY int) bool {
	i := screenY - m.y - 1 // the title occupies the first row
	if i < 0 || i >= len(m.items) || m.items[i].Separator {
		return false
	}
	m.cur = i
	return true
}

// Activate runs the highlighted item and closes the menu.
func (m *Menu) Activate() error {
	if m.cur < 0 || m.cur >= len(m.items) {
		m.Close()
		return nil
	}
	it := m.items[m.cur]
	m.Close()
	if it.Run == nil {
		return nil
	}
	return it.Run()
}

// HandleKey consumes a keystroke while the menu is up. It reports whether the
// menu is still open, and any error the activated item returned.
func (m *Menu) HandleKey(k keys.Key) (open bool, err error) {
	switch {
	case k.Special == keys.Esc, k.Mods == 0 && k.Rune == 'q',
		k.Mods&keys.Ctrl != 0 && k.Rune == 'c':
		m.Close()
		return false, nil

	case k.Special == keys.CR, k.Mods == 0 && k.Rune == 'l':
		return false, m.Activate()

	case k.Mods == 0 && k.Rune == 'j', k.Special == keys.Down,
		k.Mods&keys.Ctrl != 0 && k.Rune == 'n':
		m.Move(1)
	case k.Mods == 0 && k.Rune == 'k', k.Special == keys.Up,
		k.Mods&keys.Ctrl != 0 && k.Rune == 'p':
		m.Move(-1)
	}
	return true, nil
}

// Overlay draws the menu onto an already-rendered frame, replacing the cells
// it covers. Compositing this way keeps the menu independent of how the panes
// beneath it were laid out.
func (m *Menu) Overlay(frame []string, st theme.Styles) []string {
	if !m.open {
		return frame
	}
	box := strings.Split(m.render(st), "\n")

	out := make([]string, len(frame))
	copy(out, frame)
	for i, line := range box {
		row := m.y + i
		if row < 0 || row >= len(out) {
			continue
		}
		out[row] = spliceAt(out[row], m.x, line)
	}
	return out
}

func (m *Menu) render(st theme.Styles) string {
	inner := m.w - 2
	var b strings.Builder

	b.WriteString(st.PickerSel.Render("┌" + render.Pad(render.Truncate(" "+m.title, inner), inner) + "┐"))

	for i, it := range m.items {
		b.WriteString("\n")
		if it.Separator {
			b.WriteString(st.Picker.Render("├" + strings.Repeat("─", inner) + "┤"))
			continue
		}
		label := " " + it.Label
		gap := inner - render.VisibleWidth(label) - render.VisibleWidth(it.Key) - 1
		if gap < 1 {
			gap = 1
		}
		row := label + strings.Repeat(" ", gap) + it.Key + " "
		row = render.Pad(render.Truncate(row, inner), inner)

		style := st.Picker
		switch {
		case i == m.cur && it.Danger:
			style = st.StatusErr
		case i == m.cur:
			style = st.PickerSel
		case it.Danger:
			style = st.StatusWarn
		}
		b.WriteString(st.Picker.Render("│") + style.Render(row) + st.Picker.Render("│"))
	}

	b.WriteString("\n")
	b.WriteString(st.Picker.Render("└" + strings.Repeat("─", inner) + "┘"))
	return b.String()
}

// spliceAt replaces the cells of line starting at column x with patch.
//
// It works on display columns rather than bytes, so a menu drawn over Georgian
// or CJK text lands where it looks like it should.
func spliceAt(line string, x int, patch string) string {
	left := takeCols(line, x)
	if pad := x - render.VisibleWidth(left); pad > 0 {
		left += strings.Repeat(" ", pad)
	}
	rest := dropCols(line, x+render.VisibleWidth(patch))
	return left + patch + rest
}

// takeCols returns the prefix of s occupying at most n display columns,
// carrying any escape sequences it passes over so colour is not lost.
func takeCols(s string, n int) string { return render.TakeColumns(s, n) }

// dropCols returns the suffix of s beyond n display columns.
func dropCols(s string, n int) string { return render.DropColumns(s, n) }
