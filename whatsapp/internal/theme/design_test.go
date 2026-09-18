package theme

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestShapesParseAndDrawTheirCaps(t *testing.T) {
	for name, want := range map[string]Shape{"pill": ShapePill, "": ShapePill, "Rounded": ShapeRounded, "square": ShapeSquare} {
		got, err := ParseShape(name)
		if err != nil || got != want {
			t.Errorf("ParseShape(%q) = %v, %v", name, got, err)
		}
	}
	if _, err := ParseShape("blob"); err == nil {
		t.Error("an unknown shape was accepted")
	}
	l, r := ShapePill.Caps()
	if l != "" || r != "" {
		t.Errorf("pill caps are %q %q, want tmux's half circles", l, r)
	}
}

func TestPillIsTwoCellsWiderThanItsText(t *testing.T) {
	for _, s := range []Shape{ShapePill, ShapeRounded, ShapeSquare} {
		out := Pill(s, "hello", lipgloss.Color("#ffffff"), lipgloss.Color("#333333"), nil, false)
		if w := lipgloss.Width(out); w != PillWidth(5) {
			t.Errorf("%s pill is %d wide, want %d", s, w, PillWidth(5))
		}
	}
}

func TestEveryIconExistsInEverySet(t *testing.T) {
	for _, set := range []IconSet{IconsNerd, IconsUnicode, IconsASCII} {
		icons := NewIcons(set, nil)
		for _, name := range IconNames() {
			if icons.Get(name) == "" {
				t.Errorf("%s set has no %q icon", set, name)
			}
		}
	}
}

func TestASCIIIconsAreASCII(t *testing.T) {
	icons := NewIcons(IconsASCII, nil)
	for _, name := range IconNames() {
		for _, r := range icons.Get(name) {
			if r > 127 {
				t.Errorf("ascii icon %q contains %q", name, r)
			}
		}
	}
}

func TestIconOverridesWinInAnySet(t *testing.T) {
	icons := NewIcons(IconsNerd, map[string]string{"pin": "P"})
	if icons.Get("pin") != "P" {
		t.Error("an override was ignored")
	}
	if icons.Get("muted") == "" || strings.Contains(icons.Get("muted"), "P") {
		t.Error("an override leaked into another icon")
	}
	if icons.Get("no-such-icon") != "" {
		t.Error("an unknown icon produced a glyph")
	}
}

func TestColourOverridesReplaceRoles(t *testing.T) {
	p, _ := Load("")
	got, err := p.WithColors(map[string]string{"accent": "#123456", "bubble_mine": "#abcdef"})
	if err != nil {
		t.Fatal(err)
	}
	if got.Accent != "#123456" || got.BubbleMine != "#abcdef" {
		t.Errorf("overrides not applied: %+v", got)
	}
	if _, err := p.WithColors(map[string]string{"acent": "#123456"}); err == nil {
		t.Error("a misspelt role was accepted")
	}
	if _, err := p.WithColors(map[string]string{"accent": "red"}); err == nil {
		t.Error("a colour that is not #RRGGBB was accepted")
	}
}

func TestChipsUseTheConfiguredShape(t *testing.T) {
	p, _ := Load("")
	st := New(p, "solid").WithDesign(ShapePill, NewIcons(IconsNerd, nil))
	if !strings.Contains(st.Chip("x", p.Fg, p.Raised, false), "") {
		t.Error("a pill chip has no half-circle cap")
	}
	sq := st.WithDesign(ShapeSquare, NewIcons(IconsASCII, nil))
	if strings.Contains(sq.Chip("x", p.Fg, p.Raised, false), "") {
		t.Error("a square chip still has a pill cap")
	}
}

func TestMixBlendsAndSurvivesGarbage(t *testing.T) {
	if got := Mix("#000000", "#FFFFFF", 0.5); got != "#808080" {
		t.Errorf("Mix = %s", got)
	}
	if got := Mix("#102030", "#102030", 0.7); got != "#102030" {
		t.Errorf("mixing a colour with itself changed it: %s", got)
	}
	if got := Mix("nonsense", "#FFFFFF", 0.5); got != "nonsense" {
		t.Errorf("a malformed colour was not passed through: %s", got)
	}
}

func TestTheSelectedFillIsVisiblyDifferent(t *testing.T) {
	p, _ := Load("")
	sel := p.SelectedFill(p.BubbleMine)
	if sel == p.BubbleMine {
		t.Error("the selected fill equals the bubble fill")
	}
}

func TestContrastAndReadable(t *testing.T) {
	if c := Contrast("#000000", "#FFFFFF"); c < 20.9 {
		t.Errorf("black on white contrast = %.2f", c)
	}
	if c := Contrast("#777777", "#777777"); c != 1 {
		t.Errorf("a colour against itself = %.2f", c)
	}
	// A pale cyan on a pale chip: the light-palette case that vanished.
	fg := Readable("#81E0E0", "#DCD6C8", "#2B2A28", 3.0)
	if Contrast(fg, "#DCD6C8") < 3.0 {
		t.Errorf("Readable returned %s at %.2f", fg, Contrast(fg, "#DCD6C8"))
	}
	// Already readable colours come back untouched.
	if got := Readable("#FFFFFF", "#000000", "#777777", 3.0); got != "#FFFFFF" {
		t.Errorf("a readable colour was changed to %s", got)
	}
}
