package media

import (
	"bytes"
	"crypto/sha1"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"image"
	"image/png"
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/image/draw"
)

// The kitty graphics protocol.
//
// Half blocks work everywhere and look like half blocks. A terminal that
// speaks this protocol draws the actual pixels, which for a photograph is the
// difference between recognising a face and guessing at one.
//
// Two escapes matter here:
//
//	transmit  ESC _G a=t,i=<id>,f=100,t=f,q=2 ; <base64 path> ESC \
//	place     ESC _G a=p,i=<id>,p=<pid>,c=<cols>,r=<rows>,C=1,q=2 ESC \
//
// The transmit names a file rather than carrying the pixels, so both escapes
// are about a hundred bytes and can ride on the line that draws the picture,
// repeated on every redraw. C=1 keeps the cursor where it was, so the escape
// can sit inside a line of text without disturbing the layout, and q=2
// suppresses the terminal's replies, which nothing here is reading.
//
// Inside tmux every one of these has to be wrapped in a passthrough sequence,
// and tmux only forwards it when `allow-passthrough` is on.

// Graphics describes whether pixel-accurate images can be drawn, and why not
// when they cannot.
type Graphics struct {
	Enabled bool
	// Tmux says the escapes need wrapping in a passthrough sequence.
	Tmux bool
	// Reason explains the decision, for wa doctor.
	Reason string
}

// DetectGraphics works out whether the terminal speaks the kitty protocol.
//
// Detection is by environment rather than by querying the terminal: a query
// means writing an escape and reading the reply, and at the point wa starts
// the terminal is not yet in the state to do that safely.
func DetectGraphics(env func(string) string) Graphics {
	term := strings.ToLower(env("TERM"))
	inTmux := env("TMUX") != ""

	// Several of these matter only inside tmux, which rewrites TERM and does
	// not pass every variable through. KITTY_WINDOW_ID is per pane and is lost;
	// KITTY_PID and the installation directory are set for the session and
	// survive, so they are what actually identifies kitty under tmux.
	switch {
	case env("KITTY_WINDOW_ID") != "", env("KITTY_PID") != "",
		env("KITTY_INSTALLATION_DIR") != "", strings.Contains(term, "kitty"):
	case strings.Contains(strings.ToLower(env("TERM_PROGRAM")), "ghostty"),
		env("GHOSTTY_RESOURCES_DIR") != "":
	case env("WEZTERM_PANE") != "", env("WEZTERM_EXECUTABLE") != "":
	default:
		return Graphics{Reason: "the terminal does not announce the kitty graphics protocol"}
	}

	if inTmux {
		return Graphics{
			Enabled: true, Tmux: true,
			Reason: "kitty graphics through tmux (needs `set -g allow-passthrough on`)",
		}
	}
	return Graphics{Enabled: true, Reason: "kitty graphics"}
}

// wrapTmux makes an escape survive tmux.
//
// tmux forwards an unknown escape only inside a passthrough sequence, and only
// when allow-passthrough is set. Every ESC in the payload has to be doubled,
// which is how tmux knows where the payload ends.
func wrapTmux(s string, inTmux bool) string {
	if !inTmux {
		return s
	}
	return "\x1bPtmux;" + strings.ReplaceAll(s, "\x1b", "\x1b\x1b") + "\x1b\\"
}

// KittyPNG writes a scaled-down PNG of an image into dir and returns its path,
// reusing one already there.
//
// The terminal is told where the file is rather than sent its contents. The
// data would otherwise be a quarter of a megabyte of base64 riding on a line
// of the frame - and a frame is not a reliable carrier: the renderer keeps
// only the most recent one, so a frame built while another update was arriving
// is discarded, taking the picture with it and leaving a placement pointing at
// data the terminal never received.
//
// The scaling is not optional either. A photograph from a phone is tens of
// megapixels and the bubble it is going into is a few hundred cells.
func KittyPNG(src, dir string, maxPixels int) (string, error) {
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", err
	}
	sum := sha1.Sum([]byte(fmt.Sprintf("%s\x00%d", src, maxPixels)))
	out := filepath.Join(dir, hex.EncodeToString(sum[:])+".png")

	if fi, err := os.Stat(out); err == nil && fi.Size() > 0 {
		return out, nil
	}

	img, err := decode(src)
	if err != nil {
		return "", err
	}
	img = shrink(img, maxPixels)

	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		return "", fmt.Errorf("encoding %s: %w", src, err)
	}
	// Through a temporary file: a half-written PNG would be read once and
	// then cached as a broken picture for good.
	tmp := out + ".tmp"
	if err := os.WriteFile(tmp, buf.Bytes(), 0o600); err != nil {
		return "", err
	}
	if err := os.Rename(tmp, out); err != nil {
		return "", err
	}
	return out, nil
}

