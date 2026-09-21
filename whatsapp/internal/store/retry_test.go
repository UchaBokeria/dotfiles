package store

import (
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

func TestARetryStubIsDroppedWhenTheRealMessageFollows(t *testing.T) {
	t0 := time.Date(2026, 9, 21, 12, 28, 53, 0, time.UTC)
	stub := domain.Message{ID: "s", TS: t0, Unsupported: true}
	real := domain.Message{ID: "r", TS: t0.Add(17 * time.Second), Text: "hi"}
	got := dropRetryPlaceholders([]domain.Message{real, stub}) // newest first, as the store returns
	if len(got) != 1 || got[0].ID != "r" {
		t.Fatalf("got %+v, want only the real message", got)
	}
}

func TestAStubWithNoRetryIsKept(t *testing.T) {
	t0 := time.Now()
	stub := domain.Message{ID: "s", TS: t0, Unsupported: true}
	other := domain.Message{ID: "o", TS: t0.Add(time.Second), FromMe: true, Text: "mine"}
	late := domain.Message{ID: "l", TS: t0.Add(5 * time.Minute), Text: "later"}
	if got := dropRetryPlaceholders([]domain.Message{stub, other, late}); len(got) != 3 {
		t.Fatalf("a genuinely undecodable message was dropped: %+v", got)
	}
}
