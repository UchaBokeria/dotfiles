package ui

import (
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
)

// These go through the terminal's side of the wall: a tea.KeyMsg, the way a
// real keypress arrives, rather than a keys.Key fed straight in. Every other
// key test skips this layer, which is how <C-Down> and alt+enter broke without
// a single test noticing.
func TestTerminalKeysTranslate(t *testing.T) {
	cases := []struct {
		name string
		msg  tea.KeyMsg
		want string
	}{
		{"alt+enter is the newline, not send", tea.KeyMsg{Type: tea.KeyEnter, Alt: true}, "<M-CR>"},
		{"plain enter", tea.KeyMsg{Type: tea.KeyEnter}, "<CR>"},
		{"ctrl+down adds a cursor", tea.KeyMsg{Type: tea.KeyCtrlDown}, "<C-Down>"},
		{"ctrl+up", tea.KeyMsg{Type: tea.KeyCtrlUp}, "<C-Up>"},
		{"shift+tab", tea.KeyMsg{Type: tea.KeyShiftTab}, "<S-Tab>"},
		{"alt+backspace deletes a word", tea.KeyMsg{Type: tea.KeyBackspace, Alt: true}, "<M-BS>"},
		{"ctrl+v", tea.KeyMsg{Type: tea.KeyCtrlV}, "<C-v>"},
		{"ctrl+caret", tea.KeyMsg{Type: tea.KeyCtrlCaret}, "<C-^>"},
		{"space", tea.KeyMsg{Type: tea.KeySpace}, "<Space>"},
		{"escape", tea.KeyMsg{Type: tea.KeyEscape}, "<Esc>"},
		{"ctrl+home", tea.KeyMsg{Type: tea.KeyCtrlHome}, "<C-Home>"},
		{"page down", tea.KeyMsg{Type: tea.KeyPgDown}, "<PageDown>"},
	}
	for _, c := range cases {
		got := translateKeys(c.msg)
		if len(got) != 1 {
			t.Errorf("%s: %d keys", c.name, len(got))
			continue
		}
		want := keys.MustParse(c.want)[0]
		if got[0] != want {
			t.Errorf("%s: got %s, want %s", c.name, got[0], want)
		}
	}
}

func TestAltEnterInTheInputBoxDoesNotSend(t *testing.T) {
	// The one that mattered: alt+enter losing its alt sent a draft that was
	// meant to get a second line.
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>")
	a.feed(t, "ifirst")
	a.Update(tea.KeyMsg{Type: tea.KeyEnter, Alt: true})
	a.feed(t, "second")

	if got := a.composer.Text(); got != "first\nsecond" {
		t.Errorf("draft = %q, want two lines", got)
	}
	if a.called("send text") {
		t.Error("alt+enter sent the message")
	}
}

func TestControlDownFromTheTerminalAddsACursor(t *testing.T) {
	a := composerWith(t, "one\ntwo")
	a.Update(tea.KeyMsg{Type: tea.KeyCtrlDown})
	if got := len(a.multi.cursors); got != 2 {
		t.Errorf("%d cursors after a real ctrl+down, want 2", got)
	}
}
