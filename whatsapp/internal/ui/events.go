package ui

import (
	"context"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// applyEvent reacts to a live update.
//
// The event is a hint, never the data. Whatever it names is re-read from the
// store, which is what makes it safe for the webhook to drop events under
// burst: a lost hint costs latency, not correctness.
func (a *App) applyEvent(ev domain.Event) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	switch ev.Kind {
	case domain.EventReceipt:
		// A receipt without a message id tells us nothing about which bubble
		// to tick, so refresh the open chat instead.
		state := ev.Receipt
		if state == 0 {
			state = domain.Delivered
		}
		// The webhook batches ids; a poll or a test carries one. Either way
		// the same loop applies them.
		ids := ev.MessageIDs
		if len(ids) == 0 && ev.MessageID != "" {
			ids = []string{ev.MessageID}
		}
		touched := false
		for _, id := range ids {
			if a.receipts.Record(id, state, ev.At.Unix()) {
				touched = true
			}
			if a.pane.ApplyReceipt(id, state) {
				touched = true
			}
		}
		if touched {
			// The file is small and a tick that survives a restart is the
			// whole point of keeping it.
			if err := a.receipts.Save(); err != nil {
				a.log.Warnf("saving receipts: %v", err)
			}
			return
		}
		if len(ids) > 0 {
			return
		}
	case domain.EventChatPresence:
		// Typing indicators are sub-project 3; nothing to do yet.
		return
	}

	if err := a.list.Invalidate(ctx, ev.Chat); err != nil {
		a.log.Warnf("refreshing the chat list: %v", err)
	}
	// Only re-read the conversation when the event concerns the one on screen.
	open := a.pane.Chat().JID
	if ev.Chat.IsZero() || (!open.IsZero() && ev.Chat == open) {
		if err := a.pane.Refresh(ctx); err != nil {
			a.log.Warnf("refreshing the conversation: %v", err)
		}
	}
}

// applyReload takes the result of a configuration hot reload.
//
// A broken file keeps the configuration already in effect. Dropping to
// defaults on a typo would rearrange the interface under someone who is mid-edit.
func (a *App) applyReload(m reloadedMsg) {
	if m.err != nil {
		a.setError("config: " + m.err.Error())
		return
	}
	for _, w := range m.warns {
		a.log.Warnf("config: %v", w)
	}
	if err := a.applyConfig(m.cfg); err != nil {
		a.setError("config: " + err.Error())
		return
	}
	a.setStatus("config reloaded")
}

// reload re-reads the configuration files.
func (a *App) reload() {
	cfg, warns, err := config.Load(a.deps.ConfigPath, a.deps.OverridesPath)
	a.applyReload(reloadedMsg{cfg: cfg, warns: warns, err: err})
}