// KittyTransmitFile tells the terminal to read a picture from disk.
//
// The escape carries the path, not the pixels, so it is a hundred bytes rather
// than a quarter of a megabyte and can be repeated on every redraw without
// anyone noticing. t=f leaves the file alone; wa owns it.
func KittyTransmitFile(path string, id uint32, inTmux bool) string {
	return wrapTmux(fmt.Sprintf("\x1b_Ga=t,i=%d,f=100,t=f,q=2;%s\x1b\\",
		id, base64.StdEncoding.EncodeToString([]byte(path))), inTmux)
}

// KittyVirtualPlacement declares the size a picture will be drawn at, without
// putting it anywhere.
//
// U=1 makes the placement virtual: it is a prototype, and the picture appears
// wherever the placeholder characters are printed. That indirection is the
// whole point - see PlaceholderRow.
func KittyVirtualPlacement(id uint32, cols, rows int, inTmux bool) string {
	return wrapTmux(fmt.Sprintf("\x1b_Ga=p,U=1,i=%d,c=%d,r=%d,q=2\x1b\\",
		id, cols, rows), inTmux)
}

// PlaceholderRow returns one row of the text that shows a picture.
//
// The picture is drawn where these characters are, and they are characters:
// ordinary text that tmux stores in its own grid and redraws wherever the pane
// puts it. That is what keeps an image inside its bubble.
//
// Placing a picture directly does not survive tmux. The escape says "draw
// here", tmux forwards it unchanged, and "here" is wherever the outer
// terminal's cursor happens to be rather than where the pane is drawing -
// which is how an image ends up in a corner of the screen instead of in the
// conversation.
//
// The image id travels in the foreground colour. Only the first cell of a row
// needs its row and column spelled out; the rest inherit the row and count
// along, per the protocol, which keeps a forty-cell row to a few dozen bytes.
func PlaceholderRow(id uint32, row, cols int) string {
	if cols < 1 {
		return ""
	}
	r, g, b := (id>>16)&0xff, (id>>8)&0xff, id&0xff

	var sb strings.Builder
	fmt.Fprintf(&sb, "\x1b[38;2;%d;%d;%dm", r, g, b)
	sb.WriteRune(placeholder)
	sb.WriteRune(diacritic(row))
	sb.WriteRune(diacritic(0))
	for i := 1; i < cols; i++ {
		sb.WriteRune(placeholder)
	}
	sb.WriteString("\x1b[39m")
	return sb.String()
}

// placeholder is the character that stands in for one cell of an image.
const placeholder = '\U0010EEEE'

// KittyDeleteAll removes every picture wa has put on the screen. Used when
// leaving, so nothing is left painted over the shell.
func KittyDeleteAll(inTmux bool) string {
	return wrapTmux("\x1b_Ga=d,d=A,q=2\x1b\\", inTmux)
}

// shrink scales an image down to at most n pixels, keeping the aspect ratio.
func shrink(img image.Image, n int) image.Image {
	b := img.Bounds()
	if n <= 0 || b.Dx()*b.Dy() <= n {
		return img
	}
	scale := 1.0
	for scale*scale*float64(b.Dx()*b.Dy()) > float64(n) {
		scale *= 0.9
	}
	w := int(float64(b.Dx()) * scale)
	h := int(float64(b.Dy()) * scale)
	if w < 1 {
		w = 1
	}
	if h < 1 {
		h = 1
	}

	out := image.NewRGBA(image.Rect(0, 0, w, h))
	draw.CatmullRom.Scale(out, out.Bounds(), img, b, draw.Over, nil)
	return out
}

// KittyBox is how many cells an image should occupy inside a box, keeping its
// aspect ratio. A terminal cell is about twice as tall as it is wide.
func KittyBox(path string, maxCols, maxRows int) (cols, rows int, err error) {
	w, h, err := Dimensions(path)
	if err != nil || w == 0 || h == 0 {
		return 0, 0, err
	}
	// Work in half-cells vertically, the same arithmetic the half-block
	// renderer uses, then round back up to whole rows.
	scale := float64(maxCols) / float64(w)
	if s := float64(maxRows*2) / float64(h); s < scale {
		scale = s
	}
	cols = int(float64(w) * scale)
	rows = (int(float64(h)*scale) + 1) / 2

	if cols < 1 {
		cols = 1
	}
	if rows < 1 {
		rows = 1
	}
	if cols > maxCols {
		cols = maxCols
	}
	if rows > maxRows {
		rows = maxRows
	}
	return cols, rows, nil
}

// GraphicsFromEnv reads the process environment.
func GraphicsFromEnv() Graphics { return DetectGraphics(os.Getenv) }

// DiacriticsForTest exposes the row and column markers so the interface's
// tests can recognise one.
func DiacriticsForTest() string { return rowColumnDiacritics }
