package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func write(t *testing.T, body string) string {
	t.Helper()
	dir := t.TempDir()
	p := filepath.Join(dir, "config.toml")
	if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestDefaultIsSelfConsistent(t *testing.T) {
	c := Default()
	if c.UI.TimeoutLen != 300 {
		t.Errorf("timeoutlen = %d, want 300 (matching the author's Neovim)", c.UI.TimeoutLen)
	}
	if c.UI.Scrolloff != 10 {
		t.Errorf("scrolloff = %d, want 10", c.UI.Scrolloff)
	}
	if c.UI.Leader != "<Space>" {
		t.Errorf("leader = %q, want <Space>", c.UI.Leader)
	}
	if !c.UI.IgnoreCase || !c.UI.SmartCase {
		t.Error("ignorecase and smartcase should both default on")
	}
	if c.UI.Clipboard != "unnamedplus" {
		t.Errorf("clipboard = %q, want unnamedplus", c.UI.Clipboard)
	}
	if len(c.Keys["normal"]) == 0 {
		t.Error("the default keymap has no normal-mode bindings")
	}
}

func TestLoadAppliesDefaultsForMissingFile(t *testing.T) {
	cfg, warns, err := Load(filepath.Join(t.TempDir(), "absent.toml"))
	if err != nil {
		t.Fatalf("a missing config must not be an error: %v", err)
	}
	if len(warns) != 0 {
		t.Errorf("unexpected warnings: %v", warns)
	}
	if cfg.UI.TimeoutLen != 300 || cfg.UI.Scrolloff != 10 {
		t.Errorf("defaults not applied: %+v", cfg.UI)
	}
}

func TestLoadOverlaysUserFile(t *testing.T) {
	cfg, _, err := Load(write(t, "[ui]\nlist_width = 42\n"))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.UI.ListWidth != 42 {
		t.Errorf("list_width = %d, want 42", cfg.UI.ListWidth)
	}
	if cfg.UI.Scrolloff != 10 {
		t.Errorf("unset keys must keep their default, got scrolloff = %d", cfg.UI.Scrolloff)
	}
}

func TestUserKeysMergeWithDefaults(t *testing.T) {
	cfg, _, err := Load(write(t, "[keys.normal]\n\"<C-p>\" = \"picker.chats\"\n"))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Keys["normal"]["<C-p>"] != "picker.chats" {
		t.Error("the user binding was lost")
	}
	if cfg.Keys["normal"]["j"] == "" {
		t.Error("adding one binding must not wipe the default keymap")
	}
}

func TestLoadWarnsOnUnknownKeys(t *testing.T) {
	_, warns, err := Load(write(t, "[ui]\nlist_widht = 42\n"))
	if err != nil {
		t.Fatalf("an unknown key must warn, not fail: %v", err)
	}
	if len(warns) != 1 || !strings.Contains(warns[0].Error(), "list_widht") {
		t.Errorf("warnings = %v, want one naming list_widht", warns)
	}
}

func TestLoadReportsASyntaxError(t *testing.T) {
	if _, _, err := Load(write(t, "[ui\nlist_width = ")); err == nil {
		t.Fatal("a malformed file must be an error, not a silent default")
	}
}

func TestValidateRejectsUnknownAction(t *testing.T) {
	cfg, _, err := Load(write(t, "[keys.normal]\n\"<C-d>\" = \"scroll.nope\"\n"))
	if err != nil {
		t.Fatal(err)
	}
	known := func(name string) bool { return name != "scroll.nope" }
	err = cfg.Validate(known)
	if err == nil || !strings.Contains(err.Error(), "scroll.nope") {
		t.Fatalf("Validate() = %v, want an error naming scroll.nope", err)
	}
}

func TestValidateRejectsUnparseableKeyNotation(t *testing.T) {
	cfg, _, err := Load(write(t, "[keys.normal]\n\"<C->\" = \"app.quit\"\n"))
	if err != nil {
		t.Fatal(err)
	}
	err = cfg.Validate(func(string) bool { return true })
	if err == nil || !strings.Contains(err.Error(), "<C->") {
		t.Fatalf("Validate() = %v, want an error naming the bad notation", err)
	}
}

func TestValidateRejectsUnknownMode(t *testing.T) {
	cfg, _, err := Load(write(t, "[keys.nonsense]\n\"x\" = \"app.quit\"\n"))
	if err != nil {
		t.Fatal(err)
	}
	if err := cfg.Validate(func(string) bool { return true }); err == nil {
		t.Fatal("an unknown mode name must be rejected")
	}
}

func TestValidateAcceptsTheShippedDefaults(t *testing.T) {
	// The defaults must never ship broken: every notation must parse.
	if err := Default().Validate(func(string) bool { return true }); err != nil {
		t.Fatalf("the shipped default keymap does not validate: %v", err)
	}
}

func TestLoadParsesDurations(t *testing.T) {
	cfg, _, err := Load(write(t, "[lock]\nidle_timeout = \"90s\"\n"))
	if err != nil {
		t.Fatal(err)
	}
	if time.Duration(cfg.Lock.IdleTimeout) != 90*time.Second {
		t.Errorf("idle_timeout = %v, want 90s", time.Duration(cfg.Lock.IdleTimeout))
	}
}

func TestLoadRejectsAMalformedDuration(t *testing.T) {
	if _, _, err := Load(write(t, "[lock]\nidle_timeout = \"ten minutes\"\n")); err == nil {
		t.Fatal("a malformed duration must be an error")
	}
}
