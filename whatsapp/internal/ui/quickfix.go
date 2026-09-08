package ui

import (
	"fmt"
	"strings"
	"time"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/theme"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/ui/render"
)

// QFItem is one search result.
type QFItem struct {
	Chat      domain.JID
	ChatName  string
	MessageID string
	Text      string
	TS        time.Time
}

// Quickfix is the result list, filled by :grep and walked with the same
// bindings as the author's Neovim quickfix section.
type Quickfix struct {
	items []QFItem
	cur   int
	open  bool
	title string
}

// Set replaces the list and puts the cursor at the first item.
func (q *Quickfix) Set(title string, items []QFItem) {
	q.items = items
	q.cur = 0
	q.title = title
	q.open = len(items) > 0
}

// Len is how many results there are.
func (q *Quickfix) Len() int { return len(q.items) }

// Title describes what filled the list.
func (q *Quickfix) Title() string { return q.title }

// Current is the item under the cursor.
func (q *Quickfix) Current() (QFItem, bool) {
	if q.cur < 0 || q.cur >= len(q.items) {
		return QFItem{}, false
	}
	return q.items[q.cur], true
}

// Next and Prev walk the list, clamping at the ends so :cnext past the last
// result says nothing rather than wrapping into the first.
func (q *Quickfix) Next() (QFItem, bool) {
	if q.cur+1 >= len(q.items) {
		return QFItem{}, false
	}
	q.cur++
	return q.items[q.cur], true
}

func (q *Quickfix) Prev() (QFItem, bool) {
	if q.cur <= 0 {
		return QFItem{}, false
	}
	q.cur--
	return q.items[q.cur], true
}

// Select moves to an index.
func (q *Quickfix) Select(i int) (QFItem, bool) {
	if i < 0 || i >= len(q.items) {
		return QFItem{}, false
	}
	q.cur = i
	return q.items[i], true
}

// Index is the cursor's position.
func (q *Quickfix) Index() int { return q.cur }

// Open reports whether the window is showing.
func (q *Quickfix) Open() bool { return q.open && len(q.items) > 0 }

// Toggle opens or closes the window.
func (q *Quickfix) Toggle() { q.open = !q.open }

// SetOpen forces the window's state.
func (q *Quickfix) SetOpen(v bool) { q.open = v }

// Items lists the results, for the picker.
func (q *Quickfix) Items() []QFItem { return q.items }

// View renders the quickfix window.
func (q *Quickfix) View(st theme.Styles, width, height int) string {
	if height < 1 {
		return ""
	}
	var b strings.Builder
	header := fmt.Sprintf("%s  %d/%d", q.title, q.cur+1, len(q.items))
	b.WriteString(st.ListFilter.Render(render.Pad(render.Truncate(header, width), width)))

	rows := height - 1
	// Keep the cursor in view by scrolling the window around it.
	start := 0
	if q.cur >= rows {
		start = q.cur - rows + 1
	}
	for i := 0; i < rows; i++ {
		b.WriteString("\n")
		idx := start + i
		if idx >= len(q.items) {
			continue
		}
		it := q.items[idx]
		name := it.ChatName
		if name == "" {
			name = it.Chat.Display()
		}
		line := fmt.Sprintf("%s  %s  %s",
			it.TS.Format("02/01 15:04"), name, strings.ReplaceAll(it.Text, "\n", " "))
		line = render.Pad(render.Truncate(line, width), width)
		if idx == q.cur {
			b.WriteString(st.PickerSel.Render(line))
		} else {
			b.WriteString(st.Picker.Render(line))
		}
	}
	return b.String()
}
