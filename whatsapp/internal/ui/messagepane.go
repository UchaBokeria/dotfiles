package ui

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// pageSize is how many messages are fetched at a time. Large enough that
// scrolling rarely waits, small enough that opening a chat is instant.
const pageSize = 60

var localSeq atomic.Int64

// MessagePane is the right-hand conversation view.
//
// Messages are held oldest first, which is the order they are drawn in;
// paging backwards prepends. The selection is tracked by message id so that a
// prepend, a live update, or a reconciled send does not move the cursor.
type MessagePane struct {
	r      store.Reader
	cache  *render.Cache
	styles theme.Styles

	width  int
	height int

	chat     domain.Chat
	messages []domain.Message
	byID     map[string]int

	sel       string // message id under the cursor
	offset    int    // first visible screen row
	lines     []render.Line
	dirty     bool
	exhausted bool

	scrolloff    int
	timestamp    string
	daySeparator string
	maxBubblePct int
	mediaView    render.MediaPreviewer
	mediaRows    int
	links        bool

	searchPattern string
	searchMatches []int
	searchIndex   int
	highlighted   bool

	err error
}

// NewMessagePane returns an empty pane.
func NewMessagePane(r store.Reader, cache *render.Cache, st theme.Styles, w, h int) *MessagePane {
	if cache == nil {
		cache = render.NewCache(512)
	}
	return &MessagePane{
		r:            r,
		cache:        cache,
		styles:       st,
		width:        w,
		height:       h,
		byID:         map[string]int{},
		scrolloff:    5,
		timestamp:    "15:04",
		daySeparator: "Monday, 2 January 2006",
		maxBubblePct: 66,
		dirty:        true,
	}
}

// Invalidate forces the next render to rebuild, after a setting changed what
// a message looks like.
func (p *MessagePane) Invalidate() {
	p.dirty = true
	p.cache.Clear()
}

// SetMedia installs the attachment previewer.
func (p *MessagePane) SetMedia(v render.MediaPreviewer) {
	p.mediaView = v
	p.dirty = true
	p.cache.Clear()
}

// SetLinks turns clickable links on or off.
func (p *MessagePane) SetLinks(on bool) {
	if on == p.links {
		return
	}
	p.links = on
	p.Invalidate()
}

// SetMediaRows caps how tall an inline preview may be.
func (p *MessagePane) SetMediaRows(n int) {
	if n <= 0 {
		n = 10
	}
	if n == p.mediaRows {
		return
	}
	p.mediaRows = n
	p.dirty = true
	p.cache.Clear()
}

// Configure applies the display settings.
func (p *MessagePane) Configure(scrolloff int, timestamp, daySeparator string, maxBubblePct int) {
	p.scrolloff = scrolloff
	p.timestamp = timestamp
	p.daySeparator = daySeparator
	if maxBubblePct > 0 {
		p.maxBubblePct = maxBubblePct
	}
	p.dirty = true
}

// Open loads the most recent page of a chat and puts the cursor on the newest
// message, which is where a conversation is read from.
func (p *MessagePane) Open(ctx context.Context, c domain.Chat) error {
	page, err := p.r.Messages(ctx, store.MessageFilter{Chat: c.JID, Limit: pageSize})
	if err != nil {
		return err
	}
	p.chat = c
	p.messages = reversed(page)
	p.reindex()
	p.exhausted = len(page) < pageSize
	p.clearSearch()

	if n := len(p.messages); n > 0 {
		p.sel = p.messages[n-1].ID
	} else {
		p.sel = ""
	}
	p.dirty = true
	p.scrollToSelection()
	return nil
}

// Chat is the conversation on screen.
func (p *MessagePane) Chat() domain.Chat { return p.chat }

// Messages is the loaded window, oldest first.
func (p *MessagePane) Messages() []domain.Message { return p.messages }

// Count is how many messages are loaded.
func (p *MessagePane) Count() int { return len(p.messages) }

// Index is the cursor's position, or -1.
func (p *MessagePane) Index() int {
	if i, ok := p.byID[p.sel]; ok {
		return i
	}
	return -1
}

