package live

import (
	"context"
	"sync"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
)

// Poll watches the store for growth.
//
// It is the fallback for the case where a sync process is running that wa did
// not start: its webhook goes somewhere wa cannot hear, so the only way to
// notice a new message is to look. Reads are sub-millisecond, so a two-second
// tick is close to free.
type Poll struct {
	r        store.Reader
	every    time.Duration
	ch       chan domain.Event
	dropped  int64Counter
	cancel   context.CancelFunc
	closeOne sync.Once
	done     chan struct{}
}

// NewPoll starts polling.
func NewPoll(r store.Reader, every time.Duration, buffer int) *Poll {
	if every <= 0 {
		every = 2 * time.Second
	}
	if buffer <= 0 {
		buffer = 64
	}
	ctx, cancel := context.WithCancel(context.Background())
	p := &Poll{
		r:      r,
		every:  every,
		ch:     make(chan domain.Event, buffer),
		cancel: cancel,
		done:   make(chan struct{}),
	}
	go p.run(ctx)
	return p
}

func (p *Poll) run(ctx context.Context) {
	defer close(p.done)

	ticker := time.NewTicker(p.every)
	defer ticker.Stop()

	var lastRow int64
	var lastTS time.Time
	if st, err := p.r.Stats(ctx); err == nil {
		lastRow, lastTS = st.MaxRowID, st.LastMessageTS
	}

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}

		st, err := p.r.Stats(ctx)
		if err != nil {
			// A transient read failure is not worth reporting on every tick;
			// the next one will pick the change up.
			continue
		}
		if st.MaxRowID == lastRow && !st.LastMessageTS.After(lastTS) {
			continue
		}
		lastRow, lastTS = st.MaxRowID, st.LastMessageTS

		// No chat is identified: polling only knows that something arrived,
		// so the interface refreshes what it is showing.
		emit(p.ch, domain.Event{Kind: domain.EventMessage, At: now()}, &p.dropped)
	}
}

func (p *Poll) Events() <-chan domain.Event { return p.ch }
func (p *Poll) Dropped() int64              { return p.dropped.get() }
func (p *Poll) Describe() string            { return "polling" }

func (p *Poll) Close() error {
	p.closeOne.Do(func() {
		p.cancel()
		<-p.done
	})
	return nil
}
