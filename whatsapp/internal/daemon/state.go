package daemon

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
	"time"
)

// State is what wa records about the sync process it started, so a second
// instance can attach to the same webhook rather than starting a second sync.
//
// It holds the webhook secret, so the file is written 0600 and lives in the
// state directory, never in the configuration that is committed to dotfiles.
type State struct {
	PID       int       `json:"pid"`
	Port      int       `json:"port"`
	Secret    string    `json:"secret"`
	Owned     bool      `json:"owned"`
	StartedAt time.Time `json:"started_at"`
}

// ReadState loads the state file.
func ReadState(path string) (State, error) {
	body, err := os.ReadFile(path)
	if err != nil {
		return State{}, err
	}
	var s State
	if err := json.Unmarshal(body, &s); err != nil {
		return State{}, fmt.Errorf("%s: %w", path, err)
	}
	return s, nil
}

// WriteState saves the state file, replacing it atomically.
func WriteState(path string, s State) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	body, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	tmp := path + ".tmp"
	// 0600 because this file carries the webhook HMAC secret.
	if err := os.WriteFile(tmp, body, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

// Alive reports whether the recorded process still exists. Signal 0 performs
// the permission and existence checks without delivering anything.
func (s State) Alive() bool {
	if s.PID <= 0 {
		return false
	}
	p, err := os.FindProcess(s.PID)
	if err != nil {
		return false
	}
	return p.Signal(syscall.Signal(0)) == nil
}
