package theme

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadFallsBackToEmbedded(t *testing.T) {
	p, err := Load("")
	if err != nil {
		t.Fatal(err)
	}
	if p.Bg == "" || p.Accent == "" || p.ANSI[0] == "" || p.ANSI[15] == "" {
		t.Errorf("the embedded fallback is incomplete: %+v", p)
	}
	if p.BubbleMine == "" || p.BubbleTheirs == "" {
		t.Error("the fallback must carry both bubble fills")
	}
}

func TestLoadOfAMissingFileFallsBack(t *testing.T) {
	p, err := Load(filepath.Join(t.TempDir(), "absent.toml"))
	if err != nil {
		t.Fatalf("a missing palette must fall back, not fail: %v", err)
	}
	if p.Bg == "" {
		t.Error("fallback not applied")
	}
}

func TestLoadReadsAFile(t *testing.T) {
	f := filepath.Join(t.TempDir(), "theme.toml")
	os.WriteFile(f, []byte("bg = \"#111111\"\nfg = \"#eeeeee\"\naccent = \"#ff00ff\"\n"), 0o644)
	p, err := Load(f)
	if err != nil {
		t.Fatal(err)
	}
	if p.Bg != "#111111" || p.Accent != "#ff00ff" {
		t.Errorf("file values not applied: %+v", p)
	}
	if p.Warn == "" {
		t.Error("an unset entry must keep the fallback value")
	}
}

func TestLoadRejectsAMalformedColour(t *testing.T) {
	f := filepath.Join(t.TempDir(), "theme.toml")
	os.WriteFile(f, []byte("bg = \"not-a-colour\"\n"), 0o644)
	_, err := Load(f)
	if err == nil {
		t.Fatal("expected an error for a malformed colour")
	}
	if !strings.Contains(err.Error(), "bg") {
		t.Errorf("err = %v, want it to name the offending entry", err)
	}
}

func TestLoadRejectsAShortHex(t *testing.T) {
	f := filepath.Join(t.TempDir(), "theme.toml")
	os.WriteFile(f, []byte("accent = \"#fff\"\n"), 0o644)
	if _, err := Load(f); err == nil {
		t.Fatal("three-digit hex must be rejected; the generator never emits it")
	}
}

func TestLoadRejectsAnAlphaHex(t *testing.T) {
	// A terminal composites the background itself, so an alpha channel here is
	// always a mistake - it renders literally or is dropped silently.
	f := filepath.Join(t.TempDir(), "theme.toml")
	os.WriteFile(f, []byte("bg = \"#1C1D2480\"\n"), 0o644)
	if _, err := Load(f); err == nil {
		t.Fatal("#RRGGBBAA must be rejected for a terminal palette")
	}
}

func TestLoadRejectsAShortANSITable(t *testing.T) {
	f := filepath.Join(t.TempDir(), "theme.toml")
	os.WriteFile(f, []byte("ansi = [\"#000000\", \"#ffffff\"]\n"), 0o644)
	if _, err := Load(f); err == nil {
		t.Fatal("an ANSI table that is not 16 entries must be rejected")
	}
}

func TestGeneratedPaletteLoads(t *testing.T) {
	// The file blackwall-theme writes must be readable by the loader; if the
	// emitter and the loader drift, this is where it shows.
	p, err := Load("../../theme.toml")
	if err != nil {
		t.Fatalf("the generated theme.toml does not load: %v", err)
	}
	if p.Accent == "" {
		t.Error("the generated palette has no accent")
	}
}

func TestNewBuildsEveryStyle(t *testing.T) {
	p, _ := Load("")
	s := New(p, "rounded")
	if s.Generation == 0 {
		t.Error("Generation must be non-zero so the render cache can key on it")
	}
	if New(p, "rounded").Generation == s.Generation {
		t.Error("each New must produce a fresh generation, or the cache serves stale renders")
	}
}

func TestBorderNamesResolve(t *testing.T) {
	p, _ := Load("")
	for _, name := range []string{"rounded", "thick", "double", "ascii", "none"} {
		if _, err := Border(name); err != nil {
			t.Errorf("Border(%q) = %v", name, err)
		}
	}
	if _, err := Border("squiggly"); err == nil {
		t.Error("an unknown border name must be rejected, not silently defaulted")
	}
	_ = p
}

func TestSenderColoursAreStableAndVaried(t *testing.T) {
	// One colour for every name makes a busy group read as a monologue; a
	// colour that changes between redraws is worse.
	p, err := Load("")
	if err != nil {
		t.Fatal(err)
	}
	s := New(p, "solid")
	if len(s.SenderColors) < 3 {
		t.Fatalf("%d sender colours", len(s.SenderColors))
	}

	names := []string{"aka", "rezi", "Billi", "Lexo", "Ana", "Beka", "D", "ss"}
	seen := map[string]bool{}
	for _, n := range names {
		a := s.SenderStyle(n).GetForeground()
		b := s.SenderStyle(n).GetForeground()
		if a != b {
			t.Errorf("%q changed colour between calls", n)
		}
		seen[fmt.Sprint(a)] = true
	}
	if len(seen) < 2 {
		t.Error("every sender got the same colour")
	}
	if got := s.SenderStyle(""); got.GetForeground() != s.Sender.GetForeground() {
		t.Error("an empty name should fall back to the plain sender style")
	}
}

func TestSolidIsABorder(t *testing.T) {
	if _, err := Border("solid"); err != nil {
		t.Fatal(err)
	}
	p, _ := Load("")
	if !New(p, "solid").Solid {
		t.Error("solid styles do not say so")
	}
	if New(p, "rounded").Solid {
		t.Error("rounded styles claim to be solid")
	}
}
