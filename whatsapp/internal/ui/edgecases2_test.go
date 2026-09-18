package ui

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/action"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// --- marks meeting a world that changed -----------------------------------------

func TestMarksOnChatsThatLeftTheList(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<C-v><C-v>")
	// A reload that no longer contains a marked chat must not act on a ghost.
	a.store.mu.Lock()
	a.store.chats = a.store.chats[1:]
	a.store.mu.Unlock()
	if err := a.reloadList(); err != nil {
		t.Fatal(err)
	}
	got := a.markedChats()
	for _, c := range got {
		if c.JID.String() == "a@s.whatsapp.net" {
			t.Error("a chat that left the list is still acted on")
		}
	}
}

func TestMarkingInAnEmptyList(t *testing.T) {
	a := newTestApp(t)
	a.store.mu.Lock()
	a.store.chats = nil
	a.store.mu.Unlock()
	a.reloadList()
	a.feed(t, "<C-v>") // must not panic
	if a.chatMarks.len() != 0 {
		t.Error("an empty list produced a mark")
	}
	if err := a.reg.Run("chat.mark_read", action.Context{}); err == nil {
		t.Error("marking read with nothing selected reported success")
	}
}

func TestDeleteForEveryoneRefusesAMixedSelection(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	msgs := a.pane.Messages()
	if len(msgs) < 2 {
		t.Fatal("need two messages")
	}
	// One mine, one not.
	mixed := []domain.Message{msgs[0], msgs[1]}
	mixed[0].FromMe = true
	mixed[1].FromMe = false
	if err := a.deleteMessages(mixed, true); err == nil {
		t.Error("deleting someone else's message for everyone was allowed")
	}
	a.run(a.takeCmd())
	if a.called("messages revoke") {
		t.Error("a revoke ran for a selection that included someone else's message")
	}
}

func TestBulkDownloadWithNoAttachmentsSaysSo(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.pane.Move(-2)
	a.feed(t, "<C-v><C-v>")
	err := a.reg.Run("msg.download", action.Context{})
	if err == nil || !strings.Contains(err.Error(), "attachment") {
		t.Errorf("err = %v", err)
	}
}

// --- the finder on hostile input ------------------------------------------------

func TestFinderWithHostileQueries(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, "find"); err != nil {
		t.Fatal(err)
	}
	for _, q := range []string{`"`, `*`, `NEAR(`, `' OR 1=1 --`, strings.Repeat("x", 5000), "\x00", "გამარჯობა"} {
		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("query %q panicked: %v", q, r)
				}
			}()
			a.picker.SetQuery(q)
		}()
	}
	a.picker.SetQuery("")
	if err := a.picker.Accept(); err != nil && !strings.Contains(err.Error(), "result") {
		// An accept on whatever is left must either work or say why.
		t.Logf("accept on empty query: %v", err)
	}
}

func TestFindResultThatNoLongerExists(t *testing.T) {
	a := newTestApp(t)
	err := a.openFinderResult(PickerItem{Value: "a@s.whatsapp.net\x00NOPE"})
	if err != nil {
		t.Logf("reported: %v", err)
	}
	if !strings.Contains(a.status, "further back") && err == nil {
		t.Errorf("a missing message was landed on silently; status = %q", a.status)
	}
	if err := a.openFinderResult(PickerItem{Value: "garbage"}); err == nil {
		t.Error("a malformed result was accepted")
	}
}

// --- download cap misconfiguration ----------------------------------------------

func TestMaxDownloadConfiguredBelowWaclisOwnCap(t *testing.T) {
	a := newTestApp(t, func(d *Deps) {
		d.Cfg.Media.MaxDownload = config.Size(1024) // someone typed "1KB"
	})
	a.feed(t, "<Tab>")
	sel, _ := a.pane.Selected()
	a.pane.SetMediaForTest(sel.ID, &domain.MediaRef{Type: "document", Filename: "big.zip", Length: 4096})
	sel, _ = a.pane.Selected()
	err := a.downloadMedia(sel)
	if err == nil || !strings.Contains(err.Error(), "too large") {
		t.Errorf("err = %v", err)
	}
	if !strings.Contains(err.Error(), "wacli-big-media") {
		t.Error("the refusal does not say how to lift the cap")
	}
}

func TestAnAttachmentExactlyAtTheCapIsAllowed(t *testing.T) {
	a := newTestApp(t, func(d *Deps) {
		d.Cfg.Media.MaxDownload = config.Size(4096)
	})
	a.feed(t, "<Tab>")
	sel, _ := a.pane.Selected()
	a.pane.SetMediaForTest(sel.ID, &domain.MediaRef{Type: "document", Filename: "edge.zip", Length: 4096})
	sel, _ = a.pane.Selected()
	if err := a.downloadMedia(sel); err != nil && strings.Contains(err.Error(), "too large") {
		t.Errorf("a file exactly at the cap was refused: %v", err)
	}
}

// --- keys from the terminal ------------------------------------------------------

func TestUnknownTerminalKeysAreDropped(t *testing.T) {
	a := newTestApp(t)
	for _, m := range []tea.KeyMsg{
		{Type: tea.KeyF13},
		{Type: tea.KeyInsert},
		{Type: tea.KeyRunes, Runes: nil},
		{Type: tea.KeyCtrlAt},
	} {
		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("%v panicked: %v", m, r)
				}
			}()
			a.Update(m)
		}()
	}
}

func TestPastedTextNeverTriggersBindings(t *testing.T) {
	// A paste arrives as one batch of runes. In normal mode each rune is a
	// key, which is how vim behaves too; the guard that matters is that a
	// paste into the input box types rather than runs commands.
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>i")
	a.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("ZZ:q!<CR>dd"), Paste: true})
	if a.quitting {
		t.Fatal("pasted text quit the application")
	}
	if !strings.Contains(a.composer.Text(), "ZZ:q!") {
		t.Errorf("the paste did not land in the draft: %q", a.composer.Text())
	}
	if a.called("send text") {
		t.Error("a paste sent a message")
	}
}

// --- the root key list at a tiny terminal ----------------------------------------

func TestTheKeyListAtATinyTerminal(t *testing.T) {
	a := newTestApp(t)
	a.wkDelay = 0
	a.resize(30, 12)
	a.feed(t, "<Space>")
	a.View()
	a.feed(t, "<BS>")
	view := a.View()
	for i, line := range strings.Split(view, "\n") {
		if w := len([]rune(stripForTest(line))); w > 30 {
			t.Errorf("row %d is %d wide in a 30-column terminal", i, w)
		}
	}
	if got := strings.Count(view, "\n") + 1; got > 12 {
		t.Errorf("the frame is %d rows in a 12-row terminal", got)
	}
}
