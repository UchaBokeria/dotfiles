package ui

import (
	"strings"
	"testing"
)

func TestThePasswordCanBeSetFromInsideWa(t *testing.T) {
	// Leaving wa to run `wa lock set` in a shell is exactly what somebody who
	// has just been told "no password is set" cannot do.
	a := newTestApp(t)
	if a.lockScreen.HasPassword() {
		t.Fatal("the test app starts with a password")
	}

	if err := a.RunCommand(":lock set"); err != nil {
		t.Fatal(err)
	}
	if !a.lockScreen.Locked() || !a.lockScreen.Setting() {
		t.Fatal("the screen is not asking for a password")
	}

	a.feed(t, "hunter2<CR>")
	if !a.lockScreen.Setting() {
		t.Fatal("one entry was enough; it should ask again")
	}
	a.feed(t, "hunter2<CR>")

	if a.lockScreen.Locked() {
		t.Error("setting the password left the screen up")
	}
	if !a.lockScreen.HasPassword() {
		t.Fatal("no password was written")
	}

	// And now the lock works.
	if err := a.RunCommand(":lock"); err != nil {
		t.Fatal(err)
	}
	if !a.lockScreen.Locked() {
		t.Fatal("the screen did not lock")
	}
	a.feed(t, "wrong<CR>")
	if !a.lockScreen.Locked() {
		t.Error("a wrong password opened it")
	}
	a.feed(t, "hunter2<CR>")
	if a.lockScreen.Locked() {
		t.Error("the right password did not open it")
	}
}

func TestMismatchedPasswordsStartAgain(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":lock set"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "one<CR>")
	a.feed(t, "two<CR>")
	if !a.lockScreen.Setting() {
		t.Fatal("a mismatch was accepted")
	}
	if a.lockScreen.HasPassword() {
		t.Error("a password was written anyway")
	}
	if !strings.Contains(a.lockScreen.View(a.styles, 60, 20), "do not match") {
		t.Error("the screen does not say what went wrong")
	}
}

func TestChoosingAPasswordCanBeAbandoned(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":lock set"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "<Esc>")
	if a.lockScreen.Locked() || a.lockScreen.Setting() {
		t.Error("escape did not abandon it")
	}
}

func TestTheLockScreenMoves(t *testing.T) {
	// A locked terminal that is perfectly still cannot be told from a hung
	// one.
	a := newTestApp(t)
	if err := a.RunCommand(":lock set"); err != nil {
		t.Fatal(err)
	}
	first := a.lockScreen.View(a.styles, 60, 20)
	for i := 0; i < 4; i++ {
		a.lockScreen.Tick()
	}
	if a.lockScreen.View(a.styles, 60, 20) == first {
		t.Error("the lock screen is a still image")
	}
}

func TestTheLockScreenShowsNothingOfTheConversation(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":lock set"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "hunter2<CR>hunter2<CR>")
	if err := a.RunCommand(":lock"); err != nil {
		t.Fatal(err)
	}
	view := a.View()
	for _, secret := range []string{"Ana", "Beka", "message 1"} {
		if strings.Contains(view, secret) {
			t.Errorf("the lock screen leaks %q", secret)
		}
	}
}

func TestClearingThePassword(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":lock set"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "hunter2<CR>hunter2<CR>")
	if err := a.RunCommand(":lock clear"); err != nil {
		t.Fatal(err)
	}
	if a.lockScreen.HasPassword() {
		t.Error("the password survived")
	}
	if err := a.RunCommand(":lock"); err == nil {
		t.Error("locking with no password set would be a door with no key")
	}
}