// Selected returns the message under the cursor.
func (p *MessagePane) Selected() (domain.Message, bool) {
	i, ok := p.byID[p.sel]
	if !ok || i >= len(p.messages) {
		return domain.Message{}, false
	}
	return p.messages[i], true
}

// LoadOlder prepends the previous page and returns how many arrived.
//
// Deduplication is not optional: the CLI reader pages by timestamp alone, so a
// page boundary inside a group of same-second messages repeats one.
func (p *MessagePane) LoadOlder(ctx context.Context) (int, error) {
	if p.exhausted || len(p.messages) == 0 {
		return 0, nil
	}
	oldest := p.messages[0]
	page, err := p.r.Messages(ctx, store.MessageFilter{
		Chat:        p.chat.JID,
		Limit:       pageSize,
		BeforeTS:    oldest.TS,
		BeforeRowID: oldest.RowID,
	})
	if err != nil {
		return 0, err
	}
	if len(page) < pageSize {
		p.exhausted = true
	}

	var fresh []domain.Message
	for _, m := range reversed(page) {
		if _, seen := p.byID[m.ID]; !seen {
			fresh = append(fresh, m)
		}
	}
	if len(fresh) == 0 {
		return 0, nil
	}
	p.messages = append(fresh, p.messages...)
	p.reindex()
	p.dirty = true
	p.scrollToSelection()
	return len(fresh), nil
}

// Refresh re-reads the newest page, keeping any optimistic messages that have
// not been reconciled yet.
func (p *MessagePane) Refresh(ctx context.Context) error {
	if p.chat.JID.IsZero() {
		return nil
	}
	page, err := p.r.Messages(ctx, store.MessageFilter{Chat: p.chat.JID, Limit: pageSize})
	if err != nil {
		return err
	}
	fresh := reversed(page)

	// Anything older than the refreshed window is kept, so a scrolled-back
	// reader does not lose their place when a message arrives.
	var older []domain.Message
	if len(fresh) > 0 {
		cut := fresh[0]
		for _, m := range p.messages {
			if m.TS.Before(cut.TS) {
				older = append(older, m)
			}
		}
	}
	var pending []domain.Message
	for _, m := range p.messages {
		if m.Local {
			pending = append(pending, m)
		}
	}

	p.messages = append(append(older, fresh...), pending...)
	p.reindex()
	p.dirty = true
	p.scrollToSelection()
	return nil
}

func (p *MessagePane) reindex() {
	p.byID = make(map[string]int, len(p.messages))
	for i, m := range p.messages {
		p.byID[m.ID] = i
	}
}

// AddOptimistic shows a message before the network has confirmed it. A send
// takes about 2.7 seconds through wacli's delegation socket, which is far too
// long to leave the composer looking like it did nothing.
func (p *MessagePane) AddOptimistic(text string) domain.Message {
	m := domain.Message{
		ChatJID:  p.chat.JID,
		ID:       fmt.Sprintf("local-%d", localSeq.Add(1)),
		TS:       time.Now(),
		FromMe:   true,
		Text:     text,
		Delivery: domain.Pending,
		Local:    true,
	}
	p.messages = append(p.messages, m)
	p.reindex()
	p.sel = m.ID
	p.dirty = true
	p.scrollToSelection()
	return m
}

// Reconcile replaces an optimistic message's id with the real one.
func (p *MessagePane) Reconcile(localID, realID string) bool {
	i, ok := p.byID[localID]
	if !ok {
		return false
	}
	p.messages[i].ID = realID
	p.messages[i].Local = false
	p.messages[i].Delivery = domain.Sent
	if p.sel == localID {
		p.sel = realID
	}
	p.reindex()
	p.dirty = true
	return true
}

// FailOptimistic marks a send as failed, keeping the bubble on screen with the
// reason. Removing it would lose the text the user typed.
func (p *MessagePane) FailOptimistic(localID string, err error) bool {
	i, ok := p.byID[localID]
	if !ok {
		return false
	}
	p.messages[i].Delivery = domain.Failed
	if err != nil {
		p.messages[i].Err = err.Error()
	}
	p.dirty = true
	return true
}

