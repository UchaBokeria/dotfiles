package ui

import (
	"context"
	"fmt"
	"os"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/charmbracelet/lipgloss"
	"github.com/muesli/termenv"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
)

func TestMain(m *testing.M) {
	// Colourless, so assertions match on text rather than escape codes.
	lipgloss.SetColorProfile(termenv.Ascii)
	os.Exit(m.Run())
}

func plainStyles(t *testing.T) theme.Styles {
	t.Helper()
	p, err := theme.Load("")
	if err != nil {
		t.Fatal(err)
	}
	return theme.New(p, "rounded")
}

func jid(t *testing.T, s string) domain.JID {
	t.Helper()
	j, err := domain.ParseJID(s)
	if err != nil {
		t.Fatal(err)
	}
	return j
}

// fakeStore is an in-memory store.Reader. It counts reads per chat so a test
// can assert that a live event refreshed only what it named.
type fakeStore struct {
	mu       sync.Mutex
	chats    []domain.Chat
	messages map[string][]domain.Message
	search   []domain.Message
	stats    store.Stats

	chatLoads map[string]int
	listLoads int
	err       error
}

func newFakeStore(chats ...domain.Chat) *fakeStore {
	return &fakeStore{
		chats:     chats,
		messages:  map[string][]domain.Message{},
		chatLoads: map[string]int{},
	}
}

func (f *fakeStore) Chats(_ context.Context, filter store.ChatFilter) ([]domain.Chat, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.err != nil {
		return nil, f.err
	}
	f.listLoads++
	out := append([]domain.Chat{}, f.chats...)
	return out, nil
}

func (f *fakeStore) Chat(_ context.Context, j domain.JID) (domain.Chat, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.chatLoads[j.String()]++
	for _, c := range f.chats {
		if c.JID == j {
			return c, nil
		}
	}
	return domain.Chat{}, store.ErrNotFound
}

func (f *fakeStore) Messages(_ context.Context, filter store.MessageFilter) ([]domain.Message, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.err != nil {
		return nil, f.err
	}
	all := f.messages[filter.Chat.String()]

	// Newest first, like the real reader.
	desc := make([]domain.Message, len(all))
	for i := range all {
		desc[i] = all[len(all)-1-i]
	}

	var out []domain.Message
	for _, m := range desc {
		if !filter.BeforeTS.IsZero() {
			if m.TS.After(filter.BeforeTS) ||
				(m.TS.Equal(filter.BeforeTS) && m.RowID >= filter.BeforeRowID) {
				continue
			}
		}
		out = append(out, m)
		if filter.Limit > 0 && len(out) >= filter.Limit {
			break
		}
	}
	if filter.Ascending {
		for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
			out[i], out[j] = out[j], out[i]
		}
	}
	return out, nil
}

func (f *fakeStore) Message(_ context.Context, chat domain.JID, id string) (domain.Message, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	for _, m := range f.messages[chat.String()] {
		if m.ID == id {
			return m, nil
		}
	}
	return domain.Message{}, store.ErrNotFound
}

func (f *fakeStore) Search(_ context.Context, q store.Query) ([]domain.Message, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	// A canned answer when a test set one - the quickfix tests do - and a real
	// search over what the fake holds otherwise, so the finder is exercised
	// rather than mocked.
	if len(f.search) > 0 {
		return append([]domain.Message{}, f.search...), nil
	}
	if strings.TrimSpace(q.Text) == "" && !q.Browse {
		return nil, nil
	}

	var out []domain.Message
	for jid, msgs := range f.messages {
		if !q.Chat.IsZero() && q.Chat.String() != jid {
			continue
		}
		for _, m := range msgs {
			if !fakeMatches(m, q) {
				continue
			}
			out = append(out, m)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].TS.After(out[j].TS) })
	if q.Limit > 0 && len(out) > q.Limit {
		out = out[:q.Limit]
	}
	return out, nil
}

// fakeMatches is the fake's version of the store's where clause.
func fakeMatches(m domain.Message, q store.Query) bool {
	hay := strings.ToLower(m.Text)
	if m.Media != nil {
		hay += " " + strings.ToLower(m.Media.Caption+" "+m.Media.Filename)
	}
	if text := strings.ToLower(strings.TrimSpace(q.Text)); text != "" &&
		!strings.Contains(hay, text) {
		return false
	}
	if q.HasMedia && (m.Media == nil || m.Media.Type == "") {
		return false
	}
	if len(q.Kinds) > 0 {
		kind := ""
		if m.Media != nil {
			kind = m.Media.Type
		}
		found := false
		for _, k := range q.Kinds {
			if k == kind {
				found = true
			}
		}
		if !found {
			return false
		}
	}
	if q.HasLink && !strings.Contains(hay, "http") {
		return false
	}
	if q.FromMe && !m.FromMe {
		return false
	}
	return true
}

// setText rewrites one stored message, for tests about searching.
func (f *fakeStore) setText(chat, id, text string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	for i, m := range f.messages[chat] {
		if m.ID == id {
			f.messages[chat][i].Text = text
			return
		}
	}
}

