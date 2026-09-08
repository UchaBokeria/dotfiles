package lock

import (
	"sync"
	"time"
)

// Idle re-locks the interface after a period without input.
type Idle struct {
	mu      sync.Mutex
	timeout time.Duration
	timer   *time.Timer
	onLock  func()
	stopped bool
}

// NewIdle starts an idle timer. A timeout of zero or less disables it, and
// Touch then costs nothing.
func NewIdle(timeout time.Duration, onLock func()) *Idle {
	i := &Idle{timeout: timeout, onLock: onLock}
	if timeout > 0 && onLock != nil {
		i.timer = time.AfterFunc(timeout, i.fire)
	}
	return i
}

func (i *Idle) fire() {
	i.mu.Lock()
	stopped := i.stopped
	cb := i.onLock
	i.mu.Unlock()
	if stopped || cb == nil {
		return
	}
	cb()
}

// Touch records activity, deferring the lock.
func (i *Idle) Touch() {
	i.mu.Lock()
	defer i.mu.Unlock()
	if i.stopped || i.timer == nil {
		return
	}
	i.timer.Reset(i.timeout)
}

// Stop disables the timer. It is safe to call more than once.
func (i *Idle) Stop() {
	i.mu.Lock()
	defer i.mu.Unlock()
	i.stopped = true
	if i.timer != nil {
		i.timer.Stop()
	}
}

// Enabled reports whether an idle lock is armed.
func (i *Idle) Enabled() bool {
	i.mu.Lock()
	defer i.mu.Unlock()
	return !i.stopped && i.timer != nil
}
