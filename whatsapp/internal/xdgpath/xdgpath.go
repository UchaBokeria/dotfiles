// Package xdgpath resolves wa's files.
//
// Configuration and state are deliberately separate. config.toml is symlinked
// out of the dotfiles repository and belongs under XDG_CONFIG_HOME; the lock
// credential, the sync state file and the :set! overrides are machine-local
// and belong under XDG_STATE_HOME, where they will never be committed.
package xdgpath

import (
	"os"
	"path/filepath"
)

const app = "wa"

// ConfigDir is ~/.config/wa.
func ConfigDir() string {
	if v := os.Getenv("XDG_CONFIG_HOME"); v != "" {
		return filepath.Join(v, app)
	}
	return filepath.Join(home(), ".config", app)
}

// StateDir is ~/.local/state/wa.
func StateDir() string {
	if v := os.Getenv("XDG_STATE_HOME"); v != "" {
		return filepath.Join(v, app)
	}
	return filepath.Join(home(), ".local", "state", app)
}

// CacheDir is ~/.cache/wa.
func CacheDir() string {
	if v := os.Getenv("XDG_CACHE_HOME"); v != "" {
		return filepath.Join(v, app)
	}
	return filepath.Join(home(), ".cache", app)
}

// Config is the main configuration file.
func Config() string { return filepath.Join(ConfigDir(), "config.toml") }

// Overrides is where :set! writes.
func Overrides() string { return filepath.Join(ConfigDir(), "overrides.toml") }

// Lock is the password credential.
func Lock() string { return filepath.Join(StateDir(), "lock.json") }

// Daemon is the sync process's state file.
func Daemon() string { return filepath.Join(StateDir(), "daemon.json") }

// Quotes is wa's record of what its own sends replied to. wacli sends the
// quote but does not store it, so a reply sent from wa would otherwise show
// without its quote bar everywhere except on the other person's phone.
func Quotes() string { return filepath.Join(StateDir(), "sent-quotes.json") }

// WacliStore is where wacli keeps its database, mirroring its own defaults so
// wa can find the store without asking.
func WacliStore() string {
	if v := os.Getenv("WACLI_STORE_DIR"); v != "" {
		return v
	}
	if v := os.Getenv("XDG_STATE_HOME"); v != "" {
		return filepath.Join(v, "wacli")
	}
	return filepath.Join(home(), ".local", "state", "wacli")
}

// EnsureDirs creates the directories wa writes to.
func EnsureDirs() error {
	for _, dir := range []string{ConfigDir(), StateDir(), CacheDir()} {
		if err := os.MkdirAll(dir, 0o700); err != nil {
			return err
		}
	}
	return nil
}

func home() string {
	if h, err := os.UserHomeDir(); err == nil {
		return h
	}
	return "."
}
