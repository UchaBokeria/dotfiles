package theme

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Colours from the wallpaper.
//
// wallust (and pywal before it) write the colours they pulled out of the
// wallpaper as a small JSON file, and everything else on the desktop reads it.
// A terminal client that ignored it would be the one window on the screen
// still wearing last month's palette.
//
// Only a background, a foreground, a cursor and sixteen ANSI colours are
// given. Everything else wa draws with - the raised surfaces, the edges, the
// bubbles - is derived from those, by mixing towards the background rather
// than by picking more colours out of the wall.

// wallustPaths are looked at in order, and the first that parses wins.
func wallustPaths() []string {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil
	}
	return []string{
		// This rice writes one for everything that is not a terminal.
		filepath.Join(home, ".cache", "blackwall", "palette.json"),
		// wallust's and pywal's own, which is what a machine without the rice
		// will have.
		filepath.Join(home, ".cache", "wallust", "colors.json"),
		filepath.Join(home, ".cache", "wal", "colors.json"),
	}
}

// wallustFile is the shape both tools write, give or take the nesting pywal
// uses for its own file, which is handled below.
type wallustFile struct {
	Background string            `json:"background"`
	Foreground string            `json:"foreground"`
	Cursor     string            `json:"cursor"`
	Colors     map[string]string `json:"colors"`

	Color0  string `json:"color0"`
	Color1  string `json:"color1"`
	Color2  string `json:"color2"`
	Color3  string `json:"color3"`
	Color4  string `json:"color4"`
	Color5  string `json:"color5"`
	Color6  string `json:"color6"`
	Color7  string `json:"color7"`
	Color8  string `json:"color8"`
	Color9  string `json:"color9"`
	Color10 string `json:"color10"`
	Color11 string `json:"color11"`
	Color12 string `json:"color12"`
	Color13 string `json:"color13"`
	Color14 string `json:"color14"`
	Color15 string `json:"color15"`

	Special map[string]string `json:"special"`
}

// FromWallpaper builds a palette out of whichever colour file this machine
// has, and says which one it used. An empty path means none was found, which
// is not an error: the embedded palette is a perfectly good answer.
func FromWallpaper() (Palette, string, error) {
	for _, path := range wallustPaths() {
		body, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		p, err := paletteFromJSON(body)
		if err != nil {
			return Palette{}, path, fmt.Errorf("%s: %w", path, err)
		}
		return p, path, nil
	}
	return Palette{}, "", nil
}

func paletteFromJSON(body []byte) (Palette, error) {
	var f wallustFile
	if err := json.Unmarshal(body, &f); err != nil {
		return Palette{}, err
	}

	// pywal nests the same values; wallust's own template does not.
	bg, fg, cursor := f.Background, f.Foreground, f.Cursor
	if f.Special != nil {
		bg = firstNonEmpty(f.Special["background"], bg)
		fg = firstNonEmpty(f.Special["foreground"], fg)
		cursor = firstNonEmpty(f.Special["cursor"], cursor)
	}

	var ansi [16]string
	flat := []string{
		f.Color0, f.Color1, f.Color2, f.Color3, f.Color4, f.Color5, f.Color6, f.Color7,
		f.Color8, f.Color9, f.Color10, f.Color11, f.Color12, f.Color13, f.Color14, f.Color15,
	}
	for i := range ansi {
		c := flat[i]
		if f.Colors != nil {
			c = firstNonEmpty(f.Colors["color"+strconv.Itoa(i)], c)
		}
		ansi[i] = c
	}

	if !hex6.MatchString(bg) || !hex6.MatchString(fg) {
		return Palette{}, fmt.Errorf("no usable background and foreground")
	}
	for i, c := range ansi {
		if !hex6.MatchString(c) {
			return Palette{}, fmt.Errorf("color%d is %q, not a #rrggbb colour", i, c)
		}
	}
	return derive(bg, fg, cursor, ansi), nil
}

// derive fills in everything wa draws with from the handful the wallpaper gave.
//
// The rule throughout is to mix towards the background. A surface that is a
// little lighter than what is behind it reads as raised whatever the wallpaper
// happened to be, where a colour picked out of the wall reads as raised only
// half the time.
func derive(bg, fg, cursor string, ansi [16]string) Palette {
	p := Palette{
		Bg:     bg,
		Fg:     fg,
		Cursor: firstNonEmpty(cursor, ansi[15]),
		ANSI:   ansi,

		Accent:   ansi[4],
		OnAccent: bg,
		Link:     ansi[6],
		Muted:    mix(fg, bg, 0.35),
		Faint:    mix(fg, bg, 0.6),

		Raised:    mix(bg, fg, 0.08),
		RaisedHi:  mix(bg, fg, 0.14),
		Sunken:    mix(bg, "#000000", 0.25),
		Edge:      mix(bg, fg, 0.22),
		Selection: mix(bg, ansi[4], 0.28),

		BubbleMine:   mix(bg, ansi[4], 0.20),
		BubbleTheirs: mix(bg, fg, 0.10),

		Warn: ansi[3],
		Bad:  ansi[1],
		Good: ansi[2],
	}
	return p
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}

// mix blends two colours, t of the way from a to b.
func mix(a, b string, t float64) string {
	ar, ag, ab, ok1 := rgb(a)
	br, bg2, bb, ok2 := rgb(b)
	if !ok1 || !ok2 {
		return a
	}
	f := func(x, y int) int { return int(float64(x) + (float64(y)-float64(x))*t) }
	return fmt.Sprintf("#%02X%02X%02X", f(ar, br), f(ag, bg2), f(ab, bb))
}

func rgb(hex string) (r, g, b int, ok bool) {
	if !hex6.MatchString(hex) {
		return 0, 0, 0, false
	}
	v, err := strconv.ParseUint(hex[1:], 16, 32)
	if err != nil {
		return 0, 0, 0, false
	}
	return int(v>>16) & 0xff, int(v>>8) & 0xff, int(v) & 0xff, true
}
