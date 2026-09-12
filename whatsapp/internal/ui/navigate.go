package ui

import (
	"context"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// navigate moves the cursor in whichever pane has focus.
func (a *App) navigate(delta int) {
	switch a.focus {
	case FocusList:
		a.list.Move(delta)
		a.followSelection()
	default:
		a.pane.Move(delta)
	}
}

func (a *App) navTop() {
	switch a.focus {
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
	case FocusList:
		a.list.Bottom()
		a.followSelection()
	default:
		a.pane.Bottom()
	}
}

func (a *App) navHalfPage(dir, count int) {
	switch a.focus {
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

	if err := a.pane.Open(ctx, c); err != nil {
		a.setError(err.Error())
		return
	}
	a.composer.SwitchDraft(c.JID)
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
