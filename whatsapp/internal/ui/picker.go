package ui

import (
	"fmt"
	"github.com/charmbracelet/lipgloss"
	"sort"
	"strings"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// PickerItem is one row in the overlay.
type PickerItem struct {
	// Label is what is matched and shown.
	Label string
	// Detail is shown dimmed after the label.
	Detail string
	// Value is what the caller acts on; the label is for humans.
	Value string
}

// Picker is the fuzzy overlay behind <leader><leader>, :actions and the keymap
// listing. It is deliberately a subsequence match rather than a fuzzy score:
// the ranking of a scored matcher is hard to predict, and for a list of chats
// or actions "the characters appear in order" is enough.
type Picker struct {
	title string
	all   []PickerItem
	view  []PickerItem
	query string
	cur   int
	open  bool
	// onAccept is what to do with the chosen value.
	onAccept func(PickerItem) error
	// fetch re-asks the source whenever the query changes, for a picker over
	// something too big to hold in memory. The global finder searches a store
	// of a hundred thousand messages; filtering a preloaded list is not an
	// option, and neither is loading one.
	fetch func(query string) []PickerItem

	// top and rows are the last drawn scroll position, kept so a click can be
	// turned back into an item. headRows is how many rows sit above the list
	// itself - the title, and under the pill shape a blank row of air below
	// the search field - so a click is not off by however many of those there
	// are.
	top      int
	rows     int
	headRows int

	// accepted is what was marked when Accept ran, since Close clears the
	// marks before the callback sees them.
	accepted []PickerItem
	// marked are the multi-selected rows, by value. A picker over contacts is
	// the third place a selection is wanted - chats and messages being the
	// other two - and it works the same way there: <C-v> marks, the action
	// applies to all of them.
	marked map[string]bool
}

// RowToIndex maps a screen row to an item, or -1 for the title row and for
// empty space below the list.
func (p *Picker) RowToIndex(screenY int) int {
	head := maxInt(1, p.headRows)
	if !p.open || screenY < head || screenY > head+p.rows-1 {
		return -1
	}
	i := p.top + screenY - head
	if i < 0 || i >= len(p.view) {
		return -1
	}
	return i
}

// SelectRow moves the highlight to the item at a screen row.
func (p *Picker) SelectRow(screenY int) bool {
	i := p.RowToIndex(screenY)
	if i < 0 {
		return false
	}
	p.cur = i
	return true
}

// Scroll moves the highlight, for the wheel.
func (p *Picker) Scroll(delta int) { p.Move(delta) }

// Open shows the picker.
func (p *Picker) Open(title string, items []PickerItem, onAccept func(PickerItem) error) {
	p.title = title
	p.all = items
	p.query = ""
	p.cur = 0
	p.open = true
	p.fetch = nil
	p.onAccept = onAccept
	p.marked, p.accepted = nil, nil
	p.filter()
}

// OpenLive shows a picker whose rows come from the source on every keystroke.
func (p *Picker) OpenLive(title string, fetch func(query string) []PickerItem,
	onAccept func(PickerItem) error) {

	p.title = title
	p.query = ""
	p.cur = 0
	p.open = true
	p.fetch = fetch
	p.onAccept = onAccept
	p.marked, p.accepted = nil, nil
	p.filter()
}

// Close hides it.
func (p *Picker) Close() {
	p.open = false
	p.query = ""
	p.all = nil
	p.view = nil
	p.onAccept = nil
	p.fetch = nil
	p.marked = nil
}

// IsOpen reports whether the overlay is showing.
func (p *Picker) IsOpen() bool { return p.open }

// Query is the current filter text.
func (p *Picker) Query() string { return p.query }

// SetQuery narrows the list.
func (p *Picker) SetQuery(q string) {
	p.query = q
	p.cur = 0
	p.filter()
}

// Backspace removes the last character of the query.
func (p *Picker) Backspace() {
	if p.query == "" {
		return
	}
	r := []rune(p.query)
	p.SetQuery(string(r[:len(r)-1]))
}

// AppendRune adds to the query.
func (p *Picker) AppendRune(r rune) { p.SetQuery(p.query + string(r)) }

func (p *Picker) filter() {
	if p.fetch != nil {
		// The source already matched; matching again in here would drop rows
		// a database found by stem or by word order and this cannot.
		p.all = p.fetch(p.query)
		p.view = append(p.view[:0], p.all...)
		if p.cur >= len(p.view) {
			p.cur = maxInt(0, len(p.view)-1)
		}
		return
	}
	needle := strings.ToLower(p.query)
	p.view = p.view[:0]
	for _, it := range p.all {
		if needle == "" || subsequence(strings.ToLower(it.Label), needle) ||
			subsequence(strings.ToLower(it.Detail), needle) {
			p.view = append(p.view, it)
		}
	}
	if p.cur >= len(p.view) {
		p.cur = maxInt(0, len(p.view)-1)
	}
}

// subsequence reports whether every rune of needle appears in haystack in
// order, which is what makes "pc" match "picker.chats".
func subsequence(haystack, needle string) bool {
	if needle == "" {
		return true
	}
	n := []rune(needle)
	i := 0
	for _, r := range haystack {
		if r == n[i] {
			if i++; i == len(n) {
				return true
			}
		}
	}
	return false
}

// ToggleMark marks or unmarks the row under the cursor and moves on, so a run
// of them is one key each.
func (p *Picker) ToggleMark() {
	it, ok := p.Selected()
	if !ok {
		return
	}
	if p.marked == nil {
		p.marked = map[string]bool{}
	}
	if p.marked[it.Value] {
		delete(p.marked, it.Value)
	} else {
		p.marked[it.Value] = true
	}
	p.Move(1)
}

// Accepted is what was marked at the moment Accept ran.
func (p *Picker) Accepted() []PickerItem { return p.accepted }

// Marked is what has been marked, in the order the rows are listed.
func (p *Picker) Marked() []PickerItem {
	if len(p.marked) == 0 {
		return nil
	}
	out := make([]PickerItem, 0, len(p.marked))
	for _, it := range p.all {
		if p.marked[it.Value] {
			out = append(out, it)
		}
	}
	return out
}

// MarkCount is how many rows carry a mark.
func (p *Picker) MarkCount() int { return len(p.marked) }

// ClearMarks drops them.
func (p *Picker) ClearMarks() { p.marked = nil }

// Move shifts the cursor.
func (p *Picker) Move(delta int) {
	if len(p.view) == 0 {
		return
	}
	p.cur = clampInt(p.cur+delta, 0, len(p.view)-1)
}

// Len is how many rows match.
func (p *Picker) Len() int { return len(p.view) }

// Index is the cursor's position.
func (p *Picker) Index() int { return p.cur }

// Selected returns the row under the cursor.
func (p *Picker) Selected() (PickerItem, bool) {
	if p.cur < 0 || p.cur >= len(p.view) {
		return PickerItem{}, false
	}
	return p.view[p.cur], true
}

// Accept runs the callback for the selected row and closes the picker.
//
// The picker closes first, because a callback may open another one - the file
// browser walks into a directory that way. The marks are handed over rather
// than dropped with it, so a callback can still act on the whole selection.
func (p *Picker) Accept() error {
	it, ok := p.Selected()
	if !ok {
		p.Close()
		return nil
	}
	fn := p.onAccept
	p.accepted = p.Marked()
	p.Close()
	if fn == nil {
		return nil
	}
	return fn(it)
}

// View renders the overlay.
func (p *Picker) View(st theme.Styles, width, height int) string {
	if height < 2 {
		return ""
	}
	if st.Shape != theme.ShapeSquare {
		return p.pillView(st, width, height)
	}
	var b strings.Builder
	head := p.title + "  " + p.query + "▏"
	b.WriteString(st.ListFilter.Render(render.Pad(render.Truncate(head, width), width)))

	rows := height - 1
	start := 0
	if p.cur >= rows {
		start = p.cur - rows + 1
	}
	// Remembered so a click can be turned back into an item. The alternative
	// is recomputing the scroll position in the mouse handler, which is the
	// same arithmetic written twice and wrong once.
	p.top = start
	p.rows = rows
	p.headRows = 1
	for i := 0; i < rows; i++ {
		b.WriteString("\n")
		idx := start + i
		if idx >= len(p.view) {
			b.WriteString(st.Picker.Render(strings.Repeat(" ", width)))
			continue
		}
		it := p.view[idx]
		line := it.Label
		if it.Detail != "" {
			line += "  " + it.Detail
		}
		if p.marked[it.Value] {
			line = "✓ " + line
		} else if len(p.marked) > 0 {
			line = "  " + line
		}
		line = render.Pad(render.Truncate(line, width), width)
		if idx == p.cur {
			b.WriteString(st.PickerSel.Render(line))
		} else {
			b.WriteString(st.Picker.Render(line))
		}
	}
	return b.String()
}

// pillView draws the picker in the rice's shapes: the title as an accent chip,
// the query as a rounded field beside it, and the rows on the background with
// the chosen one on a rounded surface of its own. The rows keep their places -
// row zero is the title, one row per item under it - so a click still lands on
// the item it looks like it lands on.
func (p *Picker) pillView(st theme.Styles, width, height int) string {
	pal := st.Palette
	// Wide enough to read as a gutter rather than a rounding error: the
	// picker fills the whole terminal, and two columns of it disappeared
	// next to the wallpaper.
	const margin = 4
	w := maxInt(10, width-2*margin)
	m := strings.Repeat(" ", margin)

	title := st.Chip(p.title, pal.OnAccent, pal.Accent, true)
	fieldRoom := maxInt(4, w-render.VisibleWidth(title)-1-2)
	query := st.Icon("search") + " " + p.query + "▏"
	if p.query == "" {
		query = st.Icon("search") + " type to filter▏"
	}
	queryFg := pal.Fg
	if p.query == "" {
		queryFg = pal.Faint
	}
	field := st.Chip(render.Pad(render.Truncate(query, fieldRoom), fieldRoom), queryFg, pal.Raised, false)
	count := ""
	if n := len(p.view); n != len(p.all) || n > 0 {
		count = fmt.Sprintf(" %d", len(p.view))
	}
	head := m + title + " " + field
	if room := width - render.VisibleWidth(head) - len(count) - margin; room >= 0 {
		head += strings.Repeat(" ", room) + st.Timestamp.Render(count)
	}

	var b strings.Builder
	b.WriteString(head)
	// A blank row under the search field, or the list reads as a
	// continuation of it rather than what it is being filtered.
	b.WriteString("\n")

	rows := height - 2
	start := 0
	if p.cur >= rows {
		start = p.cur - rows + 1
	}
	p.top = start
	p.rows = rows
	p.headRows = 2
	inner := maxInt(4, w-2)
	for i := 0; i < rows; i++ {
		b.WriteString("\n")
		idx := start + i
		if idx >= len(p.view) {
			continue
		}
		it := p.view[idx]
		selected := idx == p.cur
		surface := pal.Bg
		if selected {
			surface = pal.SelectedFill(pal.Raised)
		}
		on := func(fg string, bold bool) lipgloss.Style {
			s := lipgloss.NewStyle().Foreground(lipgloss.Color(fg)).Bold(bold)
			if selected {
				s = s.Background(lipgloss.Color(surface))
			}
			return s
		}
		label := it.Label
		if p.marked[it.Value] {
			label = st.Icon("sent") + " " + label
		} else if len(p.marked) > 0 {
			label = "  " + label
		}
		detail := render.Truncate(render1line(it.Detail, 200), maxInt(0, inner/2))
		room := inner - render.VisibleWidth(detail) - 2
		line := on(pal.Fg, selected).Render(" "+render.Pad(render.Truncate(label, maxInt(1, room)), maxInt(1, room))) +
			on(pal.Faint, false).Render(detail+" ")
		line = render.Pad(line, inner)
		if !selected {
			b.WriteString(m + " " + line)
			continue
		}
		b.WriteString(m + strings.Join(st.Card([]string{line}, surface), ""))
	}
	return b.String()
}

// SortItems orders picker items by label.
func SortItems(items []PickerItem) {
	sort.Slice(items, func(i, j int) bool { return items[i].Label < items[j].Label })
}
