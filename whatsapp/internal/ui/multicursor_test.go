package ui

import (
	"strings"
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
)

func bufStart() vim.Pos      { return vim.Pos{} }
func bufAt(l, c int) vim.Pos { return vim.Pos{Line: l, Col: c} }

// composerWith puts the app in the input box with a draft already typed.
func composerWith(t *testing.T, text string) *testApp {
	t.Helper()
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>")
	a.composer.Buffer().SetText(text)
	a.composer.Buffer().SetCursor(bufStart())
	a.setFocus(FocusComposer)
	return a
}

func TestBlockInsertPrefixesEveryLine(t *testing.T) {
	// The classic use of a column selection: put the same thing in front of
	// several lines.
	a := composerWith(t, "one\ntwo\nthree")

	a.feed(t, "<C-v>") // block from 0,0
	a.feed(t, "jj")    // down two lines
	a.feed(t, "I")     // insert down the left edge
	a.feed(t, "- ")    // typed at every cursor
	a.feed(t, "<Esc>")

	want := "- one\n- two\n- three"
	if got := a.composer.Text(); got != want {
		t.Errorf("draft =\n%q\nwant\n%q", got, want)
	}
}

func TestBlockAppendAddsToEveryLine(t *testing.T) {
	a := composerWith(t, "a\nb")
	a.feed(t, "<C-v>")
	a.feed(t, "j")
	a.feed(t, "A")
	a.feed(t, "!")
	a.feed(t, "<Esc>")

	if got := a.composer.Text(); got != "a!\nb!" {
		t.Errorf("draft = %q", got)
	}
}

func TestBlockDeleteCutsTheColumn(t *testing.T) {
	a := composerWith(t, "xxone\nxxtwo")
	a.feed(t, "<C-v>")
	a.feed(t, "lj") // one column right, one line down: a 2x2 block
	a.feed(t, "d")

	if got := a.composer.Text(); got != "one\ntwo" {
		t.Errorf("draft = %q", got)
	}
	if a.multiActive() {
		t.Error("the block outlived the edit")
	}
}

func TestMultiCursorChangesEveryOccurrence(t *testing.T) {
	a := composerWith(t, "nuc here and nuc there")

	a.feed(t, "<C-n>") // the word under the cursor
	a.feed(t, "<C-n>") // and the next one
	if got := len(a.multi.cursors); got != 2 {
		t.Fatalf("%d cursors, want 2", got)
	}
	a.feed(t, "c")
	a.feed(t, "box")
	a.feed(t, "<Esc>")

	if got := a.composer.Text(); got != "box here and box there" {
		t.Errorf("draft = %q", got)
	}
}

func TestMultiCursorTypesAtEveryCursor(t *testing.T) {
	a := composerWith(t, "cat cat")
	a.feed(t, "<C-n><C-n>")
	a.feed(t, "i")
	a.feed(t, "big ")
	a.feed(t, "<Esc>")

	if got := a.composer.Text(); got != "big cat big cat" {
		t.Errorf("draft = %q", got)
	}
}

func TestMultiCursorBackspaceAtEveryCursor(t *testing.T) {
	a := composerWith(t, "x cat x cat")
	a.composer.Buffer().SetCursor(bufAt(0, 2))
	a.feed(t, "<C-n><C-n>")
	a.feed(t, "i")
	a.feed(t, "<BS>")
	a.feed(t, "<Esc>")

	if got := a.composer.Text(); got != "xcat xcat" {
		t.Errorf("draft = %q", got)
	}
}

func TestEscapeLeavesTheMultiCursor(t *testing.T) {
	a := composerWith(t, "one one")
	a.feed(t, "<C-n>")
	if !a.multiActive() {
		t.Fatal("no cursor was added")
	}
	a.feed(t, "<Esc>")
	if a.multiActive() {
		t.Error("escape did not end it")
	}
}

func TestTheBlockKeysDoNotLeakIntoTheConversation(t *testing.T) {
	// <C-v> in the conversation marks a message; in the input box it starts a
	// block. The two must not be the same thing.
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.feed(t, "<C-v>")
	if a.multiActive() {
		t.Error("the conversation started a block selection")
	}
	if a.msgMarks.len() != 1 {
		t.Errorf("%d messages marked", a.msgMarks.len())
	}
}

func TestMultiCursorSaysHowManyThereAre(t *testing.T) {
	a := composerWith(t, "one one one")
	a.feed(t, "<C-n><C-n><C-n>")
	if !strings.Contains(a.status, "3 cursors") {
		t.Errorf("status = %q", a.status)
	}
}

func TestVerticalCursorsWriteDownAColumn(t *testing.T) {
	// vim-visual-multi's <C-Down>: a cursor on the line below, same column.
	a := composerWith(t, "one\ntwo\nthree")

	a.feed(t, "<C-Down>")
	a.feed(t, "<C-Down>")
	if got := len(a.multi.cursors); got != 3 {
		t.Fatalf("%d cursors, want 3", got)
	}
	a.feed(t, "i")
	a.feed(t, "> ")
	a.feed(t, "<Esc>")

	want := "> one\n> two\n> three"
	if got := a.composer.Text(); got != want {
		t.Errorf("draft =\n%q\nwant\n%q", got, want)
	}
}

func TestVerticalCursorsStopAtTheEnd(t *testing.T) {
	a := composerWith(t, "only one line")
	a.feed(t, "<C-Down>")
	if got := len(a.multi.cursors); got != 1 {
		t.Errorf("%d cursors on a one-line draft", got)
	}
	if !strings.Contains(a.status, "no line that way") {
		t.Errorf("status = %q", a.status)
	}
}

func TestVerticalCursorsClampToShortLines(t *testing.T) {
	a := composerWith(t, "a longer line\nshort")
	a.composer.Buffer().SetCursor(bufAt(0, 12))
	a.feed(t, "<C-Down>")
	if got := len(a.multi.cursors); got != 2 {
		t.Fatalf("%d cursors", got)
	}
	if got := a.multi.cursors[1]; got.Line != 1 || got.Col != 5 {
		t.Errorf("second cursor at %+v, want the end of the short line", got)
	}
}
