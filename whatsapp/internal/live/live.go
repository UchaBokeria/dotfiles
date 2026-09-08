// Package live delivers updates from the running sync process.
//
// An event is a hint that a chat changed, never the data itself. The interface
// re-reads the authoritative rows from the store when one arrives, which is
// what makes the bounded event channel safe: dropping an event under burst
// costs latency and never correctness.
package live

import (
	"time"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
)

// Source produces live updates.
type Source interface {
	// Events yields updates. The channel is closed by Close.
	Events() <-chan domain.Event
	// Dropped counts events discarded because the consumer fell behind.
	Dropped() int64
	// Describe is a short phrase for the status line.
	Describe() string
	Close() error
}

// nilSource is used when nothing can deliver updates.
type nilSource struct {
	ch chan domain.Event
}

// None is a source that never emits. It exists so the interface never has to
// branch on a nil Source.
func None() Source { return &nilSource{ch: make(chan domain.Event)} }

func (n *nilSource) Events() <-chan domain.Event { return n.ch }
func (n *nilSource) Dropped() int64              { return 0 }
func (n *nilSource) Describe() string            { return "no live updates" }
func (n *nilSource) Close() error {
	close(n.ch)
	return nil
}

// emit puts an event on the channel without ever blocking the producer.
// When the buffer is full the oldest event is discarded: the newest state of
// the world is what the interface will read anyway.
func emit(ch chan domain.Event, ev domain.Event, dropped *int64Counter) {
	select {
	case ch <- ev:
		return
	default:
	}
	select {
	case <-ch:
		dropped.add(1)
	default:
	}
	select {
	case ch <- ev:
	default:
		dropped.add(1)
	}
}

func now() time.Time { return time.Now() }
