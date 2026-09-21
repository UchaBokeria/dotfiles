package live

import (
	"sync"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// Merge fans two sources into one, so a webhook's normal path and a poll's
// slower one both reach the interface without it having to know there are
// two.
//
// A sync process wa adopted rather than started is not supervised: nothing
// here restarts it if it dies mid-session, and its own webhook goes quiet
// with it. Polling underneath it too, always, is what still notices a new
// message a few seconds later regardless of why the faster path stopped -
// the sync died, its process was killed by hand, a webhook request dropped
// on the floor - rather than only for the specific cause this once was.
func Merge(a, b Source) Source {
	m := &merged{
		ch:   make(chan domain.Event, 64),
		a:    a,
		b:    b,
		done: make(chan struct{}),
	}
	m.wg.Add(2)
	go m.pump(a)
	go m.pump(b)
	go func() {
		m.wg.Wait()
		close(m.ch)
	}()
	return m
}

type merged struct {
	ch      chan domain.Event
	dropped int64Counter
	a, b    Source
	done    chan struct{}
	wg      sync.WaitGroup
}

func (m *merged) pump(s Source) {
	defer m.wg.Done()
	for {
		select {
		case <-m.done:
			return
		case ev, ok := <-s.Events():
			if !ok {
				return
			}
			emit(m.ch, ev, &m.dropped)
		}
	}
}

func (m *merged) Events() <-chan domain.Event { return m.ch }
func (m *merged) Dropped() int64              { return m.dropped.get() + m.a.Dropped() + m.b.Dropped() }
func (m *merged) Describe() string            { return m.a.Describe() + " + " + m.b.Describe() }

func (m *merged) Close() error {
	close(m.done)
	errA := m.a.Close()
	errB := m.b.Close()
	if errA != nil {
		return errA
	}
	return errB
}
