package media

import (
	"fmt"
	"image"
	"image/color"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"os"
	"strings"

	// WhatsApp stickers are webp, and so is a good share of what people
	// forward. The standard library does not decode it, and without this a
	// sticker renders as a filename chip - which is close to useless, because
	// a sticker has no filename worth reading.
	_ "golang.org/x/image/webp"
)

// upperHalf is the character every image cell is drawn with: its foreground
// paints the top pixel and its background the bottom, so one row of cells
// carries two rows of pixels.
const upperHalf = "▀"

// MaxPixels caps what will be decoded. A photograph straight from a phone is
// tens of megapixels; decoding one to draw forty columns of text is a waste
// that shows up as a visible stall while scrolling.
const MaxPixels = 40_000_000

// Thumbnail renders an image file as terminal rows.
//
// cols and rows are cell counts. Because each cell is two pixels tall, the
// aspect ratio works out at roughly 1:2 - which is why the height is doubled
// before fitting rather than after.
func Thumbnail(path string, cols, rows int) ([]string, error) {
	if cols < 1 || rows < 1 {
		return nil, fmt.Errorf("no room for a preview")
	}
	img, err := decode(path)
	if err != nil {
		return nil, err
	}
	return Render(img, cols, rows), nil
}

func decode(path string) (image.Image, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	cfg, _, err := image.DecodeConfig(f)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	if cfg.Width*cfg.Height > MaxPixels {
		return nil, fmt.Errorf("%s is %dx%d, too large to preview", path, cfg.Width, cfg.Height)
	}
	if _, err := f.Seek(0, 0); err != nil {
		return nil, err
	}
	img, _, err := image.Decode(f)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return img, nil
}

// Render draws an image into half-block rows, preserving the aspect ratio and
// fitting inside the given cell box.
func Render(img image.Image, cols, rows int) []string {
	b := img.Bounds()
	if b.Dx() == 0 || b.Dy() == 0 {
		return nil
	}

	// Fit the image into cols x (rows*2) pixels.
	maxW, maxH := cols, rows*2
	scale := float64(maxW) / float64(b.Dx())
	if s := float64(maxH) / float64(b.Dy()); s < scale {
		scale = s
	}
	w := int(float64(b.Dx()) * scale)
	h := int(float64(b.Dy()) * scale)
	if w < 1 {
		w = 1
	}
	if h < 2 {
		h = 2
	}
	// An odd pixel height would leave a half-drawn final row.
	if h%2 == 1 {
		h--
	}

	out := make([]string, 0, h/2)
	for y := 0; y < h; y += 2 {
		var line strings.Builder
		for x := 0; x < w; x++ {
			top := sample(img, b, x, y, w, h)
			bottom := sample(img, b, x, y+1, w, h)
			line.WriteString(cell(top, bottom))
		}
		line.WriteString("\x1b[0m")
		out = append(out, line.String())
	}
	return out
}

// sample takes the pixel of the source that maps to a thumbnail position,
// using nearest neighbour. Averaging would look better and cost more; at forty
// columns the difference is not visible.
func sample(img image.Image, b image.Rectangle, x, y, w, h int) color.RGBA {
	sx := b.Min.X + x*b.Dx()/w
	sy := b.Min.Y + y*b.Dy()/h
	if sx >= b.Max.X {
		sx = b.Max.X - 1
	}
	if sy >= b.Max.Y {
		sy = b.Max.Y - 1
	}
	r, g, bl, a := img.At(sx, sy).RGBA()

	// Composite onto a mid grey: a transparent sticker on an unknown terminal
	// background otherwise renders as a black rectangle.
	const bg = 0x8080
	if a < 0xffff {
		alpha := float64(a) / 0xffff
		r = uint32(float64(r)*alpha + bg*(1-alpha))
		g = uint32(float64(g)*alpha + bg*(1-alpha))
		bl = uint32(float64(bl)*alpha + bg*(1-alpha))
	}
	return color.RGBA{R: uint8(r >> 8), G: uint8(g >> 8), B: uint8(bl >> 8), A: 255}
}

// cell writes one character carrying two pixels.
func cell(top, bottom color.RGBA) string {
	return fmt.Sprintf("\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm%s",
		top.R, top.G, top.B, bottom.R, bottom.G, bottom.B, upperHalf)
}

// Dimensions reports an image's size without decoding all of it, for the
// caption under a preview.
func Dimensions(path string) (w, h int, err error) {
	f, err := os.Open(path)
	if err != nil {
		return 0, 0, err
	}
	defer f.Close()

	cfg, _, err := image.DecodeConfig(f)
	if err != nil {
		return 0, 0, err
	}
	return cfg.Width, cfg.Height, nil
}
