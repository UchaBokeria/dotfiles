package ui

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// The finder.
//
// :grep fills the quickfix list, which is the right tool when the results are
// a work list to walk through. The finder is the other half: type, watch the
// matches narrow, press enter, land on the message. It searches the store on
// every keystroke rather than filtering a list held in memory, because the
// store holds a hundred thousand messages and the interesting one is rarely in
// the last hundred.

// findScope is what a finder searches.
type findScope struct {
	name  string
	title string
	// query is the store query, minus the text the user types.
	query store.Query
}

// findScopes are the tabs: everything, attachments by kind, links, starred.
var findScopes = []findScope{
	{name: "messages", title: "find · messages", query: store.Query{Browse: true}},
	{name: "media", title: "find · attachments", query: store.Query{HasMedia: true, Browse: true}},
	{name: "images", title: "find · pictures", query: store.Query{Kinds: []string{"image", "sticker"}, Browse: true}},
	{name: "video", title: "find · video", query: store.Query{Kinds: []string{"video"}, Browse: true}},
	{name: "audio", title: "find · audio and voice", query: store.Query{Kinds: []string{"audio", "ptt"}, Browse: true}},
	{name: "docs", title: "find · documents", query: store.Query{Kinds: []string{"document"}, Browse: true}},
	{name: "links", title: "find · links", query: store.Query{HasLink: true, Browse: true}},
	{name: "starred", title: "find · starred", query: store.Query{Starred: true, Browse: true}},
}

// findScopeByName is the scope a command or keymap asked for.
func findScopeByName(name string) (findScope, bool) {
	for _, s := range findScopes {
		if s.name == name {
			return s, true
		}
	}
	return findScope{}, false
}

// openFinder shows the finder for one scope, over every chat or just this one.
func (a *App) openFinder(scope findScope, thisChat bool) error {
	if a.deps.Store == nil {
		return fmt.Errorf("no store to search")
	}
	q := scope.query
	title := scope.title
	if thisChat {
		chat := a.pane.Chat()
		if chat.JID.IsZero() {
			return fmt.Errorf("no chat is open")
		}
		q.Chat = chat.JID
		title += " · " + chat.DisplayName()
	}

	a.picker.OpenLive(title, func(text string) []PickerItem {
		return a.findRows(q, text)
	}, func(it PickerItem) error {
		return a.openFinderResult(it)
	})
	return nil
}

// findRows runs one search and turns the messages into rows.
func (a *App) findRows(q store.Query, text string) []PickerItem {
	q.Text = text
	if q.Limit == 0 {
		q.Limit = 200
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	msgs, err := a.deps.Store.Search(ctx, q)
	if err != nil {
		a.log.Warnf("finding: %v", err)
		return nil
	}

	out := make([]PickerItem, 0, len(msgs))
	for _, m := range msgs {
		out = append(out, PickerItem{
			Label:  findLabel(a, m),
			Detail: m.TS.Format("2006-01-02 15:04"),
			// The chat and the message, so enter can land on it. A message id
			// is unique per chat, not globally.
			Value: m.ChatJID.String() + "\x00" + m.ID,
		})
	}
	return out
}

// findLabel is one result: who, where, and what.
func findLabel(a *App, m domain.Message) string {
	who := a.chatName(m.ChatJID)
	what := strings.TrimSpace(m.Body())
	if m.Media != nil && m.Media.Type != "" {
		name := m.Media.Filename
		if name == "" {
			name = m.Media.Type
		}
		size := ""
		if m.Media.Length > 0 {
			size = " " + media.HumanSize(m.Media.Length)
		}
		chip := "[" + m.Media.Type + "] " + name + size
		if what == "" {
			what = chip
		} else {
			what = chip + " — " + what
		}
	}
	if what == "" {
		what = "(no text)"
	}
	return render.Pad(render.Truncate(who, 18), 18) + " │ " + render1line(what, 200)
}

// chatName is what to call a chat in a list, without a store round trip per
// row: the chat list already knows the names.
//
// The match is on the user part as well as the whole address. One person can
// be stored under a LID and a phone number both, and a result that came back
// under the other spelling should still say "You" rather than a bare number.
func (a *App) chatName(jid domain.JID) string {
	for _, c := range a.list.All() {
		if c.JID == jid || (c.JID.User != "" && c.JID.User == jid.User) {
			return a.list.DisplayName(c)
		}
	}
	if open := a.pane.Chat(); open.JID == jid {
		return a.list.DisplayName(open)
	}
	return jid.Display()
}

// openFinderResult jumps to the message a row names.
func (a *App) openFinderResult(it PickerItem) error {
	chat, id, ok := strings.Cut(it.Value, "\x00")
	if !ok {
		return fmt.Errorf("malformed result")
	}
	jid, err := domain.ParseJID(chat)
	if err != nil {
		return err
	}
	return a.openQuickfixItem(QFItem{Chat: jid, MessageID: id})
}