// ApplyReceipt advances a message's delivery state.
func (p *MessagePane) ApplyReceipt(id string, state domain.DeliveryState) bool {
	i, ok := p.byID[id]
	if !ok {
		return false
	}
	// Delivery only moves forwards: a late "delivered" must not undo "read".
	if state <= p.messages[i].Delivery && p.messages[i].Delivery != domain.Failed {
		return false
	}
	p.messages[i].Delivery = state
	p.dirty = true
	return true
}

// --- movement --------------------------------------------------------------

// Move shifts the cursor by whole messages.
func (p *MessagePane) Move(delta int) {
	if len(p.messages) == 0 {
		return
	}
	i := clampInt(p.Index()+delta, 0, len(p.messages)-1)
	p.sel = p.messages[i].ID
	p.scrollToSelection()
}

// Top and Bottom are gg and G.
func (p *MessagePane) Top() { p.Move(-len(p.messages)) }
func (p *MessagePane) Bottom() {
	if n := len(p.messages); n > 0 {
		p.sel = p.messages[n-1].ID
		p.scrollToSelection()
	}
}

// Scroll moves the window without touching the selection, for the wheel.
func (p *MessagePane) Scroll(delta int) {
	lines := p.render()
	if len(lines) <= p.height {
		p.offset = 0
		return
	}
	p.offset = clampInt(p.offset+delta, 0, len(lines)-p.height)
}

// HalfPage and Page scroll by screen rows rather than messages, because that
// is what ctrl-d means to the hand that presses it.
func (p *MessagePane) HalfPage(dir int) { p.scrollRows(dir * maxInt(1, p.height/2)) }
func (p *MessagePane) Page(dir int)     { p.scrollRows(dir * maxInt(1, p.height)) }

// scrollRows moves the viewport and drags the cursor to the nearest message
// still on screen.
func (p *MessagePane) scrollRows(rows int) {
	lines := p.render()
	if len(lines) == 0 {
		return
	}
	p.offset = clampInt(p.offset+rows, 0, maxInt(0, len(lines)-p.height))

	// Put the cursor on a message inside the new window.
	want := p.offset
	if rows < 0 {
		want = p.offset
	} else {
		want = p.offset + p.height - 1
	}
	want = clampInt(want, 0, len(lines)-1)
	for i := want; i >= 0 && i < len(lines); {
		if !lines[i].IsSeparator && lines[i].MessageIndex >= 0 {
			p.sel = p.messages[lines[i].MessageIndex].ID
			return
		}
		if rows < 0 {
			i++
		} else {
			i--
		}
	}
}

// Recentre implements zz, zt and zb.
func (p *MessagePane) Recentre(where string) {
	lines := p.render()
	row := render.FirstRowOf(lines, p.Index())
	if row < 0 {
		return
	}
	switch where {
	case "top":
		p.offset = row
	case "bottom":
		p.offset = row - p.height + 1
	default:
		p.offset = row - p.height/2
	}
	p.offset = clampInt(p.offset, 0, maxInt(0, len(lines)-p.height))
}

// scrollToSelection keeps the cursor on screen with scrolloff rows of context.
func (p *MessagePane) scrollToSelection() {
	lines := p.render()
	if len(lines) == 0 {
		p.offset = 0
		return
	}
	first := render.FirstRowOf(lines, p.Index())
	last := render.LastRowOf(lines, p.Index())
	if first < 0 {
		p.offset = clampInt(p.offset, 0, maxInt(0, len(lines)-p.height))
		return
	}

	pad := p.scrolloff
	if pad > (p.height-1)/2 {
		pad = maxInt(0, (p.height-1)/2)
	}
	if first-pad < p.offset {
		p.offset = first - pad
	}
	if last+pad >= p.offset+p.height {
		p.offset = last + pad - p.height + 1
	}
	p.offset = clampInt(p.offset, 0, maxInt(0, len(lines)-p.height))
}

// Offset is the first visible screen row, for hit testing and tests.
func (p *MessagePane) Offset() int { return p.offset }

// AtTop reports whether the oldest loaded message is on screen, which is when
// the caller should fetch another page.
func (p *MessagePane) AtTop() bool { return p.offset == 0 }

