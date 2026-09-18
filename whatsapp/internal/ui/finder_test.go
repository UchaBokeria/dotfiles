package ui

import (
	"strings"
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

func TestTheFinderSearchesEveryChat(t *testing.T) {
	a := newTestApp(t)
	a.store.setText("a@s.whatsapp.net", "M3", "the nuc arrived")
	a.store.setText("b@s.whatsapp.net", "M2", "nuc firmware update")

	if err := a.command(t, "find"); err != nil {
		t.Fatal(err)
	}
	if !a.picker.IsOpen() {
		t.Fatal("the finder did not open")
	}

	a.picker.SetQuery("nuc")
	var labels []string
	for i := 0; i < a.picker.Len(); i++ {
		a.picker.Move(i - a.picker.Index())
		it, _ := a.picker.Selected()
		labels = append(labels, it.Label)
	}
	joined := strings.Join(labels, "\n")
	if !strings.Contains(joined, "the nuc arrived") || !strings.Contains(joined, "nuc firmware update") {
		t.Errorf("the finder missed a chat:\n%s", joined)
	}
	if !strings.Contains(joined, "Ana") || !strings.Contains(joined, "Beka") {
		t.Errorf("results do not say which chat they are in:\n%s", joined)
	}
}

func TestTheFinderRequeriesOnEveryKeystroke(t *testing.T) {
	// A picker that filters a preloaded list cannot search a store of a
	// hundred thousand messages; this one asks the store again each time.
	a := newTestApp(t)
	a.store.setText("a@s.whatsapp.net", "M3", "needle here")

	if err := a.command(t, "find"); err != nil {
		t.Fatal(err)
	}
	before := a.picker.Len()
	a.picker.SetQuery("needle")
	if a.picker.Len() == 0 {
		t.Fatal("no results for a message that exists")
	}
	if a.picker.Len() >= before && before > 1 {
		t.Errorf("typing did not narrow the list: %d then %d", before, a.picker.Len())
	}
}

func TestTheFinderJumpsToTheMessage(t *testing.T) {
	a := newTestApp(t)
	a.store.setText("b@s.whatsapp.net", "M2", "over here")
	if err := a.command(t, "find"); err != nil {
		t.Fatal(err)
	}
	a.picker.SetQuery("over here")
	if a.picker.Len() == 0 {
		t.Fatal("no results")
	}
	if err := a.picker.Accept(); err != nil {
		t.Fatal(err)
	}
	if got := a.pane.Chat().JID.String(); got != "b@s.whatsapp.net" {
		t.Errorf("landed in %s", got)
	}
	if m, ok := a.pane.Selected(); !ok || m.ID != "M2" {
		t.Errorf("selected %q", m.ID)
	}
}

func TestFindScopesAreAllBoundAndNamed(t *testing.T) {
	a := newTestApp(t)
	for _, s := range findScopes {
		for _, name := range []string{"find." + s.name, "find.chat_" + s.name} {
			act, ok := a.reg.Lookup(name)
			if !ok {
				t.Errorf("%s is not registered", name)
				continue
			}
			if act.Summary == "" {
				t.Errorf("%s has no summary, so the popup cannot label it", name)
			}
		}
	}
}

func TestFindRejectsAnUnknownScope(t *testing.T) {
	a := newTestApp(t)
	err := a.command(t, "find nonsense")
	if err == nil {
		t.Fatal("an unknown scope was accepted")
	}
	if !strings.Contains(err.Error(), "messages") {
		t.Errorf("the error does not say what is allowed: %v", err)
	}
}

func TestTheProfilePageAddsTheChatUp(t *testing.T) {
	a := newTestApp(t)
	a.store.setText("a@s.whatsapp.net", "M1", "look at https://wacli.sh")
	a.store.setMedia("a@s.whatsapp.net", "M2", &domain.MediaRef{
		Type: "image", Filename: "beach.jpg", Length: 2048,
	})

	if err := a.command(t, "stats"); err != nil {
		t.Fatal(err)
	}
	view := a.overlay.View(a.styles, 80, 30)
	for _, want := range []string{"messages", "total", "attachments", "pictures", "links", "history"} {
		if !strings.Contains(view, want) {
			t.Errorf("the profile does not mention %q:\n%s", want, view)
		}
	}
}
