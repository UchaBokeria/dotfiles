package ui

import (
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
)

func TestExternalReloadMsgRestylesAndKeepsListening(t *testing.T) {
	ch := make(chan struct{}, 1)
	calls := 0
	a := newTestApp(t, func(d *Deps) {
		d.ReloadWatch = ch
		d.Restyle = func(config.Config) theme.Styles {
			calls++
			return plainStyles(t)
		}
	})

	if cmd := a.waitForReloadWatch(); cmd == nil {
		t.Fatal("waitForReloadWatch returned nil with a channel set")
	}

	// NewApp's own construction already restyled once; only the delta from
	// here on is what externalReloadMsg is being credited with.
	before := calls
	a.Update(externalReloadMsg{})
	if calls != before+1 {
		t.Fatalf("externalReloadMsg called Restyle %d more time(s), want 1", calls-before)
	}
}

func TestNoReloadWatchMeansNoCommand(t *testing.T) {
	a := newTestApp(t)
	if cmd := a.waitForReloadWatch(); cmd != nil {
		t.Error("waitForReloadWatch returned a command with no ReloadWatch configured")
	}
}
