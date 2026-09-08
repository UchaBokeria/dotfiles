package ui

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/store"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/theme"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/ui/render"
)

// Filters, in the order the cycle visits them.
var chatFilters = []string{"all", "unread", "pinned", "groups", "dms", "muted", "archived"}

func knownFilter(name string) bool {
	for _, f := range chatFilters {
		if f == name {
			return true
		}
	}
	return false
}

// ChatList is the left pane.
//
// It keeps every loaded chat and a filtered view over it, and tracks the
// selection by JID rather than by index: an incoming message reorders the list
// under the cursor, and an index would silently select a different
// conversation.
type ChatList struct {
	r      store.Reader
	styles theme.Styles

	width  int
	height int

	all  []domain.Chat
	view []domain.Chat

	filter string
	search string

	selected domain.JID
	sel      int
	offset   int

	scrolloff int
	now       func() time.Time
}

// NewChatList returns an empty list.
func NewChatList(r store.Reader, st theme.Styles, width, height int) *ChatList {
	return &ChatList{
		r:         r,
		styles:    st,
		width:     width,
		height:    height,
		filter:    "all",
		scrolloff: 3,
		now:       time.Now,
	}
}

// SetScrolloff sets how many rows of context to keep around the cursor.
func (c *ChatList) SetScrolloff(n int) { c.scrolloff = n }

// Load reads the chats from the store.
func (c *ChatList) Load(ctx context.Context) error {
	chats, err := c.r.Chats(ctx, store.ChatFilter{
		Limit:           500,
		IncludeArchived: true,
	})
	if err != nil {
		return err
	}
	c.all = chats
	c.rebuild()
	return nil
}

// Invalidate reloads one chat, for a live event naming it. The whole list is
// reloaded when the chat is unknown, because a new conversation has to appear
// from somewhere.
func (c *ChatList) Invalidate(ctx context.Context, jid domain.JID) error {
	if jid.IsZero() {
		return c.Load(ctx)
	}
	updated, err := c.r.Chat(ctx, jid)
	if err != nil {
		return c.Load(ctx)
	}
	for i, ch := range c.all {
		if ch.JID == jid {
			c.all[i] = updated
			c.sortAll()
			c.rebuild()
			return nil
		}
	}
	c.all = append(c.all, updated)
	c.sortAll()
	c.rebuild()
	return nil
}

// sortAll restores the pinned-first, most-recent-next order the store uses, so
// an updated chat moves to where it belongs.
func (c *ChatList) sortAll() {
	sort.SliceStable(c.all, func(i, j int) bool {
		a, b := c.all[i], c.all[j]
		if a.Pinned != b.Pinned {
			return a.Pinned
		}
		if !a.LastMessageTS.Equal(b.LastMessageTS) {
			return a.LastMessageTS.After(b.LastMessageTS)
		}
		return a.JID.String() < b.JID.String()
	})
}

// SetFilter narrows the list. An unknown name is an error rather than a silent
// no-op, so a typo at the : prompt says so.
func (c *ChatList) SetFilter(name string) error {
	if !knownFilter(name) {
		return fmt.Errorf("%q is not a filter (%s)", name, strings.Join(chatFilters, ", "))
	}
	c.filter = name
	c.rebuild()
	return nil
}

// Filter is the active filter.
func (c *ChatList) Filter() string { return c.filter }

// CycleFilter moves to the next filter.
func (c *ChatList) CycleFilter() {
	for i, f := range chatFilters {
		if f == c.filter {
			c.filter = chatFilters[(i+1)%len(chatFilters)]
			c.rebuild()
			return
		}
	}
	c.filter = chatFilters[0]
	c.rebuild()
}

// SetSearch narrows by name as the user types.
func (c *ChatList) SetSearch(q string) {
	c.search = q
	c.rebuild()
}

// Search is the active query.
func (c *ChatList) Search() string { return c.search }

