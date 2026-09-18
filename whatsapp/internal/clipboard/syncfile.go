package clipboard

import (
	"os"
	"sync"
)

// SyncFile is the terminal, shared between the renderer and anything else that
// writes escape sequences to it.
//
// Two writers and no lock is how a copy over ssh ends up inside a frame. The
// alternative wa used before - handing the sequence to the renderer to emit
// with the next frame - loses copies instead: Bubble Tea skips a frame that is
// byte for byte the one already on screen, so copying the same message twice
// wrote the sequence once. One serialised writer costs a mutex and neither
// mistake is possible.
//
// It embeds *os.File rather than wrapping an io.Writer because Bubble Tea asks
// its output for a file descriptor before it will treat it as a terminal.
type SyncFile struct {
	*os.File
	mu sync.Mutex
}

// NewSyncFile wraps a terminal.
func NewSyncFile(f *os.File) *SyncFile { return &SyncFile{File: f} }

// Write is atomic with respect to every other write through this file.
func (s *SyncFile) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.File.Write(p)
}
