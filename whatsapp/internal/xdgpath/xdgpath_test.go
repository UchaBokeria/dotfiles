package xdgpath

import (
	"path/filepath"
	"strings"
	"testing"
)

func TestPathsFollowTheEnvironment(t *testing.T) {
	t.Setenv("XDG_CONFIG_HOME", "/tmp/cfg")
	t.Setenv("XDG_STATE_HOME", "/tmp/state")
	t.Setenv("XDG_CACHE_HOME", "/tmp/cache")

	if got := Config(); got != "/tmp/cfg/wa/config.toml" {
		t.Errorf("Config = %q", got)
	}
	if got := Lock(); got != "/tmp/state/wa/lock.json" {
		t.Errorf("Lock = %q", got)
	}
	if got := CacheDir(); got != "/tmp/cache/wa" {
		t.Errorf("CacheDir = %q", got)
	}
}

func TestSecretsLiveInStateNotConfig(t *testing.T) {
	// config.toml is symlinked out of the dotfiles repository. Anything
	// secret that landed beside it would end up committed.
	t.Setenv("XDG_CONFIG_HOME", "/tmp/cfg")
	t.Setenv("XDG_STATE_HOME", "/tmp/state")

	for _, p := range []string{Lock(), Daemon()} {
		if strings.HasPrefix(p, ConfigDir()) {
			t.Errorf("%s is inside the config directory", p)
		}
		if !strings.HasPrefix(p, StateDir()) {
			t.Errorf("%s is not in the state directory", p)
		}
	}
}

func TestWacliStoreDefault(t *testing.T) {
	t.Setenv("WACLI_STORE_DIR", "")
	t.Setenv("XDG_STATE_HOME", "/tmp/state")
	if got := WacliStore(); got != filepath.Join("/tmp/state", "wacli") {
		t.Errorf("WacliStore = %q", got)
	}

	t.Setenv("WACLI_STORE_DIR", "/elsewhere")
	if got := WacliStore(); got != "/elsewhere" {
		t.Errorf("an explicit WACLI_STORE_DIR was ignored: %q", got)
	}
}

func TestOverridesAreNotTheMainConfig(t *testing.T) {
	if Overrides() == Config() {
		t.Fatal(":set! must not write to the hand-written config file")
	}
}