// Exhausted reports whether the whole history is loaded.
func (p *MessagePane) Exhausted() bool { return p.exhausted }

// RowToMessage maps a screen row inside the pane onto a message, or -1 for a
// day separator or empty space.
func (p *MessagePane) RowToMessage(row int) int {
	lines := p.render()
	i := p.offset + row
	if i < 0 || i >= len(lines) {
		return -1
	}
	if lines[i].IsSeparator {
		return -1
	}
	return lines[i].MessageIndex
}

// SelectIndex puts the cursor on a message by position.
func (p *MessagePane) SelectIndex(i int) { p.selectIndex(i) }

// --- search ----------------------------------------------------------------

// Search finds a pattern within the loaded messages and moves to the first
// match in the given direction. It reports whether anything matched.
func (p *MessagePane) Search(pattern string, forward bool, ignoreCase, smartCase bool) bool {
	p.searchPattern = pattern
	p.searchMatches = nil
	p.searchIndex = -1
	p.highlighted = false
	if pattern == "" {
		return false
	}

	fold := ignoreCase
	if smartCase && strings.ToLower(pattern) != pattern {
		fold = false
	}
	needle := pattern
	if fold {
		needle = strings.ToLower(pattern)
	}

	for i, m := range p.messages {
		hay := m.Body()
		if fold {
			hay = strings.ToLower(hay)
		}
		if strings.Contains(hay, needle) {
			p.searchMatches = append(p.searchMatches, i)
		}
	}
	if len(p.searchMatches) == 0 {
		return false
	}
	p.highlighted = true
	return p.Next(forward)
}

// Next moves to the next or previous match, wrapping around.
func (p *MessagePane) Next(forward bool) bool {
	if len(p.searchMatches) == 0 {
		return false
	}
	cur := p.Index()

	if forward {
		for i, idx := range p.searchMatches {
			if idx > cur {
				p.searchIndex = i
				p.selectIndex(idx)
				return true
			}
		}
		p.searchIndex = 0
	} else {
		for i := len(p.searchMatches) - 1; i >= 0; i-- {
			if p.searchMatches[i] < cur {
				p.searchIndex = i
				p.selectIndex(p.searchMatches[i])
				return true
			}
		}
		p.searchIndex = len(p.searchMatches) - 1
	}
	p.selectIndex(p.searchMatches[p.searchIndex])
	return true
}

func (p *MessagePane) selectIndex(i int) {
	if i < 0 || i >= len(p.messages) {
		return
	}
	p.sel = p.messages[i].ID
	p.scrollToSelection()
}

// ClearHighlight is what Esc in normal mode does.
func (p *MessagePane) ClearHighlight() { p.highlighted = false }

// Highlighted reports whether search matches are marked.
func (p *MessagePane) Highlighted() bool { return p.highlighted }

// MatchCount is how many messages matched the last search.
func (p *MessagePane) MatchCount() int { return len(p.searchMatches) }

func (p *MessagePane) clearSearch() {
	p.searchPattern = ""
	p.searchMatches = nil
	p.searchIndex = -1
	p.highlighted = false
}

// --- rendering -------------------------------------------------------------

// Resize sets the pane's dimensions and invalidates the layout.
func (p *MessagePane) Resize(w, h int) {
	if w == p.width && h == p.height {
		return
	}
	p.width, p.height = w, h
	p.dirty = true
	p.scrollToSelection()
}

// Gutter width: four columns is enough for three digits and a space, which
// covers any window a person can read.
const gutterWidth = 4

func (p *MessagePane) bodyWidth() int { return maxInt(8, p.width-gutterWidth) }

func (p *MessagePane) options() render.Options {
	return render.Options{
		Width:      p.bodyWidth(),
		MaxBubble:  maxInt(10, p.bodyWidth()*p.maxBubblePct/100),
		Timestamp:  p.timestamp,
		ShowSender: p.chat.IsGroup(),
		Styles:     p.styles,
		Media:      p.mediaView,
		MediaRows:  p.mediaRows,
		Links:      p.links,
	}
}

