package theme

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const wallustJSON = `{
  "cursor": "#FACDAC", "background": "#29272B", "foreground": "#F7F6D9",
  "color0": "#4F4C51", "color1": "#AA9B75", "color2": "#FDA380", "color3": "#F0B864",
  "color4": "#81E0B9", "color5": "#DAD1C1", "color6": "#E9E692", "color7": "#ECEAC0",
  "color8": "#A5A486", "color9": "#AA9B75", "color10": "#FDA380", "color11": "#F0B864",
  "color12": "#81E0B9", "color13": "#DAD1C1", "color14": "#E9E692", "color15": "#ECEAC0"
}`

// pywal nests the same values, and a machine may well have its file rather
// than wallust's.
const pywalJSON = `{
  "special": {"background": "#101014", "foreground": "#E8E8EE", "cursor": "#E8E8EE"},
  "colors": {
    "color0": "#101014", "color1": "#C05050", "color2": "#50C070", "color3": "#C0A050",
    "color4": "#5080C0", "color5": "#9050C0", "color6": "#50B0C0", "color7": "#C0C0C8",
    "color8": "#303038", "color9": "#D06060", "color10": "#60D080", "color11": "#D0B060",
    "color12": "#6090D0", "color13": "#A060D0", "color14": "#60C0D0", "color15": "#F0F0F8"
  }
}`

func TestAPaletteFromTheWallpaper(t *testing.T) {
	p, err := paletteFromJSON([]byte(wallustJSON))
	if err != nil {
		t.Fatal(err)
	}
	if p.Bg != "#29272B" || p.Fg != "#F7F6D9" {
		t.Errorf("bg/fg = %s/%s", p.Bg, p.Fg)
	}
	if p.Accent != "#81E0B9" {
		t.Errorf("accent = %s", p.Accent)
	}
	if p.ANSI[15] != "#ECEAC0" {
		t.Errorf("ansi[15] = %s", p.ANSI[15])
	}
	// Everything else is mixed towards the background, so a surface reads as
	// raised whatever the wallpaper happened to be.
	for name, got := range map[string]string{
		"raised": p.Raised, "edge": p.Edge, "selection": p.Selection,
		"bubble mine": p.BubbleMine, "bubble theirs": p.BubbleTheirs,
		"muted": p.Muted, "faint": p.Faint,
	} {
		if !hex6.MatchString(got) {
			t.Errorf("%s = %q, not a colour", name, got)
		}
		if got == p.Bg {
			t.Errorf("%s is the background itself, so it will not be seen", name)
		}
	}
	if err := p.validate("test"); err != nil {
		t.Errorf("the derived palette does not validate: %v", err)
	}
}

func TestAPywalFileWorksToo(t *testing.T) {
	p, err := paletteFromJSON([]byte(pywalJSON))
	if err != nil {
		t.Fatal(err)
	}
	if p.Bg != "#101014" || p.Accent != "#5080C0" {
		t.Errorf("bg=%s accent=%s", p.Bg, p.Accent)
	}
}

func TestANonsenseColourFileIsAnError(t *testing.T) {
	// Falling back silently would leave somebody staring at colours they
	// thought they had changed.
	for _, body := range []string{`{}`, `{"background":"nope","foreground":"#FFFFFF"}`, `not json`} {
		if _, err := paletteFromJSON([]byte(body)); err == nil {
			t.Errorf("%q was accepted", body)
		}
	}
}

func TestNoColourFileIsNotAnError(t *testing.T) {
	t.Setenv("HOME", t.TempDir())
	p, from, err := FromWallpaper()
	if err != nil {
		t.Fatal(err)
	}
	if from != "" {
		t.Errorf("found %q in an empty home", from)
	}
	if p.Bg != "" {
		t.Error("a palette was invented out of nothing")
	}
}

func TestTheWallpaperFileIsFoundInTheCache(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	dir := filepath.Join(home, ".cache", "blackwall")
	os.MkdirAll(dir, 0o755)
	os.WriteFile(filepath.Join(dir, "palette.json"), []byte(wallustJSON), 0o644)

	p, from, err := FromWallpaper()
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasSuffix(from, "palette.json") {
		t.Errorf("from = %q", from)
	}
	if p.Accent != "#81E0B9" {
		t.Errorf("accent = %s", p.Accent)
	}
}

func TestGlassLeavesTheBarsUnpainted(t *testing.T) {
	p, _ := Load("")
	plain := New(p, "solid")
	glass := plain.Glassy()

	if !glass.Glass {
		t.Error("glass styles do not say so")
	}
	if glass.Status.GetBackground() == plain.Status.GetBackground() {
		t.Error("the status bar is still painted")
	}
	if glass.Picker.GetBackground() == plain.Picker.GetBackground() {
		t.Error("the picker is still painted")
	}
	// Content keeps its fill: a transparent bubble is just text.
	if glass.BubbleMine.GetBackground() != plain.BubbleMine.GetBackground() {
		t.Error("bubbles lost their fill")
	}
	if glass.ListBadge.GetBackground() != plain.ListBadge.GetBackground() {
		t.Error("badges lost their fill")
	}
}
