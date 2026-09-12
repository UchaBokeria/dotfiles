package ui

import (
	"strings"
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
)

func TestHelpOpensAndCloses(t *testing.T) {
	// The first version of the help page could not be closed at all: it went
	// through the modal engine, where Esc is bound to clearing the search.
	a := newTestApp(t)
	a.feed(t, "<Space>?")
	if !a.overlay.IsOpen() {
		t.Fatal("leader-? did not open the help page")
	}
	a.feed(t, "<Esc>")
	if a.overlay.IsOpen() {
		t.Fatal("Esc did not close the help page")
	}
}

func TestEveryEscapeKeyClosesTheOverlay(t *testing.T) {
	for _, k := range []keys.Key{
		{Special: keys.Esc},
		{Special: keys.CR},
		{Rune: 'q'},
		{Mods: keys.Ctrl, Rune: 'c'},
	} {
		a := newTestApp(t)
		a.RunCommand(":help")
		if !a.overlay.IsOpen() {
			t.Fatal("the help page did not open")
		}
		a.HandleKey(k)
		if a.overlay.IsOpen() {
			t.Errorf("%s did not close the overlay", k)
		}
	}
}

func TestOverlayScrolls(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 20)
	a.RunCommand(":help")

	if a.overlay.Offset() != 0 {
		t.Fatalf("the page opened at offset %d", a.overlay.Offset())
	}
	a.HandleKey(keys.Key{Rune: 'j'})
	if a.overlay.Offset() != 1 {
		t.Errorf("j scrolled to %d, want 1", a.overlay.Offset())
	}
	a.HandleKey(keys.Key{Mods: keys.Ctrl, Rune: 'd'})
	if a.overlay.Offset() <= 1 {
		t.Errorf("ctrl-d did not page down: offset %d", a.overlay.Offset())
	}
	a.HandleKey(keys.Key{Rune: 'g'})
	if a.overlay.Offset() != 0 {
		t.Errorf("g did not return to the top: offset %d", a.overlay.Offset())
	}
	a.HandleKey(keys.Key{Rune: 'G'})
	if a.overlay.Offset() == 0 {
		t.Error("G did not jump to the end")
	}
}

func TestOverlayScrollingStopsAtTheEnds(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 20)
	a.RunCommand(":help")

	for i := 0; i < 500; i++ {
		a.HandleKey(keys.Key{Rune: 'j'})
	}
	first := a.overlay.Offset()
	a.HandleKey(keys.Key{Rune: 'j'})
	if a.overlay.Offset() != first {
		t.Error("scrolling past the end kept going")
	}
	for i := 0; i < 500; i++ {
		a.HandleKey(keys.Key{Rune: 'k'})
	}
	if a.overlay.Offset() != 0 {
		t.Errorf("scrolling past the top reached %d", a.overlay.Offset())
	}
}

func TestOverlayTellsYouHowToLeave(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 20)
	a.RunCommand(":help")

	view := a.View()
	if !strings.Contains(view, "q or Esc to close") {
		t.Errorf("the page does not say how to close it:\n%s", view)
	}
}

func TestHelpListsBindingsAndCommands(t *testing.T) {
	a := newTestApp(t)
	a.RunCommand(":help")
	body := strings.Join(a.overlay.Lines(), "\n")

	for _, want := range []string{"NORMAL", "nav.down", "COMMANDS", ":grep", "MOUSE"} {
		if !strings.Contains(body, want) {
			t.Errorf("the help page is missing %q", want)
		}
	}
}

func TestLogOpensInTheOverlay(t *testing.T) {
	a := newTestApp(t)
	a.setStatus("something happened")
	a.RunCommand(":log")

	if !a.overlay.IsOpen() {
		t.Fatal(":log did not open the page")
	}
	if !strings.Contains(strings.Join(a.overlay.Lines(), "\n"), "something happened") {
		t.Error("the log page does not show the entry")
	}
}

func TestOverlayWheelScrolls(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 20)
	a.RunCommand(":help")
	a.wheelAt(10, 10, false)
	if a.overlay.Offset() == 0 {
		t.Error("the wheel did not scroll the page")
	}
}

func TestKeysDoNotLeakThroughTheOverlay(t *testing.T) {
	// While the page is up, a key must not also act on the panes underneath.
	a := newTestApp(t)
	a.RunCommand(":help")
	before := a.list.Index()

	a.HandleKey(keys.Key{Rune: 'j'})
	if a.list.Index() != before {
		t.Error("j moved the chat list while the help page was open")
	}
}
