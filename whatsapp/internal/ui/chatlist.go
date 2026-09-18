package ui

import (
	"context"
	"fmt"
	"github.com/charmbracelet/lipgloss"
	"sort"
	"strings"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// Filters, in the order the cycle visits them.
var chatFilters = []string{"all", "unread", "favourites", "pinned", "groups", "dms", "muted", "archived"}

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

	// self is the linked account, shown as "You" the way the phone app labels
	// the message-yourself chat.
	self domain.JID

	// marked are the multi-selected chats, by JID.
	marked map[string]bool
	// favourites are the chats tagged as such, read alongside the list.
	favourites map[string]bool
	// focused says the list has the keyboard, which is drawn as its chip and
	// its selection taking the accent.
	focused bool
	// perChat is how many lines each chat takes: 2 puts the last message under
	// the name. Zero means one, the dense layout the tests were written for.
	perChat int
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

// SetSelf records the linked account.
func (c *ChatList) SetSelf(j domain.JID) { c.self = j }

// DisplayName is the chat's name as this list shows it.
func (c *ChatList) DisplayName(ch domain.Chat) string {
	if !c.self.IsZero() && ch.JID.User == c.self.User {
		return "You"
	}
	return ch.DisplayName()
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
	c.loadFavourites(ctx)
	c.rebuild()
	return nil
}

// loadFavourites reads which contacts carry the favourite tag.
//
// WhatsApp's own favourites never reach a linked device, so a favourite here
// is one of wacli's local contact tags. It is a second query rather than a
// column on the chat because that is where the tag lives; it is cheap, and a
// failure only costs the filter.
func (c *ChatList) loadFavourites(ctx context.Context) {
	contacts, err := c.r.Contacts(ctx, store.ContactFilter{Tag: favouriteTag, Limit: 500})
	if err != nil {
		return
	}
	set := make(map[string]bool, len(contacts))
	for _, ct := range contacts {
		set[ct.JID.String()] = true
	}
	c.favourites = set
}

// Favourite reports whether a chat is one.
func (c *ChatList) Favourite(jid domain.JID) bool { return c.favourites[jid.String()] }

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
	case "favourites":
		return c.favourites[ch.JID.String()]
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

// RowToIndex maps a screen row inside the pane onto a chat, or -1. The header
// and the air under it never select anything.
func (c *ChatList) RowToIndex(row int) int {
	head := c.headerRows()
	if row < head {
		return -1
	}
	pos := row - head
	stride := c.chatLines()
	if pos%stride >= c.linesPerChat() {
		return -1 // the gap row between two chats: nothing is there to click.
	}
	i := c.offset + pos/stride
	if i < 0 || i >= len(c.view) {
		return -1
	}
	return i
}

// Offset is the first visible row, for hit testing and menu placement.
func (c *ChatList) Offset() int { return c.offset }

// SetLayout sets lines per chat, from [ui.layout] list_rows.
func (c *ChatList) SetLayout(rowsPerChat int) {
	c.perChat = clampInt(rowsPerChat, 1, 2)
	c.clampOffset()
}

// linesPerChat is never zero, and is one whenever the rows are drawn the
// plain way: only the pill rows have a second line, and a click mapped as if
// every chat took two lines selects the chat above the one clicked.
func (c *ChatList) linesPerChat() int {
	if c.perChat < 1 || c.styles.Shape != theme.ShapePill {
		return 1
	}
	return c.perChat
}

// gapLines is the blank row left between chats. The pill rows draw a card of
// their own per chat, and stacked with no gap they read as one fused block
// rather than a list of separate conversations.
func (c *ChatList) gapLines() int {
	if c.styles.Shape == theme.ShapePill {
		return 1
	}
	return 0
}

// headerGap is the blank row between the filter chip and the first chat: the
// header describes what is being searched or filtered, and butted straight
// against the first row it reads as part of that row rather than a caption
// above the list.
func (c *ChatList) headerGap() int {
	if c.styles.Shape == theme.ShapePill {
		return 1
	}
	return 0
}

// headerRows is the header chip plus the gap under it.
func (c *ChatList) headerRows() int { return 1 + c.headerGap() }

// chatLines is the full height one chat occupies on screen, its own rows plus
// the gap after it. Every place that maps a row to a chat or a chat to a
// height must use this, not linesPerChat, or the two fall out of step.
func (c *ChatList) chatLines() int { return c.linesPerChat() + c.gapLines() }

// SetFocused says whether the list has the keyboard.
func (c *ChatList) SetFocused(on bool) { c.focused = on }

// SetMarks records which chats are multi-selected, so the rows can say so.
func (c *ChatList) SetMarks(ids map[string]bool) { c.marked = ids }

// Marked reports whether a chat carries a mark.
func (c *ChatList) Marked(jid domain.JID) bool { return c.marked[jid.String()] }

// Rows is the visible slice.
func (c *ChatList) Rows() []domain.Chat { return c.view }

// All is every loaded chat, filter or no filter. The finder names chats from
// it: a result in an archived conversation still deserves a name.
func (c *ChatList) All() []domain.Chat { return c.all }

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

// Scroll moves the window without touching the selection.
//
// The wheel is for reading; it should no more change which chat is open than
// scrolling a page changes which link is focused. Moving the cursor is what
// j and k are for.
func (c *ChatList) Scroll(delta int) {
	rows := c.rows()
	if len(c.view) <= rows {
		c.offset = 0
		return
	}
	c.offset = clampInt(c.offset+delta, 0, len(c.view)-rows)
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
func (c *ChatList) rows() int { return maxInt(1, (c.height-c.headerRows())/c.chatLines()) }

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
	for j := 0; j < c.headerGap(); j++ {
		b.WriteString("\n")
	}

	pill := c.styles.Shape == theme.ShapePill
	gap := c.gapLines()
	rows := c.rows()
	for i := 0; i < rows; i++ {
		idx := c.offset + i
		if idx >= len(c.view) {
			for j := 0; j < c.chatLines(); j++ {
				b.WriteString("\n")
			}
			continue
		}
		if pill {
			for _, line := range c.pillRow(c.view[idx], idx == c.sel) {
				b.WriteString("\n")
				b.WriteString(line)
			}
			for j := 0; j < gap; j++ {
				b.WriteString("\n")
			}
			continue
		}
		b.WriteString("\n")
		b.WriteString(c.row(c.view[idx], idx == c.sel))
	}
	return b.String()
}

// pillRow draws one chat in the rice's shapes.
//
// The name and the time on the first line, the last message and the unread
// count under them - the order a phone uses, because it is the order the eye
// asks the questions in: who, when, what, how much. The initial in a small
// chip in the person's own colour tells rows apart before a name is read,
// and is the only colour a row carries unless it has something unread.
//
// The selection is a rounded surface behind the whole row: with the keyboard
// it takes the selection colour, without it a quiet raised fill, so the list
// still shows where it is while the conversation has focus.
func (c *ChatList) pillRow(ch domain.Chat, selected bool) []string {
	st := c.styles
	p := st.Palette
	now := c.now()
	unread := ch.Unread || ch.UnreadCount > 0
	name := c.DisplayName(ch)

	surface := p.Bg
	if selected {
		surface = p.Raised
		if c.focused {
			surface = p.Selection
		}
	}
	on := func(fg string, bold bool) lipgloss.Style {
		s := lipgloss.NewStyle().Foreground(lipgloss.Color(fg)).Bold(bold)
		if selected {
			s = s.Background(lipgloss.Color(surface))
		}
		return s
	}

	// Two cells of caps and one of padding each side come off the width.
	inner := maxInt(8, c.width-4)

	initial := strings.ToUpper(string([]rune(strings.TrimLeft(name, "+ "))[:1]))
	if ch.Kind == domain.KindGroup {
		initial = st.Icon("group")
	}
	avatarHex := p.Accent
	if c, ok := st.SenderStyle(name).GetForeground().(lipgloss.Color); ok {
		avatarHex = string(c)
	}
	avatarHex = theme.Readable(avatarHex, p.RaisedHi, p.Fg, 3.0)

	// Under glass, a row sitting on the plain background sits on nothing wa
	// drew - the compositor shows through it - so the cap glyphs must carry no
	// background of their own there, or they paint a solid square where the
	// wallpaper should be. A selected row's surface is a real fill regardless
	// of glass, so it keeps one.
	var avatarBehind lipgloss.TerminalColor = lipgloss.Color(surface)
	if st.Glass && !selected {
		avatarBehind = nil
	}
	avatar := theme.Pill(st.Shape, initial,
		lipgloss.Color(avatarHex), lipgloss.Color(p.RaisedHi), avatarBehind, true)
	avatarW := render.VisibleWidth(avatar)

	stamp := ""
	if !ch.LastMessageTS.IsZero() {
		stamp = relativeStamp(ch.LastMessageTS, now)
	}
	stampFg := p.Faint
	if unread && !ch.Muted(now) {
		stampFg = p.Accent
	}

	// States, as icons, after the name.
	var marks []string
	if c.marked[ch.JID.String()] {
		marks = append(marks, on(p.Accent, true).Render(st.Icon("sent")))
	}
	if c.favourites[ch.JID.String()] {
		marks = append(marks, on(p.Accent, false).Render(st.Icon("favourite")))
	}
	if ch.Pinned {
		marks = append(marks, on(p.Faint, false).Render(st.Icon("pin")))
	}
	if ch.Muted(now) {
		marks = append(marks, on(p.Faint, false).Render(st.Icon("muted")))
	}
	markStr := strings.Join(marks, on(p.Faint, false).Render(" "))
	if markStr != "" {
		markStr = on(p.Faint, false).Render(" ") + markStr
	}

	nameRoom := inner - avatarW - 1 - render.VisibleWidth(markStr) - render.VisibleWidth(stamp) - 1
	nameStr := on(p.Fg, unread).Render(render.Truncate(name, maxInt(1, nameRoom)))
	line1 := avatar + on(p.Fg, false).Render(" ") + nameStr + markStr
	line1 = padOn(line1, inner-render.VisibleWidth(stamp), surface, selected) + on(stampFg, unread).Render(stamp)

	badge := ""
	if ch.UnreadCount > 0 {
		fill, fg := p.Accent, p.OnAccent
		if ch.Muted(now) {
			fill, fg = p.RaisedHi, p.Muted
		}
		badge = theme.Pill(st.Shape, fmt.Sprintf("%d", ch.UnreadCount),
			lipgloss.Color(fg), lipgloss.Color(fill), avatarBehind, true)
	} else if ch.Unread {
		badge = on(p.Accent, true).Render(st.Icon("dot"))
	}
	// Blank under the avatar, not a second pill: a rounded shape here just to
	// fill the row's second line read as a duplicate, unlit avatar stacked
	// under the real one. Plain space keeps the column lined up; a selected
	// row's own fill (below) still colours it correctly, and under glass with
	// nothing selected it is left fully transparent like everything else that
	// is not content.
	indentStyle := lipgloss.NewStyle()
	if !(st.Glass && !selected) {
		indentStyle = indentStyle.Background(lipgloss.Color(surface))
	}
	indent := indentStyle.Render(strings.Repeat(" ", avatarW)) + on(p.Fg, false).Render(" ")
	snipRoom := inner - render.VisibleWidth(indent) - render.VisibleWidth(badge) - 1
	// wacli's "(message)" means a type it could not decode; quoting the
	// placeholder as though somebody had written it reads as a typo.
	snipText, snipStyle := render1line(ch.LastSnippet, 200), on(p.Muted, false)
	if strings.TrimSpace(ch.LastSnippet) == "(message)" || strings.TrimSpace(ch.LastSnippet) == "" {
		snipText, snipStyle = "message", on(p.Faint, false).Italic(true)
	}
	snippet := snipStyle.Render(render.Truncate(snipText, maxInt(1, snipRoom)))
	line2 := indent + snippet
	line2 = padOn(line2, inner-render.VisibleWidth(badge), surface, selected) + badge

	lines := []string{line1}
	if c.linesPerChat() > 1 {
		lines = append(lines, line2)
	}

	// The surface: caps and a cell of padding either side, drawn only behind
	// the selected row; every other row sits on the background.
	l, r := st.Shape.Caps()
	edge := lipgloss.NewStyle().Foreground(lipgloss.Color(surface))
	if !st.Glass {
		edge = edge.Background(lipgloss.Color(p.Bg))
	}
	out := make([]string, len(lines))
	for i, line := range lines {
		if !selected {
			out[i] = "  " + line + "  "
			continue
		}
		pad := lipgloss.NewStyle().Background(lipgloss.Color(surface)).Render(" ")
		out[i] = edge.Render(l) + pad + line + pad + edge.Render(r)
	}
	return out
}

// padOn fills a line to width on the row's surface.
func padOn(s string, width int, surface string, selected bool) string {
	gap := width - render.VisibleWidth(s)
	if gap <= 0 {
		return render.Truncate(s, maxInt(0, width))
	}
	fill := strings.Repeat(" ", gap)
	if selected {
		fill = lipgloss.NewStyle().Background(lipgloss.Color(surface)).Render(fill)
	}
	return s + fill
}

// header shows the filter and, while searching, the query.
func (c *ChatList) header() string {
	st := c.styles
	p := st.Palette

	label := st.Icon("filter") + " " + c.filter
	if c.search != "" {
		label = st.Icon("search") + " " + c.search
	}
	// The list's own chip is where focus shows: accent with the keyboard,
	// a quiet raised pill without it.
	fg, fill := p.Muted, p.Raised
	if c.focused {
		fg, fill = p.OnAccent, p.Accent
	}
	chip := st.Chip(render.Truncate(label, maxInt(1, c.width-8)), fg, fill, c.focused)
	count := st.ListTime.Render(fmt.Sprintf("%d", len(c.view)))

	gap := c.width - render.VisibleWidth(chip) - render.VisibleWidth(count) - 1
	if gap < 1 {
		return chip
	}
	return chip + strings.Repeat(" ", gap) + count
}

// row renders one chat: a cursor bar, markers, the name, an unread badge and
// the time of the last message.
//
// The pieces are styled separately rather than the row as a whole. A row drawn
// in one colour reads as a wall of names; the eye wants the time quiet, the
// count loud, and the name somewhere in between - which is exactly the order
// in which those three things matter.
func (c *ChatList) row(ch domain.Chat, selected bool) string {
	unread := ch.Unread || ch.UnreadCount > 0

	// A bar rather than a background: it marks the row without repainting it,
	// so the name keeps whatever colour says whether it has been read.
	cursor := " "
	if selected {
		cursor = "▌"
	}

	marks := ""
	if c.favourites[ch.JID.String()] {
		marks += "★"
	}
	if c.marked[ch.JID.String()] {
		// A marked chat says so where the pin would be: the eye is already
		// there, and a selection you cannot see is a selection you will act on
		// by accident.
		marks += "✓"
	}
	if ch.Pinned {
		marks += "▪"
	}
	if ch.Muted(c.now()) {
		marks += "○"
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
		// A leading space of its own: without a badge between them, a
		// truncated name would otherwise run straight into the date.
		stamp = " " + relativeStamp(ch.LastMessageTS, c.now()) + " "
	}

	nameWidth := c.width - render.VisibleWidth(cursor) - render.VisibleWidth(marks) -
		render.VisibleWidth(badge) - render.VisibleWidth(stamp)
	if nameWidth < 1 {
		nameWidth = 1
	}
	name := render.Pad(render.Truncate(c.DisplayName(ch), nameWidth), nameWidth)

	nameStyle := c.styles.ListRow
	switch {
	case selected:
		nameStyle = c.styles.ListRowSel
	case unread:
		nameStyle = c.styles.ListName
	}

	badgeStyle := c.styles.ListBadge
	if ch.Muted(c.now()) {
		// A muted chat is one you asked not to be told about, so its count is
		// information rather than a summons.
		badgeStyle = c.styles.ListMute
	}

	return c.styles.ListPin.Render(cursor) +
		c.styles.ListMute.Render(marks) +
		nameStyle.Render(name) +
		badgeStyle.Render(badge) +
		c.styles.ListTime.Render(stamp)
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

// SetStyles replaces the style set, for a reload.
func (c *ChatList) SetStyles(st theme.Styles) { c.styles = st }
