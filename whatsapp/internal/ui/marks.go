package ui

import (
	"fmt"
	"sort"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// Multi-select.
//
// WhatsApp long-presses a message and then taps more of them; here the same
// idea is a set of marks, one per section, toggled with <C-v>. Every action
// that can sensibly work on many - mark read, archive, download, delete,
// forward, copy - looks at the marks first and falls back to what is under the
// cursor when there are none, so nothing has to be learned twice.

// markSet is the marked items of one section, keyed by id.
type markSet struct {
	ids map[string]bool
	// order remembers when each was marked, so acting on a selection happens
	// in the order it was made rather than in map order.
	order []string
}

func (m *markSet) toggle(id string) bool {
	if id == "" {
		return false
	}
	if m.ids == nil {
		m.ids = map[string]bool{}
	}
	if m.ids[id] {
		delete(m.ids, id)
		for i, v := range m.order {
			if v == id {
				m.order = append(m.order[:i], m.order[i+1:]...)
				break
			}
		}
		return false
	}
	m.ids[id] = true
	m.order = append(m.order, id)
	return true
}

func (m *markSet) has(id string) bool { return m.ids[id] }
func (m *markSet) len() int           { return len(m.ids) }
func (m *markSet) clear() {
	m.ids = nil
	m.order = nil
}

// list is the marked ids, oldest mark first.
func (m *markSet) list() []string {
	out := make([]string, 0, len(m.order))
	for _, id := range m.order {
		if m.ids[id] {
			out = append(out, id)
		}
	}
	return out
}

// toggleMark marks whatever the cursor is on, in whichever section has focus.
func (a *App) toggleMark() error {
	switch a.focus {
	case FocusList:
		c, ok := a.list.Selected()
		if !ok {
			return fmt.Errorf("no chat is selected")
		}
		on := a.chatMarks.toggle(c.JID.String())
		a.list.SetMarks(a.chatMarks.ids)
		a.setStatus(markStatus(on, c.DisplayName(), a.chatMarks.len(), "chat"))
		// Moving on afterwards is what makes marking a run of chats one key
		// per chat rather than two.
		a.list.Move(1)
		a.followSelection()
	case FocusChat:
		m, ok := a.pane.Selected()
		if !ok {
			return fmt.Errorf("no message is selected")
		}
		on := a.msgMarks.toggle(m.ID)
		a.pane.SetMarks(a.msgMarks.ids)
		a.setStatus(markStatus(on, render1line(m.Body(), 30), a.msgMarks.len(), "message"))
		a.pane.Move(1)
	default:
		// In the input box the same key means what it means in vim: a column
		// selection over the draft.
		return a.startBlock()
	}
	return nil
}

func markStatus(on bool, what string, n int, kind string) string {
	verb := "unmarked"
	if on {
		verb = "marked"
	}
	return fmt.Sprintf("%s %s · %s selected", verb, what, plural(n, kind, kind+"s"))
}

// clearMarks drops every mark in every section, which is what Esc does.
func (a *App) clearMarks() {
	a.chatMarks.clear()
	a.msgMarks.clear()
	a.list.SetMarks(nil)
	a.pane.SetMarks(nil)
}

// markedChats is what a chat action should act on: the marks if there are any,
// otherwise whatever is under the cursor.
func (a *App) markedChats() []domain.Chat {
	if a.chatMarks.len() == 0 {
		if c, ok := a.targetChat(); ok {
			return []domain.Chat{c}
		}
		return nil
	}
	byJID := map[string]domain.Chat{}
	for _, c := range a.list.All() {
		byJID[c.JID.String()] = c
	}
	out := make([]domain.Chat, 0, a.chatMarks.len())
	for _, id := range a.chatMarks.list() {
		if c, ok := byJID[id]; ok {
			out = append(out, c)
		}
	}
	return out
}

// markedMessages is the same rule for messages.
func (a *App) markedMessages() []domain.Message {
	if a.msgMarks.len() == 0 {
		if m, ok := a.pane.Selected(); ok {
			return []domain.Message{m}
		}
		return nil
	}
	byID := map[string]domain.Message{}
	for _, m := range a.pane.Messages() {
		byID[m.ID] = m
	}
	out := make([]domain.Message, 0, a.msgMarks.len())
	for _, id := range a.msgMarks.list() {
		if m, ok := byID[id]; ok {
			out = append(out, m)
		}
	}
	// In the order they were sent, not the order they were clicked: a copy of
	// six messages out of sequence is not a copy of the conversation.
	sort.SliceStable(out, func(i, j int) bool { return out[i].TS.Before(out[j].TS) })
	return out
}
