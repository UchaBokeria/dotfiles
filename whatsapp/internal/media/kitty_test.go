package media

import (
	"encoding/base64"
	"os"
	"strings"
	"testing"
)

func env(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func TestDetectGraphics(t *testing.T) {
	cases := []struct {
		name    string
		env     map[string]string
		enabled bool
		tmux    bool
	}{
		{"kitty", map[string]string{"KITTY_WINDOW_ID": "1", "TERM": "xterm-kitty"}, true, false},
		{"kitty in tmux", map[string]string{"KITTY_WINDOW_ID": "1", "TERM": "tmux-256color", "TMUX": "/tmp/x"}, true, true},
		// tmux does not pass the per-pane variable through, and rewrites TERM.
		// What is left is the session-wide pair.
		{"kitty under tmux, no window id",
			map[string]string{"KITTY_PID": "5", "TERM": "tmux-256color", "TMUX": "/tmp/x"}, true, true},
		{"kitty by installation dir",
			map[string]string{"KITTY_INSTALLATION_DIR": "/usr/lib/kitty", "TERM": "tmux-256color"}, true, false},
		{"ghostty", map[string]string{"TERM_PROGRAM": "ghostty"}, true, false},
		{"wezterm", map[string]string{"WEZTERM_PANE": "0"}, true, false},
		{"plain xterm", map[string]string{"TERM": "xterm-256color"}, false, false},
		{"nothing", map[string]string{}, false, false},
	}
	for _, c := range cases {
		got := DetectGraphics(env(c.env))
		if got.Enabled != c.enabled {
			t.Errorf("%s: Enabled = %v, want %v (%s)", c.name, got.Enabled, c.enabled, got.Reason)
		}
		if got.Tmux != c.tmux {
			t.Errorf("%s: Tmux = %v, want %v", c.name, got.Tmux, c.tmux)
		}
		if got.Reason == "" {
			t.Errorf("%s: no reason given", c.name)
		}
	}
}

func TestTmuxWrappingDoublesEscapes(t *testing.T) {
	// tmux forwards an escape it does not understand only inside a passthrough
	// sequence, and finds the end of the payload by the doubled ESC.
	got := wrapTmux("\x1b_Ga=p\x1b\\", true)
	if !strings.HasPrefix(got, "\x1bPtmux;") {
		t.Errorf("no passthrough prefix: %q", got)
	}
	if !strings.HasSuffix(got, "\x1b\\") {
		t.Errorf("no terminator: %q", got)
	}
	payload := strings.TrimSuffix(strings.TrimPrefix(got, "\x1bPtmux;"), "\x1b\\")
	if payload != "\x1b\x1b_Ga=p\x1b\x1b\\" {
		t.Errorf("payload = %q, want every ESC doubled", payload)
	}
	if got := wrapTmux("\x1b_Ga=p\x1b\\", false); strings.Contains(got, "tmux") {
		t.Errorf("wrapped outside tmux: %q", got)
	}
}

func TestVirtualPlacementIsWellFormed(t *testing.T) {
	got := KittyVirtualPlacement(7, 40, 10, false)
	for _, want := range []string{"a=p", "U=1", "i=7", "c=40", "r=10", "q=2"} {
		if !strings.Contains(got, want) {
			t.Errorf("%q missing from %q", want, got)
		}
	}
	if strings.Contains(got, "C=1") {
		t.Error("a virtual placement has no cursor policy; it is not placed anywhere")
	}
}

func TestPlaceholderRowMarksItsCells(t *testing.T) {
	got := PlaceholderRow(42, 3, 5)

	if n := strings.Count(got, string(placeholder)); n != 5 {
		t.Errorf("%d placeholder cells, want 5", n)
	}
	// The row and column of the first cell are spelled out; the rest inherit
	// the row and count along, which is what keeps a wide row short.
	if !strings.ContainsRune(got, diacritic(3)) {
		t.Error("the row is not marked")
	}
	if !strings.ContainsRune(got, diacritic(0)) {
		t.Error("the first column is not marked")
	}
	if !strings.HasPrefix(got, "\x1b[38;2;0;0;42m") {
		t.Errorf("the image id is not in the foreground colour: %q", got[:20])
	}
	if !strings.HasSuffix(got, "\x1b[39m") {
		t.Error("the foreground colour is not put back")
	}
}

func TestPlaceholderRowCarriesTheWholeID(t *testing.T) {
	// Ids past 255 have to survive, or two pictures collide and one shows in
	// place of the other.
	got := PlaceholderRow(0x010203, 0, 1)
	if !strings.HasPrefix(got, "\x1b[38;2;1;2;3m") {
		t.Errorf("id 0x010203 became %q", got[:20])
	}
}

func TestPlaceholderRowOfNothing(t *testing.T) {
	if got := PlaceholderRow(1, 0, 0); got != "" {
		t.Errorf("got %q", got)
	}
}

func TestDiacriticsAreKittys(t *testing.T) {
	runes := []rune(rowColumnDiacritics)
	if len(runes) != maxPlaceholderCells {
		t.Fatalf("%d diacritics, want %d", len(runes), maxPlaceholderCells)
	}
	// The first three, from kitty's own table. A shifted list shows the wrong
	// slice of every picture.
	for i, want := range []rune{0x0305, 0x030D, 0x030E} {
		if runes[i] != want {
			t.Errorf("diacritic %d = %U, want %U", i, runes[i], want)
		}
	}
	if got := diacritic(-1); got != runes[0] {
		t.Errorf("a negative index gave %U", got)
	}
	if got := diacritic(maxPlaceholderCells); got != runes[0] {
		t.Errorf("an out-of-range index gave %U", got)
	}
}

func TestKittyPNGWritesAScaledCopy(t *testing.T) {
	dir := t.TempDir()
	got, err := KittyPNG("testdata/sticker-lossy.webp", dir, 4000)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasSuffix(got, ".png") {
		t.Errorf("wrote %q", got)
	}
	w, h, err := Dimensions(got)
	if err != nil {
		t.Fatal(err)
	}
	if w*h > 4000 {
		t.Errorf("the copy is %dx%d, over the %d pixel cap", w, h, 4000)
	}
	if w*2 < h || h*2 < w {
		t.Errorf("the aspect ratio was not kept: %dx%d from 120x90", w, h)
	}
}

func TestKittyPNGReusesTheCopy(t *testing.T) {
	// The picture is written once and named from then on, so the file has to
	// be found again rather than re-encoded on every redraw.
	dir := t.TempDir()
	first, err := KittyPNG("testdata/sticker-lossy.webp", dir, 4000)
	if err != nil {
		t.Fatal(err)
	}
	before, err := os.Stat(first)
	if err != nil {
		t.Fatal(err)
	}

	second, err := KittyPNG("testdata/sticker-lossy.webp", dir, 4000)
	if err != nil {
		t.Fatal(err)
	}
	if second != first {
		t.Errorf("a second call wrote %q, not %q", second, first)
	}
	after, _ := os.Stat(second)
	if !after.ModTime().Equal(before.ModTime()) {
		t.Error("the copy was written again")
	}
}

func TestKittyPNGLeavesNoTemporaryFile(t *testing.T) {
	// A half-written PNG read once would be cached as a broken picture.
	dir := t.TempDir()
	if _, err := KittyPNG("testdata/sticker-lossy.webp", dir, 4000); err != nil {
		t.Fatal(err)
	}
	entries, _ := os.ReadDir(dir)
	for _, e := range entries {
		if strings.HasSuffix(e.Name(), ".tmp") {
			t.Errorf("left %q behind", e.Name())
		}
	}
}

func TestKittyPNGOfSomethingUndecodable(t *testing.T) {
	if _, err := KittyPNG("testdata/voice.ogg", t.TempDir(), 4000); err == nil {
		t.Error("a voice note is not a picture")
	}
}

func TestKittyTransmitFileNamesTheFile(t *testing.T) {
	got := KittyTransmitFile("/home/x/.cache/wa/graphics/ab.png", 4, false)
	for _, want := range []string{"a=t", "i=4", "f=100", "t=f", "q=2"} {
		if !strings.Contains(got, want) {
			t.Errorf("%q missing from %q", want, got)
		}
	}
	if len(got) > 200 {
		t.Errorf("the escape is %d bytes; it should carry a path, not pixels", len(got))
	}

	payload := got[strings.Index(got, ";")+1 : len(got)-2]
	path, err := base64.StdEncoding.DecodeString(payload)
	if err != nil {
		t.Fatalf("the path is not base64: %v", err)
	}
	if string(path) != "/home/x/.cache/wa/graphics/ab.png" {
		t.Errorf("path = %q", path)
	}
}

func TestKittyBoxKeepsTheAspectRatio(t *testing.T) {
	// 120x90 is 4:3. A cell is about twice as tall as it is wide, so 40
	// columns of it is 30 pixels tall in half-cells, or 15 rows.
	cols, rows, err := KittyBox("testdata/sticker-lossy.webp", 40, 20)
	if err != nil {
		t.Fatal(err)
	}
	if cols != 40 {
		t.Errorf("cols = %d, want the full width", cols)
	}
	if rows != 15 {
		t.Errorf("rows = %d, want 15 for a 4:3 picture 40 columns wide", rows)
	}
}

func TestKittyBoxNeverExceedsTheBox(t *testing.T) {
	for _, box := range [][2]int{{10, 2}, {4, 40}, {1, 1}} {
		cols, rows, err := KittyBox("testdata/sticker-lossy.webp", box[0], box[1])
		if err != nil {
			t.Fatal(err)
		}
		if cols > box[0] || rows > box[1] || cols < 1 || rows < 1 {
			t.Errorf("box %v gave %dx%d", box, cols, rows)
		}
	}
}

func TestDeleteEscapes(t *testing.T) {
	if got := KittyDeleteAll(false); !strings.Contains(got, "a=d,d=A") {
		t.Errorf("got %q", got)
	}
}
