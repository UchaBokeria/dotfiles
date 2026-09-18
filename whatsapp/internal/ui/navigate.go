package ui

import (
	"context"
	"fmt"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
)

// navigate moves the cursor in whichever pane has focus.
func (a *App) navigate(delta int) {
	switch a.focus {
	case FocusList:
		a.list.Move(delta)
		a.followSelection()
	case FocusComposer:
		// The keys belong to whatever has focus. Sending j and k to the
		// conversation while the cursor is sitting in a half-written message
		// is the one thing that makes the input box feel like it is not
		// really focused.
		name := "down"
		if delta < 0 {
			name = "up"
			delta = -delta
		}
		a.draftMotion(name, delta)
	default:
		a.pane.Move(delta)
	}
}

// draftMotion moves the cursor inside the draft.
func (a *App) draftMotion(name string, count int) {
	buf, _ := a.activeBuffer()
	if buf == nil {
		return
	}
	if m := vim.Move(buf, name, count, 0); m.Valid {
		buf.SetCursor(m.To)
	}
}

func (a *App) navTop() {
	switch a.focus {
	case FocusComposer:
		a.draftMotion("buffer_start", 1)
		return
	case FocusList:
		a.list.Top()
		a.followSelection()
	default:
		a.pane.Top()
		a.maybeLoadOlder()
	}
}

func (a *App) navBottom() {
	switch a.focus {
	case FocusComposer:
		a.draftMotion("buffer_end", 1)
		return
	case FocusList:
		a.list.Bottom()
		a.followSelection()
	default:
		a.pane.Bottom()
	}
}

func (a *App) navHalfPage(dir, count int) {
	switch a.focus {
	case FocusComposer:
		name := "down"
		if dir < 0 {
			name = "up"
		}
		a.draftMotion(name, maxInt(1, count)*5)
		return
	case FocusList:
		for i := 0; i < count; i++ {
			a.list.HalfPage(dir)
		}
		a.followSelection()
	default:
		for i := 0; i < count; i++ {
			a.pane.HalfPage(dir)
		}
		a.maybeLoadOlder()
	}
}

func (a *App) navPage(dir, count int) {
	switch a.focus {
	case FocusComposer:
		name := "down"
		if dir < 0 {
			name = "up"
		}
		a.draftMotion(name, maxInt(1, count)*10)
		return
	case FocusList:
		for i := 0; i < count; i++ {
			a.list.Page(dir)
		}
		a.followSelection()
	default:
		for i := 0; i < count; i++ {
			a.pane.Page(dir)
		}
		a.maybeLoadOlder()
	}
}

// followSelection opens whatever the list cursor moved onto.
//
// Opening on movement rather than on Enter is what makes j and k feel like
// reading rather than like navigating a menu.
func (a *App) followSelection() {
	c, ok := a.list.Selected()
	if !ok || c.JID == a.pane.Chat().JID {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	a.rememberAlternate()
	if err := a.pane.Open(ctx, c); err != nil {
		a.setError(err.Error())
		return
	}
	a.composer.SwitchDraft(c.JID)
}

// rememberAlternate notes the chat being left, so <C-^> can go back to it.
//
// It is vim's alternate file: the one key that means "the other one", which in
// a chat client is the conversation you keep flicking back to while a third
// one keeps interrupting.
func (a *App) rememberAlternate() {
	if cur := a.pane.Chat().JID; !cur.IsZero() {
		a.altChat = cur
	}
}

// alternateChat swaps back to the chat left last.
func (a *App) alternateChat() error {
	if a.altChat.IsZero() {
		return fmt.Errorf("no other chat yet")
	}
	if a.altChat == a.pane.Chat().JID {
		return fmt.Errorf("already in the last chat")
	}
	return a.openChat(a.altChat)
}

// maybeLoadOlder fetches another page when the reader has reached the top of
// what is loaded.
func (a *App) maybeLoadOlder() {
	if !a.pane.AtTop() || a.pane.Exhausted() {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if _, err := a.pane.LoadOlder(ctx); err != nil {
		a.log.Warnf("loading older messages: %v", err)
	}
}

// openChat switches to a conversation, recording where we came from so ctrl-o
// can come back.
func (a *App) openChat(jid domain.JID) error {
	a.rememberAlternate()
	if cur := a.pane.Chat().JID; !cur.IsZero() {
		id := ""
		if m, ok := a.pane.Selected(); ok {
			id = m.ID
		}
		a.jumps.Push(cur, id)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	c, err := a.deps.Store.Chat(ctx, jid)
	if err != nil {
		return err
	}
	if !a.list.Select(jid) {
		// The chat is filtered out of the current view; widen rather than
		// silently doing nothing.
		a.list.SetFilter("all")
		a.list.SetSearch("")
		a.list.Select(jid)
	}
	if err := a.pane.Open(ctx, c); err != nil {
		return err
	}
	a.composer.SwitchDraft(c.JID)
	a.setFocus(FocusChat)
	return nil
}

// jumpTo moves to a remembered position.
func (a *App) jumpTo(j Jump) {
	if err := a.openChat(j.Chat); err != nil {
		a.setError(err.Error())
		return
	}
	if j.MessageID == "" {
		return
	}
	for i, m := range a.pane.Messages() {
		if m.ID == j.MessageID {
			a.pane.Move(i - a.pane.Index())
			return
		}
	}
}

// parseJID is a thin wrapper so commands.go does not import domain directly
// for a single call.
func parseJID(s string) (domain.JID, error) { return domain.ParseJID(s) }
