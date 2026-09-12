package ui

import (
	"sync"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
)

// graphics draws photographs as pixels where the terminal can.
//
// The picture is put on screen as *text*: a run of placeholder characters that
// say "cell (row, column) of image 7". Ordinary text is something tmux
// understands, stores in its grid and redraws wherever the pane moves it, so
// the picture stays inside its bubble and scrolls with the conversation.
//
// Placing a picture directly - the obvious way - does not survive tmux. The
// escape means "draw at the cursor", tmux forwards it unchanged, and the outer
// terminal's cursor is not where the pane is drawing. The picture lands in a
// corner of the screen.
//
// Because the placeholders are text, there is no placement to track and
// nothing to clean up when a message scrolls away: the text goes, and the
// picture goes with it.
type graphics struct {
	mode media.Graphics
	// dir holds the scaled copies the terminal reads.
	dir string

	mu sync.Mutex
	// sent maps a source file to the image id the terminal knows it by, and
	// the size the virtual placement was declared at.
	sent   map[string]placed
	nextID uint32

	// onErr reports a picture that could not be drawn. Drawing happens while
	// the frame is being built, where returning an error would mean an empty
	// bubble and no explanation.
	onErr func(error)
}

// placed is a picture the terminal has, and the cell box it was declared at.
type placed struct {
	id         uint32
	cols, rows int
}

func newGraphics(mode media.Graphics, dir string) *graphics {
	return &graphics{mode: mode, dir: dir, sent: map[string]placed{}, nextID: 1}
}

// Enabled reports whether pixel images are being drawn.
func (g *graphics) Enabled() bool { return g != nil && g.mode.Enabled }

// OnError sets the sink for pictures that could not be drawn.
func (g *graphics) OnError(fn func(error)) {
	if g != nil {
		g.onErr = fn
	}
}

func (g *graphics) report(err error) {
	if g != nil && g.onErr != nil && err != nil {
		g.onErr(err)
	}
}

// Lines returns the rows that draw a picture inside a box of cells.
//
// Every row is self-contained, so the renderer may write any of them, in any
// order, as often as it likes. That matters more than it sounds: the bubble
// renderer measures a body twice and keeps only the second measurement, and
// the frame renderer keeps only the most recent frame, so anything that had to
// happen exactly once would be thrown away sooner or later.
func (g *graphics) Lines(path string, cols, rows int) []string {
	if !g.Enabled() || cols < 1 || rows < 1 {
		return nil
	}
	if cols > maxPlaceholderCells {
		cols = maxPlaceholderCells
	}
	if rows > maxPlaceholderCells {
		rows = maxPlaceholderCells
	}

	boxCols, boxRows, err := media.KittyBox(path, cols, rows)
	if err != nil || boxCols < 1 || boxRows < 1 {
		g.report(err)
		return nil
	}

	// A scaled copy on disk, written once. The terminal is told where it is
	// rather than sent its contents, which keeps the escape to a hundred bytes
	// and lets it be repeated freely.
	file, err := media.KittyPNG(path, g.dir, maxTransmitPixels)
	if err != nil {
		g.report(err)
		return nil
	}

	g.mu.Lock()
	known, seen := g.sent[path]
	if !seen || known.cols != boxCols || known.rows != boxRows {
		if !seen {
			known.id = g.nextID
			g.nextID++
		}
		known.cols, known.rows = boxCols, boxRows
		g.sent[path] = known
	}
	id := known.id
	g.mu.Unlock()

	// Both escapes go out with the first row. Transmitting is idempotent - it
	// hands the terminal the same file again - and re-declaring the placement
	// is how a picture follows the bubble when the pane is resized.
	head := media.KittyTransmitFile(file, id, g.mode.Tmux) +
		media.KittyVirtualPlacement(id, boxCols, boxRows, g.mode.Tmux)

	out := make([]string, 0, boxRows)
	for r := 0; r < boxRows; r++ {
		row := media.PlaceholderRow(id, r, boxCols)
		if r == 0 {
			row = head + row
		}
		out = append(out, row)
	}
	return out
}

// Clear removes every picture wa handed the terminal, for when it exits.
func (g *graphics) Clear() string {
	if !g.Enabled() {
		return ""
	}
	return media.KittyDeleteAll(g.mode.Tmux)
}

// maxPlaceholderCells is how wide or tall a picture may be, in cells. Past it
// there is no diacritic to name the cell with.
const maxPlaceholderCells = 297

// maxTransmitPixels is how large a picture is stored at.
//
// It has to cover the biggest box a bubble will ever draw it in, because the
// terminal scales the one copy from then on. A bubble is at most about sixty
// cells across and a dozen rows tall, and a cell is roughly ten by twenty
// pixels, so this is comfortably more than any of them will ask for.
const maxTransmitPixels = 150_000
