package ui

import (
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

	// top and rows are the last drawn scroll position, kept so a click can be
	// turned back into an item.
	top  int
	rows int
}

// RowToIndex maps a screen row to an item, or -1 for the title row and for
// empty space below the list.
func (p *Picker) RowToIndex(screenY int) int {
	if !p.open || screenY < 1 || screenY > p.rows {
		return -1
	}
	i := p.top + screenY - 1
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
	p.onAccept = onAccept
	p.filter()
}

// Close hides it.
func (p *Picker) Close() {
	p.open = false
	p.query = ""
	p.all = nil
	p.view = nil
	p.onAccept = nil
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
func (p *Picker) Accept() error {
	it, ok := p.Selected()
	if !ok {
		p.Close()
		return nil
	}
	fn := p.onAccept
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
		line = render.Pad(render.Truncate(line, width), width)
		if idx == p.cur {
			b.WriteString(st.PickerSel.Render(line))
		} else {
			b.WriteString(st.Picker.Render(line))
		}
	}
	return b.String()
}

// SortItems orders picker items by label.
func SortItems(items []PickerItem) {
	sort.Slice(items, func(i, j int) bool { return items[i].Label < items[j].Label })
}
