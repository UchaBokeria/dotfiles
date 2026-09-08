package config

import (
	"path/filepath"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"
)

// debounce is how long to wait after the last write before reloading. Editors
// save in several syscalls, and reloading between them reads a half-file.
const debounce = 150 * time.Millisecond

// Watcher reloads the configuration when its file changes.
type Watcher struct {
	fs     *fsnotify.Watcher
	done   chan struct{}
	closed sync.Once
}

// Watch calls onChange whenever path changes. The callback receives the
// reloaded configuration, any warnings, and any error; on error the caller is
// expected to keep the configuration it already has, because dropping to
// defaults on a typo would be worse than ignoring the edit.
//
// The parent directory is watched rather than the file, because editors that
// write by rename replace the inode and a file watch would go deaf.
func Watch(path string, onChange func(Config, []Warning, error)) (*Watcher, error) {
	fsw, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, err
	}
	dir := filepath.Dir(path)
	if err := fsw.Add(dir); err != nil {
		fsw.Close()
		return nil, err
	}

	w := &Watcher{fs: fsw, done: make(chan struct{})}
	go w.run(path, onChange)
	return w, nil
}

func (w *Watcher) run(path string, onChange func(Config, []Warning, error)) {
	var timer *time.Timer
	var timerC <-chan time.Time
	target := filepath.Clean(path)

	for {
		select {
		case <-w.done:
			if timer != nil {
				timer.Stop()
			}
			return

		case ev, ok := <-w.fs.Events:
			if !ok {
				return
			}
			if filepath.Clean(ev.Name) != target {
				continue
			}
			if ev.Op&(fsnotify.Write|fsnotify.Create|fsnotify.Rename) == 0 {
				continue
			}
			if timer != nil {
				timer.Stop()
			}
			timer = time.NewTimer(debounce)
			timerC = timer.C

		case <-timerC:
			timerC = nil
			cfg, warns, err := Load(path)
			onChange(cfg, warns, err)

		case err, ok := <-w.fs.Errors:
			if !ok {
				return
			}
			onChange(Config{}, nil, err)
		}
	}
}

// Close stops watching. It is safe to call more than once.
func (w *Watcher) Close() error {
	var err error
	w.closed.Do(func() {
		close(w.done)
		err = w.fs.Close()
	})
	return err
}
