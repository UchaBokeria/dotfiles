package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const handWritten = `# my config, hands off
[ui]
list_width = 34  # narrow on purpose
`

func TestPersistLeavesTheMainConfigAlone(t *testing.T) {
	main := write(t, handWritten)
	over := filepath.Join(filepath.Dir(main), "overrides.toml")

	if err := Persist(over, map[string]string{"ui.list_width": "40"}); err != nil {
		t.Fatal(err)
	}
	body, err := os.ReadFile(main)
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != handWritten {
		t.Errorf(":set! must not touch config.toml, it is symlinked out of the dotfiles repo:\n%s", body)
	}
}

func TestPersistedOverrideWins(t *testing.T) {
	main := write(t, handWritten)
	over := filepath.Join(filepath.Dir(main), "overrides.toml")
	if err := Persist(over, map[string]string{"ui.list_width": "40"}); err != nil {
		t.Fatal(err)
	}
	cfg, warns, err := Load(main, over)
	if err != nil {
		t.Fatalf("the file we wrote does not parse: %v", err)
	}
	if len(warns) != 0 {
		t.Errorf("the file we wrote warns: %v", warns)
	}
	if cfg.UI.ListWidth != 40 {
		t.Errorf("list_width = %d, want the override's 40", cfg.UI.ListWidth)
	}
}

func TestPersistMergesWithEarlierWrites(t *testing.T) {
	over := filepath.Join(t.TempDir(), "overrides.toml")
	if err := Persist(over, map[string]string{"ui.list_width": "40"}); err != nil {
		t.Fatal(err)
	}
	if err := Persist(over, map[string]string{"ui.scrolloff": "3"}); err != nil {
		t.Fatal(err)
	}
	cfg, _, err := Load("", over)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.UI.ListWidth != 40 {
		t.Errorf("the earlier :set! was lost: list_width = %d", cfg.UI.ListWidth)
	}
	if cfg.UI.Scrolloff != 3 {
		t.Errorf("the later :set! did not apply: scrolloff = %d", cfg.UI.Scrolloff)
	}
}

func TestPersistReplacesRatherThanAppends(t *testing.T) {
	over := filepath.Join(t.TempDir(), "overrides.toml")
	Persist(over, map[string]string{"ui.list_width": "40"})
	Persist(over, map[string]string{"ui.list_width": "50"})
	body, _ := os.ReadFile(over)
	if strings.Contains(string(body), "list_width = 40") {
		t.Errorf("the stale value survived:\n%s", body)
	}
	if n := strings.Count(string(body), "[ui]"); n != 1 {
		t.Errorf("[ui] appears %d times - TOML forbids a repeated table:\n%s", n, body)
	}
}

func TestPersistRoundTripsEveryScalarKind(t *testing.T) {
	over := filepath.Join(t.TempDir(), "overrides.toml")
	if err := Persist(over, map[string]string{
		"ui.list_width":     "40",
		"ui.ignorecase":     "false",
		"ui.timestamp":      "2006-01-02 15:04",
		"lock.idle_timeout": "45s",
	}); err != nil {
		t.Fatal(err)
	}
	cfg, warns, err := Load("", over)
	if err != nil {
		t.Fatalf("round trip does not parse: %v", err)
	}
	if len(warns) != 0 {
		t.Errorf("round trip warns: %v", warns)
	}
	if cfg.UI.ListWidth != 40 || cfg.UI.IgnoreCase || cfg.UI.Timestamp != "2006-01-02 15:04" {
		t.Errorf("round trip lost values: %+v", cfg.UI)
	}
	if cfg.Lock.IdleTimeout.String() != "45s" {
		t.Errorf("duration round trip = %s", cfg.Lock.IdleTimeout)
	}
}

func TestPersistRejectsAnInvalidAssignment(t *testing.T) {
	over := filepath.Join(t.TempDir(), "overrides.toml")
	if err := Persist(over, map[string]string{"ui.list_width": "wide"}); err == nil {
		t.Fatal("an unparseable value must be refused before it reaches the file")
	}
	if _, err := os.Stat(over); err == nil {
		t.Error("a refused :set! must not create the file")
	}
}

func TestPersistCreatesAMissingDirectory(t *testing.T) {
	over := filepath.Join(t.TempDir(), "nested", "dir", "overrides.toml")
	if err := Persist(over, map[string]string{"ui.list_width": "40"}); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(over); err != nil {
		t.Fatalf("Persist did not create the file: %v", err)
	}
}
