package clipboard

import (
	"bytes"
	"encoding/base64"
	"os"
	"strings"
	"testing"
)

// noHelper points the lookup at an empty PATH so the OSC 52 path is taken.
func noHelper(t *testing.T) {
	t.Helper()
	t.Setenv("PATH", t.TempDir())
}

func TestOSC52CarriesTheText(t *testing.T) {
	noHelper(t)
	t.Setenv("TMUX", "")

	var buf bytes.Buffer
	c := New(&buf)
	if err := c.Write("hello clipboard"); err != nil {
		t.Fatal(err)
	}

	got := buf.String()
	if !strings.HasPrefix(got, "\x1b]52;c;") {
		t.Fatalf("not an OSC 52 sequence: %q", got)
	}
	payload := strings.TrimSuffix(strings.TrimPrefix(got, "\x1b]52;c;"), "\x07")
	decoded, err := base64.StdEncoding.DecodeString(payload)
	if err != nil {
		t.Fatalf("payload is not base64: %v", err)
	}
	if string(decoded) != "hello clipboard" {
		t.Errorf("decoded %q", decoded)
	}
}

func TestInsideTmuxTheSequenceIsWrapped(t *testing.T) {
	// Without the wrapper tmux eats the sequence and the copy silently does
	// nothing.
	noHelper(t)
	t.Setenv("TMUX", "/tmp/tmux-1000/default,123,0")

	var buf bytes.Buffer
	if err := New(&buf).Write("x"); err != nil {
		t.Fatal(err)
	}
	got := buf.String()
	if !strings.HasPrefix(got, "\x1bPtmux;") || !strings.HasSuffix(got, "\x1b\\") {
		t.Errorf("not wrapped for tmux: %q", got)
	}
	if !strings.Contains(got, "\x1b\x1b]52") {
		t.Errorf("the inner escape was not doubled, so tmux will not forward it: %q", got)
	}
}

func TestAHelperIsPreferredOverOSC52(t *testing.T) {
	// A helper survives tmux; an escape sequence often does not.
	dir := t.TempDir()
	out := dir + "/copied.txt"
	script := dir + "/wl-copy"
	// /bin/cat by absolute path: PATH is about to be narrowed to this
	// directory, so the script cannot look anything up for itself.
	if err := os.WriteFile(script, []byte("#!/bin/sh\n/bin/cat > "+out+"\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", dir)

	var buf bytes.Buffer
	c := New(&buf)
	if err := c.Write("via the helper"); err != nil {
		t.Fatal(err)
	}
	if buf.Len() != 0 {
		t.Errorf("an escape sequence was written even though a helper exists: %q", buf.String())
	}
	body, err := os.ReadFile(out)
	if err != nil {
		t.Fatalf("the helper was not run: %v", err)
	}
	if string(body) != "via the helper" {
		t.Errorf("the helper received %q", body)
	}
}

func TestWriteOfNothingIsNotAnError(t *testing.T) {
	noHelper(t)
	if err := New(nil).Write(""); err != nil {
		t.Errorf("copying an empty selection should be a no-op, got %v", err)
	}
}

func TestWithoutAnywhereToWriteItSaysSo(t *testing.T) {
	noHelper(t)
	err := New(nil).Write("text")
	if err == nil {
		t.Fatal("a copy with nowhere to go must be reported, not silently dropped")
	}
	if !strings.Contains(err.Error(), "wl-copy") {
		t.Errorf("err = %v, want it to name what to install", err)
	}
}

func TestReadWithoutAHelperIsAnError(t *testing.T) {
	noHelper(t)
	if _, err := New(nil).Read(); err == nil {
		t.Fatal("OSC 52 cannot read; that must be an error rather than an empty paste")
	}
}

func TestAvailableNamesTheMechanism(t *testing.T) {
	noHelper(t)
	t.Setenv("TMUX", "")
	if got := New(nil).Available(); got != "OSC 52" {
		t.Errorf("Available = %q", got)
	}
}

func TestAFailingHelperFallsBackToOSC52(t *testing.T) {
	// A helper that is installed but broken - no Wayland display, say - must
	// not swallow the copy.
	dir := t.TempDir()
	script := dir + "/wl-copy"
	if err := os.WriteFile(script, []byte("#!/bin/sh\nexit 1\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", dir)
	t.Setenv("TMUX", "")

	var buf bytes.Buffer
	if err := New(&buf).Write("still copied"); err != nil {
		t.Fatal(err)
	}
	if buf.Len() == 0 {
		t.Fatal("a failing helper dropped the copy instead of falling back")
	}
}