// setMedia attaches a file to one stored message.
func (f *fakeStore) setMedia(chat, id string, ref *domain.MediaRef) {
	f.mu.Lock()
	defer f.mu.Unlock()
	for i, m := range f.messages[chat] {
		if m.ID == id {
			f.messages[chat][i].Media = ref
			return
		}
	}
}

func (f *fakeStore) Contact(_ context.Context, j domain.JID) (domain.Contact, error) {
	return domain.Contact{JID: j}, nil
}

// Contacts is the address book the fake knows: one per chat, plus anything a
// test added.
func (f *fakeStore) Contacts(_ context.Context, filter store.ContactFilter) ([]domain.Contact, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	var out []domain.Contact
	for _, c := range f.chats {
		contact := domain.Contact{JID: c.JID, Name: c.Name}
		if filter.Query != "" &&
			!strings.Contains(strings.ToLower(contact.DisplayName()), strings.ToLower(filter.Query)) {
			continue
		}
		out = append(out, contact)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].DisplayName() < out[j].DisplayName() })
	return out, nil
}

func (f *fakeStore) Stats(context.Context) (store.Stats, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.stats, nil
}

// ChatStats counts what the fake holds, the same way the real one does.
func (f *fakeStore) ChatStats(_ context.Context, jid domain.JID) (store.ChatStats, error) {
	st := store.ChatStats{Chat: jid, Kinds: map[string]int{}}
	for _, m := range f.messages[jid.String()] {
		st.Messages++
		if m.FromMe {
			st.Sent++
		} else {
			st.Received++
		}
		if m.Media != nil && m.Media.Type != "" {
			st.Kinds[m.Media.Type]++
			st.Bytes += m.Media.Length
		}
		if strings.Contains(m.Text, "http") {
			st.Links++
		}
		if st.First.IsZero() || m.TS.Before(st.First) {
			st.First = m.TS
		}
		if m.TS.After(st.Last) {
			st.Last = m.TS
		}
	}
	return st, nil
}

func (f *fakeStore) Close() error { return nil }

func (f *fakeStore) setChat(c domain.Chat) {
	f.mu.Lock()
	defer f.mu.Unlock()
	for i := range f.chats {
		if f.chats[i].JID == c.JID {
			f.chats[i] = c
			return
		}
	}
	f.chats = append(f.chats, c)
}

func (f *fakeStore) loadsOf(j string) int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.chatLoads[j]
}

// chat builds a chat fixture.
func chat(t *testing.T, name, id string, opts ...func(*domain.Chat)) domain.Chat {
	t.Helper()
	c := domain.Chat{
		JID:           jid(t, id),
		Kind:          domain.KindDM,
		Name:          name,
		LastMessageTS: time.Date(2026, 9, 8, 12, 0, 0, 0, time.UTC),
	}
	if strings.HasSuffix(id, "@g.us") {
		c.Kind = domain.KindGroup
	}
	for _, o := range opts {
		o(&c)
	}
	return c
}

func unread(n int) func(*domain.Chat) {
	return func(c *domain.Chat) { c.UnreadCount = n; c.Unread = n > 0 }
}
func pinned() func(*domain.Chat)   { return func(c *domain.Chat) { c.Pinned = true } }
func archived() func(*domain.Chat) { return func(c *domain.Chat) { c.Archived = true } }
func mutedFor(d time.Duration) func(*domain.Chat) {
	return func(c *domain.Chat) { c.MutedUntil = time.Now().Add(d) }
}
func at(ts time.Time) func(*domain.Chat) {
	return func(c *domain.Chat) { c.LastMessageTS = ts }
}

// msgs seeds n messages one minute apart, oldest first.
func msgs(t *testing.T, chatID string, n int) []domain.Message {
	t.Helper()
	base := time.Date(2026, 9, 8, 9, 0, 0, 0, time.UTC)
	out := make([]domain.Message, 0, n)
	for i := 1; i <= n; i++ {
		out = append(out, domain.Message{
			RowID:   int64(i),
			ChatJID: jid(t, chatID),
			ID:      fmt.Sprintf("M%d", i),
			TS:      base.Add(time.Duration(i) * time.Minute),
			Text:    fmt.Sprintf("message %d", i),
		})
	}
	return out
}

func chatNames(cs []domain.Chat) []string {
	out := make([]string, 0, len(cs))
	for _, c := range cs {
		out = append(out, c.Name)
	}
	return out
}

func messageIDs(ms []domain.Message) []string {
	out := make([]string, 0, len(ms))
	for _, m := range ms {
		out = append(out, m.ID)
	}
	return out
}

// SetMediaForTest attaches an attachment to a loaded message, so the media
// paths can be exercised without a store full of photographs.
func (p *MessagePane) SetMediaForTest(msgID string, ref *domain.MediaRef) bool {
	i, ok := p.byID[msgID]
	if !ok {
		return false
	}
	p.messages[i].Media = ref
	p.dirty = true
	return true
}

// SetTextForTest rewrites a loaded message's text.
func (p *MessagePane) SetTextForTest(msgID, text string) bool {
	i, ok := p.byID[msgID]
	if !ok {
		return false
	}
	p.messages[i].Text = text
	p.dirty = true
	return true
}

// SetChatForTest replaces the open conversation's chat record.
func (p *MessagePane) SetChatForTest(c domain.Chat) { p.chat = c }
