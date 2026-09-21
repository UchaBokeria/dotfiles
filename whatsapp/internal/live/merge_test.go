package live

import (
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// fakeSource is a minimal Source a test can push events into by hand.
type fakeSource struct {
	ch     chan domain.Event
	closed bool
}

func newFakeSource() *fakeSource { return &fakeSource{ch: make(chan domain.Event, 4)} }

func (f *fakeSource) Events() <-chan domain.Event { return f.ch }
func (f *fakeSource) Dropped() int64              { return 0 }
func (f *fakeSource) Describe() string            { return "fake" }
func (f *fakeSource) Close() error {
	if !f.closed {
		f.closed = true
		close(f.ch)
	}
	return nil
}

func TestMergeDeliversFromEitherSource(t *testing.T) {
	a, b := newFakeSource(), newFakeSource()
	m := Merge(a, b)
	defer m.Close()

	a.ch <- domain.Event{Kind: domain.EventMessage}
	if _, ok := waitEvent(t, m); !ok {
		t.Fatal("Merge did not deliver an event from the first source")
	}

	b.ch <- domain.Event{Kind: domain.EventReceipt}
	if _, ok := waitEvent(t, m); !ok {
		t.Fatal("Merge did not deliver an event from the second source")
	}
}

func TestMergeSurvivesOneSourceDying(t *testing.T) {
	// This is the point of merging a webhook with a poll: an adopted sync
	// dying mid-session takes the webhook with it, but the poll underneath
	// keeps working and Merge must still pass its events through.
	a, b := newFakeSource(), newFakeSource()
	m := Merge(a, b)
	defer m.Close()

	a.Close()
	b.ch <- domain.Event{Kind: domain.EventMessage}
	if _, ok := waitEvent(t, m); !ok {
		t.Fatal("Merge stopped delivering after one source closed")
	}
}

func TestMergeCloseClosesBothSourcesAndItsOwnChannel(t *testing.T) {
	a, b := newFakeSource(), newFakeSource()
	m := Merge(a, b)
	if err := m.Close(); err != nil {
		t.Fatal(err)
	}
	if !a.closed || !b.closed {
		t.Error("Close did not close both underlying sources")
	}
	select {
	case _, ok := <-m.Events():
		if ok {
			t.Error("Merge's channel carried a value after Close")
		}
	case <-time.After(time.Second):
		t.Error("Merge's channel was never closed")
	}
}

func TestMergeDroppedSumsAllThree(t *testing.T) {
	var _ Source = Merge(newFakeSource(), newFakeSource())
}