// rebuild recomputes the visible slice and re-finds the selection.
func (c *ChatList) rebuild() {
	needle := strings.ToLower(strings.TrimSpace(c.search))
	now := c.now()

	c.view = c.view[:0]
	for _, ch := range c.all {
		if !c.matchesFilter(ch, now) {
			continue
		}
		if needle != "" && !matchesSearch(ch, needle) {
			continue
		}
		c.view = append(c.view, ch)
	}
	c.restoreSelection()
}

func (c *ChatList) matchesFilter(ch domain.Chat, now time.Time) bool {
	switch c.filter {
	case "unread":
		return ch.Unread || ch.UnreadCount > 0
	case "pinned":
		return ch.Pinned
	case "archived":
		return ch.Archived
	case "muted":
		return ch.Muted(now)
	case "groups":
		return ch.Kind == domain.KindGroup && !ch.Archived
	case "dms":
		return ch.Kind == domain.KindDM && !ch.Archived
	default:
		// Archived chats are hidden from the default view, as on the phone.
		return !ch.Archived
	}
}

func matchesSearch(ch domain.Chat, needle string) bool {
	if strings.Contains(strings.ToLower(ch.DisplayName()), needle) {
		return true
	}
	if strings.Contains(strings.ToLower(ch.JID.User), needle) {
		return true
	}
	return strings.Contains(strings.ToLower(ch.LastSnippet), needle)
}

// restoreSelection keeps the cursor on the same conversation across a refilter,
// falling back to the nearest row when it has been filtered away.
func (c *ChatList) restoreSelection() {
	if len(c.view) == 0 {
		c.sel = 0
		c.offset = 0
		return
	}
	if !c.selected.IsZero() {
		for i, ch := range c.view {
			if ch.JID == c.selected {
				c.sel = i
				c.clampOffset()
				return
			}
		}
	}
	if c.sel >= len(c.view) {
		c.sel = len(c.view) - 1
	}
	if c.sel < 0 {
		c.sel = 0
	}
	c.selected = c.view[c.sel].JID
	c.clampOffset()
}

// Rows is the visible slice.
func (c *ChatList) Rows() []domain.Chat { return c.view }

// Len is how many chats are on screen.
func (c *ChatList) Len() int { return len(c.view) }

// Index is the cursor's position in the filtered list.
func (c *ChatList) Index() int { return c.sel }

// Selected returns the chat under the cursor.
func (c *ChatList) Selected() (domain.Chat, bool) {
	if c.sel < 0 || c.sel >= len(c.view) {
		return domain.Chat{}, false
	}
	return c.view[c.sel], true
}

// Select moves the cursor to a chat by JID, if it is visible.
func (c *ChatList) Select(jid domain.JID) bool {
	for i, ch := range c.view {
		if ch.JID == jid {
			c.sel = i
			c.selected = jid
			c.clampOffset()
			return true
		}
	}
	return false
}

// Move shifts the cursor, clamping at both ends rather than wrapping: wrapping
// past the end of a long list is disorienting.
func (c *ChatList) Move(delta int) {
	c.MoveTo(c.sel + delta)
}

// MoveTo places the cursor at an index.
func (c *ChatList) MoveTo(i int) {
	if len(c.view) == 0 {
		return
	}
	c.sel = clampInt(i, 0, len(c.view)-1)
	c.selected = c.view[c.sel].JID
	c.clampOffset()
}

// Top and Bottom are gg and G.
func (c *ChatList) Top()    { c.MoveTo(0) }
func (c *ChatList) Bottom() { c.MoveTo(len(c.view) - 1) }

// HalfPage is ctrl-d and ctrl-u.
func (c *ChatList) HalfPage(dir int) { c.Move(dir * maxInt(1, c.rows()/2)) }

// Page is ctrl-f and ctrl-b.
func (c *ChatList) Page(dir int) { c.Move(dir * maxInt(1, c.rows())) }

