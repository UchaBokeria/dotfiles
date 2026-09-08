// Package theme loads the colour palette and turns it into named styles.
//
// Every colour wa draws comes from here. The palette is written by
// `blackwall-theme wa`, which derives it from the same tokens as every other
// surface in the rice, so a wallpaper change re-themes the client in the same
// pass. A copy is embedded in the binary so wa looks right on a machine that
// has no dotfiles at all.
package theme

import (
	_ "embed"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"regexp"
	"strings"

	"github.com/BurntSushi/toml"
)

//go:embed fallback.toml
var fallbackTOML string

// Palette is the resolved colour set. Every entry is an opaque #RRGGBB: the
// terminal has already composited its own background, so a colour carrying
// alpha would either render the alpha literally or be silently flattened to
// full strength.
type Palette struct {
	Bg       string `toml:"bg"`
	Fg       string `toml:"fg"`
	Accent   string `toml:"accent"`
	OnAccent string `toml:"on_accent"`
	Link     string `toml:"link"`
	Muted    string `toml:"muted"`
	Faint    string `toml:"faint"`
	Cursor   string `toml:"cursor"`

	Raised    string `toml:"raised"`
	RaisedHi  string `toml:"raised_hi"`
	Sunken    string `toml:"sunken"`
	Edge      string `toml:"edge"`
	Selection string `toml:"selection"`

	BubbleMine   string `toml:"bubble_mine"`
	BubbleTheirs string `toml:"bubble_theirs"`

	Warn string `toml:"warn"`
	Bad  string `toml:"bad"`
	Good string `toml:"good"`

	ANSI [16]string `toml:"ansi"`
}

var hex6 = regexp.MustCompile(`^#[0-9A-Fa-f]{6}$`)

// Load reads a palette written by `blackwall-theme wa`. An empty path or a
// missing file yields the embedded fallback, which is not an error: running
// without the dotfiles is a supported case. A file that exists but is wrong is
// an error, because silently ignoring it would leave the user staring at
// colours they thought they had changed.
func Load(file string) (Palette, error) {
	var p Palette
	if _, err := toml.Decode(fallbackTOML, &p); err != nil {
		panic("theme: embedded fallback.toml does not parse: " + err.Error())
	}

	if file == "" {
		return p, nil
	}
	body, err := os.ReadFile(file)
	if errors.Is(err, fs.ErrNotExist) {
		return p, nil
	}
	if err != nil {
		return p, fmt.Errorf("reading %s: %w", file, err)
	}

	// Decode over the fallback so a partial palette keeps the rest, and track
	// which ANSI table the file actually supplied.
	var probe struct {
		ANSI []string `toml:"ansi"`
	}
	if _, err := toml.Decode(string(body), &probe); err != nil {
		return p, fmt.Errorf("%s: %w", file, err)
	}
	if probe.ANSI != nil && len(probe.ANSI) != 16 {
		return p, fmt.Errorf("%s: ansi has %d entries, want 16", file, len(probe.ANSI))
	}
	if _, err := toml.Decode(string(body), &p); err != nil {
		return p, fmt.Errorf("%s: %w", file, err)
	}

	if err := p.validate(file); err != nil {
		return Palette{}, err
	}
	return p, nil
}

func (p Palette) validate(file string) error {
	named := []struct {
		name  string
		value string
	}{
		{"bg", p.Bg}, {"fg", p.Fg}, {"accent", p.Accent}, {"on_accent", p.OnAccent},
		{"link", p.Link}, {"muted", p.Muted}, {"faint", p.Faint}, {"cursor", p.Cursor},
		{"raised", p.Raised}, {"raised_hi", p.RaisedHi}, {"sunken", p.Sunken},
		{"edge", p.Edge}, {"selection", p.Selection},
		{"bubble_mine", p.BubbleMine}, {"bubble_theirs", p.BubbleTheirs},
		{"warn", p.Warn}, {"bad", p.Bad}, {"good", p.Good},
	}
	var bad []string
	for _, e := range named {
		if !hex6.MatchString(e.value) {
			bad = append(bad, fmt.Sprintf("%s = %q", e.name, e.value))
		}
	}
	for i, c := range p.ANSI {
		if !hex6.MatchString(c) {
			bad = append(bad, fmt.Sprintf("ansi[%d] = %q", i, c))
		}
	}
	if len(bad) > 0 {
		return fmt.Errorf(
			"%s: not an opaque #RRGGBB colour: %s\n"+
				"a terminal composites its own background, so alpha and short hex are both wrong",
			file, strings.Join(bad, ", "))
	}
	return nil
}
