package ui

import (
	"os"
	"strings"
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

const testPicture = "../media/testdata/sticker-lossy.webp"

func testGraphics(t *testing.T) *graphics {
	t.Helper()
	return newGraphics(media.Graphics{Enabled: true, Reason: "test"}, t.TempDir())
}

func TestGraphicsOffDrawsNothing(t *testing.T) {
	g := newGraphics(media.Graphics{}, t.TempDir())
	if g.Enabled() {
		t.Error("disabled graphics reported as enabled")
	}
	if lines := g.Lines(testPicture, 40, 10); lines != nil {
		t.Errorf("drew %d lines with graphics off", len(lines))
	}
	var nilG *graphics
	if nilG.Enabled() || nilG.Clear() != "" {
		t.Error("a nil graphics drew something")
	}
}

func TestThePictureIsDrawnAsText(t *testing.T) {
	// Placing a picture directly does not survive tmux: the escape means "draw
	// at the cursor", tmux forwards it unchanged, and the outer terminal's
	// cursor is not where the pane is drawing - so the picture lands in a
	// corner of the screen. Placeholder characters are text, which tmux
	// stores and moves like any other text.
	g := testGraphics(t)
	lines := g.Lines(testPicture, 40, 10)
	if len(lines) == 0 {
		t.Fatal("no rows")
	}

	if strings.Contains(strings.Join(lines, ""), "a=p,i=") {
		t.Error("a real placement is used; it will not survive tmux")
	}
	if !strings.Contains(lines[0], "U=1") {
		t.Error("no virtual placement was declared")
	}
	for i, l := range lines {
		if !strings.ContainsRune(l, '\U0010EEEE') {
			t.Errorf("row %d carries no placeholder characters", i)
		}
	}
}

func TestEveryRowStandsAlone(t *testing.T) {
	// The bubble renderer measures a body twice and keeps the second pass, and
	// the frame renderer keeps only the most recent frame. Anything that had
	// to happen exactly once would be thrown away sooner or later, so asking
	// for the same picture twice must give the same rows both times.
	g := testGraphics(t)
	first := g.Lines(testPicture, 40, 10)
	second := g.Lines(testPicture, 40, 10)

	if len(first) != len(second) {
		t.Fatalf("%d rows then %d", len(first), len(second))
	}
	for i := range first {
		if first[i] != second[i] {
			t.Fatalf("row %d differs between calls", i)
		}
	}
}

func TestRowsAreNumberedInOrder(t *testing.T) {
	// A cell says which row and column of the picture it is. Getting the row
	// wrong shows the wrong slice of the image in that line.
	g := testGraphics(t)
	lines := g.Lines(testPicture, 40, 10)

	seen := map[rune]bool{}
	for i, l := range lines {
		var mark rune
		for _, r := range l {
			if r == '\U0010EEEE' {
				continue
			}
			if strings.ContainsRune(media.DiacriticsForTest(), r) {
				mark = r
				break
			}
		}
		if mark == 0 {
			t.Fatalf("row %d has no row marker", i)
		}
		if seen[mark] {
			t.Errorf("row %d repeats a marker used by an earlier row", i)
		}
		seen[mark] = true
	}
}

func TestGraphicsRowsFillTheBox(t *testing.T) {
	g := testGraphics(t)
	lines := g.Lines(testPicture, 40, 10)
	if len(lines) == 0 {
		t.Fatal("no rows")
	}
	want := render.VisibleWidth(lines[len(lines)-1])
	if want < 1 {
		t.Fatal("the rows take no columns")
	}
	for i, l := range lines {
		if got := render.VisibleWidth(l); got != want {
			t.Errorf("row %d is %d columns, want %d", i, got, want)
		}
	}
}

func TestTheScaledCopyIsWrittenOnce(t *testing.T) {
	dir := t.TempDir()
	g := newGraphics(media.Graphics{Enabled: true}, dir)

	g.Lines(testPicture, 40, 10)
	files, _ := os.ReadDir(dir)
	if len(files) != 1 {
		t.Fatalf("wrote %d files, want 1", len(files))
	}
	first := files[0].Name()

	g.Lines(testPicture, 20, 5)
	files, _ = os.ReadDir(dir)
	if len(files) != 1 || files[0].Name() != first {
		t.Errorf("a second box size wrote another copy: %v", files)
	}
}

func TestAPictureKeepsItsIdentity(t *testing.T) {
	// The id travels in the foreground colour of every placeholder cell, so
	// the same file must always be the same id or the picture changes under
	// the reader.
	g := testGraphics(t)
	a := g.Lines(testPicture, 40, 10)[0]
	b := g.Lines(testPicture, 30, 8)[0]

	idOf := func(s string) string {
		i := strings.Index(s, "\x1b[38;2;")
		if i < 0 {
			return ""
		}
		return s[i : strings.Index(s[i:], "m")+i]
	}
	if idOf(a) != idOf(b) || idOf(a) == "" {
		t.Errorf("the picture changed id between sizes: %q then %q", idOf(a), idOf(b))
	}
}

func TestGraphicsClearRemovesEverything(t *testing.T) {
	if got := testGraphics(t).Clear(); !strings.Contains(got, "a=d,d=A") {
		t.Errorf("Clear = %q", got)
	}
}