// Resize sets the pane's dimensions.
func (c *ChatList) Resize(width, height int) {
	c.width, c.height = width, height
	c.clampOffset()
}

// rows is how many chats fit, leaving a row for the header.
func (c *ChatList) rows() int { return maxInt(1, c.height-1) }

// clampOffset scrolls the window so the cursor stays visible with scrolloff
// rows of context where the list is long enough to allow it.
func (c *ChatList) clampOffset() {
	rows := c.rows()
	if len(c.view) <= rows {
		c.offset = 0
		return
	}
	pad := c.scrolloff
	if pad > (rows-1)/2 {
		pad = (rows - 1) / 2
	}
	if c.sel-pad < c.offset {
		c.offset = c.sel - pad
	}
	if c.sel+pad >= c.offset+rows {
		c.offset = c.sel + pad - rows + 1
	}
	c.offset = clampInt(c.offset, 0, len(c.view)-rows)
}

// View renders the pane.
func (c *ChatList) View() string {
	var b strings.Builder
	b.WriteString(c.header())

	rows := c.rows()
	for i := 0; i < rows; i++ {
		b.WriteString("\n")
		idx := c.offset + i
		if idx >= len(c.view) {
			continue
		}
		b.WriteString(c.row(c.view[idx], idx == c.sel))
	}
	return b.String()
}

// header shows the filter and, while searching, the query.
func (c *ChatList) header() string {
	label := c.filter
	if c.search != "" {
		label = "/" + c.search
	}
	count := fmt.Sprintf("%d", len(c.view))
	gap := c.width - render.VisibleWidth(label) - render.VisibleWidth(count) - 1
	if gap < 1 {
		return c.styles.ListFilter.Render(render.Truncate(label, c.width))
	}
	return c.styles.ListFilter.Render(label) +
		strings.Repeat(" ", gap) +
		c.styles.ListTime.Render(count) + " "
}

// row renders one chat: markers, name, unread badge, and a snippet.
func (c *ChatList) row(ch domain.Chat, selected bool) string {
	marks := ""
	if ch.Pinned {
		marks += "▪"
	}
	if ch.Muted(c.now()) {
		marks += "○"
	}
	if marks == "" {
		marks = " "
	}
	marks = render.Pad(marks, 2)

	badge := ""
	if ch.UnreadCount > 0 {
		badge = fmt.Sprintf(" %d", ch.UnreadCount)
	} else if ch.Unread {
		badge = " •"
	}

	stamp := ""
	if !ch.LastMessageTS.IsZero() {
		stamp = relativeStamp(ch.LastMessageTS, c.now())
	}

	// Name line: marks, name, then the timestamp pushed right.
	nameWidth := c.width - render.VisibleWidth(marks) -
		render.VisibleWidth(badge) - render.VisibleWidth(stamp) - 1
	if nameWidth < 1 {
		nameWidth = 1
	}
	name := render.Pad(render.Truncate(ch.DisplayName(), nameWidth), nameWidth)

	line := marks + name + badge + " " + stamp
	line = render.Pad(render.Truncate(line, c.width), c.width)

	if selected {
		return c.styles.ListRowSel.Render(line)
	}
	if ch.Unread || ch.UnreadCount > 0 {
		return c.styles.ListName.Render(line)
	}
	return c.styles.ListRow.Render(line)
}

// relativeStamp is the compact time a chat list shows: a clock today, a
// weekday this week, a date beyond that.
func relativeStamp(t, now time.Time) string {
	y, m, d := now.Date()
	today := time.Date(y, m, d, 0, 0, 0, 0, now.Location())
	switch {
	case !t.Before(today):
		return t.Format("15:04")
	case !t.Before(today.AddDate(0, 0, -6)):
		return t.Format("Mon")
	default:
		return t.Format("02/01")
	}
}

func clampInt(v, lo, hi int) int {
	if hi < lo {
		return lo
	}
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
