package config

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestWatchReloadsOnWrite(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "config.toml")
	os.WriteFile(p, []byte("[ui]\nlist_width = 30\n"), 0o644)

	got := make(chan Config, 4)
	w, err := Watch(p, func(c Config, _ []Warning, err error) {
		if err == nil {
			got <- c
		}
	})
	if err != nil {
		t.Fatal(err)
	}
	defer w.Close()

	os.WriteFile(p, []byte("[ui]\nlist_width = 55\n"), 0o644)
	select {
	case c := <-got:
		if c.UI.ListWidth != 55 {
			t.Errorf("reloaded list_width = %d, want 55", c.UI.ListWidth)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("the watcher never fired")
	}
}

func TestWatchReportsAParseErrorWithoutLosingTheConfig(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "config.toml")
	os.WriteFile(p, []byte("[ui]\nlist_width = 30\n"), 0o644)

	errs := make(chan error, 4)
	w, err := Watch(p, func(_ Config, _ []Warning, err error) {
		if err != nil {
			errs <- err
		}
	})
	if err != nil {
		t.Fatal(err)
	}
	defer w.Close()

	os.WriteFile(p, []byte("[ui\nlist_width ="), 0o644)
	select {
	case err := <-errs:
		if err == nil {
			t.Fatal("expected a parse error")
		}
	case <-time.After(3 * time.Second):
		t.Fatal("a broken config must be reported, not swallowed")
	}
}

func TestWatchSurvivesAtomicSaveByRename(t *testing.T) {
	// Editors commonly write a temp file and rename over the target, which
	// replaces the inode. Watching the file itself would go deaf here.
	dir := t.TempDir()
	p := filepath.Join(dir, "config.toml")
	os.WriteFile(p, []byte("[ui]\nlist_width = 30\n"), 0o644)

	got := make(chan Config, 4)
	w, err := Watch(p, func(c Config, _ []Warning, err error) {
		if err == nil {
			got <- c
		}
	})
	if err != nil {
		t.Fatal(err)
	}
	defer w.Close()

	tmp := p + ".new"
	os.WriteFile(tmp, []byte("[ui]\nlist_width = 77\n"), 0o644)
	os.Rename(tmp, p)

	select {
	case c := <-got:
		if c.UI.ListWidth != 77 {
			t.Errorf("list_width = %d, want 77", c.UI.ListWidth)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("the watcher missed an atomic save")
	}
}

func TestCloseIsIdempotent(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "config.toml")
	os.WriteFile(p, []byte(""), 0o644)
	w, err := Watch(p, func(Config, []Warning, error) {})
	if err != nil {
		t.Fatal(err)
	}
	if err := w.Close(); err != nil {
		t.Fatal(err)
	}
	if err := w.Close(); err != nil {
		t.Errorf("second Close returned %v", err)
	}
}
