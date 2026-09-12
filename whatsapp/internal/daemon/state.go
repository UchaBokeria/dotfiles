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
	// PID is the sync process.
	PID int `json:"pid"`
	// OwnerPID is the wa that started it. The two are needed separately: an
	// orphaned sync whose wa is gone may be taken over by the next instance,
	// while a sync belonging to a wa that is still open must be left alone, or
	// two clients spend their time restarting each other's sync process.
	OwnerPID  int       `json:"owner_pid"`
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

// Alive reports whether the recorded sync process still exists. Signal 0
// performs the permission and existence checks without delivering anything.
func (s State) Alive() bool { return pidAlive(s.PID) }

// OwnerAlive reports whether the wa that started the sync is still running.
// An older state file has no owner recorded; treating that as "gone" is the
// safe reading, since the alternative is refusing to work forever.
func (s State) OwnerAlive() bool {
	return s.OwnerPID > 0 && pidAlive(s.OwnerPID)
}

// Orphaned reports a sync process still running with no wa behind it - what a
// closed terminal or a killed client leaves behind.
func (s State) Orphaned() bool { return s.Alive() && !s.OwnerAlive() }

func pidAlive(pid int) bool {
	if pid <= 0 {
		return false
	}
	p, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	return p.Signal(syscall.Signal(0)) == nil
}