// render lays the conversation out, reusing the previous layout when nothing
// has changed.
func (p *MessagePane) render() []render.Line {
	if !p.dirty && p.lines != nil {
		return p.lines
	}
	o := p.options()
	var out []render.Line
	var lastDay time.Time
	haveDay := false

	for i, m := range p.messages {
		day := m.TS.Truncate(24 * time.Hour)
		if !haveDay || !day.Equal(lastDay) {
			out = append(out, render.Line{
				Text:         render.DaySeparator(m.TS, o, p.daySeparator),
				MessageIndex: -1,
				IsSeparator:  true,
			})
			lastDay, haveDay = day, true
		}
		for _, l := range p.cache.Bubble(m, o) {
			out = append(out, render.Line{Text: l, MessageIndex: i})
		}
		if i < len(p.messages)-1 {
			out = append(out, render.Line{Text: "", MessageIndex: i})
		}
	}
	p.lines = out
	p.dirty = false
	return out
}

// View renders the visible window with its gutter.
func (p *MessagePane) View() string {
	if p.chat.JID.IsZero() {
		return p.styles.Placeholder.Render("no chat selected")
	}
	lines := p.render()
	cursor := p.Index()

	var b strings.Builder
	for row := 0; row < p.height; row++ {
		if row > 0 {
			b.WriteString("\n")
		}
		i := p.offset + row
		if i < 0 || i >= len(lines) {
			b.WriteString(strings.Repeat(" ", gutterWidth))
			continue
		}
		// Only the first row of a message carries a number, so a five-line
		// bubble does not look like five messages.
		firstRow := i == 0 || lines[i-1].IsSeparator ||
			lines[i-1].MessageIndex != lines[i].MessageIndex
		b.WriteString(p.gutter(lines[i], cursor, firstRow))
		b.WriteString(lines[i].Text)
	}
	return b.String()
}

// gutter draws the message number beside the first row of each message, in the
// hybrid absolute-and-relative style the author's Neovim uses, so a count like
// 5j is something to read rather than estimate.
func (p *MessagePane) gutter(l render.Line, cursor int, firstRow bool) string {
	if l.IsSeparator || l.MessageIndex < 0 || !firstRow {
		return strings.Repeat(" ", gutterWidth)
	}

	dist := l.MessageIndex - cursor
	if dist == 0 {
		return render.PadLeft(p.styles.GutterCur.Render(strconv.Itoa(l.MessageIndex+1)), gutterWidth-1) + " "
	}
	if dist < 0 {
		dist = -dist
	}
	return render.PadLeft(p.styles.Gutter.Render(strconv.Itoa(dist)), gutterWidth-1) + " "
}

// Err is the last read error, for the status line.
func (p *MessagePane) Err() error { return p.err }

func reversed(in []domain.Message) []domain.Message {
	out := make([]domain.Message, len(in))
	for i := range in {
		out[i] = in[len(in)-1-i]
	}
	return out
}

// ApplyReaction shows a reaction at once, without waiting for the store.
//
// `send react` returns as soon as WhatsApp accepts it, but the row appears
// only when the sync process writes it - a second or two later, and sometimes
// under a different chat address. Re-reading immediately therefore found
// nothing, which is why a reaction looked like it had done nothing until the
// client was closed and opened again.
func (p *MessagePane) ApplyReaction(msgID, emoji string, by domain.JID, byName string, fromMe bool) bool {
	i, ok := p.byID[msgID]
	if !ok {
		return false
	}
	p.messages[i].Reactions = store.ApplyReaction(p.messages[i].Reactions, domain.Reaction{
		Emoji:  emoji,
		By:     by,
		ByName: byName,
		FromMe: fromMe,
		At:     time.Now(),
	})
	p.dirty = true
	return true
}

// SetReactions replaces a message's reactions outright. Used to undo one that
// was drawn optimistically and then failed to send.
func (p *MessagePane) SetReactions(msgID string, rs []domain.Reaction) bool {
	i, ok := p.byID[msgID]
	if !ok {
		return false
	}
	p.messages[i].Reactions = rs
	p.dirty = true
	return true
}
