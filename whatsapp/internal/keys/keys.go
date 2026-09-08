// Package keys parses vim key notation into comparable key values. It is
// shared by the configuration loader, which validates bindings, and the modal
// engine, which matches them, so neither has to depend on the other.
package keys

import (
	"fmt"
	"strings"
	"unicode"
)

// Mod is a set of modifier flags.
type Mod uint8

const (
	Ctrl Mod = 1 << iota
	Alt
	Shift
)

// Special names a key that has no printable rune.
type Special uint8

const (
	None Special = iota
	Esc
	CR
	Tab
	BS
	Space
	Del
	Up
	Down
	Left
	Right
	Home
	End
	PgUp
	PgDn
	Insert
	F1
	F2
	F3
	F4
	F5
	F6
	F7
	F8
	F9
	F10
	F11
	F12
)

var specialNames = map[string]Special{
	"esc":       Esc,
	"escape":    Esc,
	"cr":        CR,
	"enter":     CR,
	"return":    CR,
	"tab":       Tab,
	"bs":        BS,
	"backspace": BS,
	"space":     Space,
	"del":       Del,
	"delete":    Del,
	"up":        Up,
	"down":      Down,
	"left":      Left,
	"right":     Right,
	"home":      Home,
	"end":       End,
	"pgup":      PgUp,
	"pageup":    PgUp,
	"pgdn":      PgDn,
	"pagedown":  PgDn,
	"insert":    Insert,
	"f1":        F1,
	"f2":        F2,
	"f3":        F3,
	"f4":        F4,
	"f5":        F5,
	"f6":        F6,
	"f7":        F7,
	"f8":        F8,
	"f9":        F9,
	"f10":       F10,
	"f11":       F11,
	"f12":       F12,
}

// canonical is the spelling Key.String uses, so notation round trips.
var specialSpelling = map[Special]string{
	Esc: "Esc", CR: "CR", Tab: "Tab", BS: "BS", Space: "Space", Del: "Del",
	Up: "Up", Down: "Down", Left: "Left", Right: "Right",
	Home: "Home", End: "End", PgUp: "PgUp", PgDn: "PgDn", Insert: "Insert",
	F1: "F1", F2: "F2", F3: "F3", F4: "F4", F5: "F5", F6: "F6",
	F7: "F7", F8: "F8", F9: "F9", F10: "F10", F11: "F11", F12: "F12",
}

// Key is one keystroke. Either Rune or Special is set, never both.
type Key struct {
	Mods    Mod
	Rune    rune
	Special Special
}

// String renders the key back into notation.
func (k Key) String() string {
	if k.Mods == 0 && k.Special == None {
		if k.Rune == '<' {
			return "<lt>"
		}
		return string(k.Rune)
	}
	var b strings.Builder
	b.WriteByte('<')
	if k.Mods&Ctrl != 0 {
		b.WriteString("C-")
	}
	if k.Mods&Alt != 0 {
		b.WriteString("M-")
	}
	if k.Mods&Shift != 0 {
		b.WriteString("S-")
	}
	if k.Special != None {
		b.WriteString(specialSpelling[k.Special])
	} else {
		b.WriteRune(k.Rune)
	}
	b.WriteByte('>')
	return b.String()
}

// Digit reports the key as a decimal digit, for count accumulation. A modified
// key is never a digit: <C-5> is a binding, not a count.
func (k Key) Digit() (int, bool) {
	if k.Mods != 0 || k.Special != None {
		return 0, false
	}
	if k.Rune >= '0' && k.Rune <= '9' {
		return int(k.Rune - '0'), true
	}
	return 0, false
}

// Printable reports the character this key inserts in insert mode. Modified
// and non-printing keys insert nothing.
func (k Key) Printable() (rune, bool) {
	if k.Mods&(Ctrl|Alt) != 0 {
		return 0, false
	}
	if k.Special == Space {
		return ' ', true
	}
	if k.Special != None {
		return 0, false
	}
	if k.Rune == 0 || !unicode.IsPrint(k.Rune) {
		return 0, false
	}
	return k.Rune, true
}

// Parse converts notation such as `<leader>ts` or `<C-d>` into keys. leader is
// substituted for `<leader>`; passing nil makes `<leader>` an error rather than
// silently dropping the prefix from a binding.
func Parse(notation string, leader []Key) ([]Key, error) {
	if notation == "" {
		return nil, fmt.Errorf("empty key notation")
	}
	var out []Key
	runes := []rune(notation)
	for i := 0; i < len(runes); {
		if runes[i] != '<' {
			out = append(out, Key{Rune: runes[i]})
			i++
			continue
		}
		end := indexRune(runes[i:], '>')
		if end < 0 {
			return nil, fmt.Errorf("unterminated %q in %q", "<", notation)
		}
		token := string(runes[i+1 : i+end])
		i += end + 1

		k, expanded, err := parseToken(token, leader)
		if err != nil {
			return nil, fmt.Errorf("%q in %q: %w", "<"+token+">", notation, err)
		}
		if expanded != nil {
			out = append(out, expanded...)
			continue
		}
		out = append(out, k)
	}
	return out, nil
}

// MustParse is Parse for notation known at compile time, such as test input.
func MustParse(notation string) []Key {
	k, err := Parse(notation, []Key{{Special: Space}})
	if err != nil {
		panic(err)
	}
	return k
}

func parseToken(token string, leader []Key) (Key, []Key, error) {
	if token == "" {
		return Key{}, nil, fmt.Errorf("empty")
	}
	lower := strings.ToLower(token)
	if lower == "leader" {
		if len(leader) == 0 {
			return Key{}, nil, fmt.Errorf("no leader is configured")
		}
		return Key{}, leader, nil
	}
	if lower == "lt" {
		return Key{Rune: '<'}, nil, nil
	}
	if lower == "gt" {
		return Key{Rune: '>'}, nil, nil
	}

	var mods Mod
	rest := token
	for {
		if len(rest) < 2 || rest[1] != '-' {
			break
		}
		switch rest[0] {
		case 'C', 'c':
			mods |= Ctrl
		case 'M', 'm', 'A', 'a':
			mods |= Alt
		case 'S', 's':
			mods |= Shift
		default:
			// Not a modifier prefix; the rest is the key itself.
			goto done
		}
		rest = rest[2:]
	}
done:
	if rest == "" {
		return Key{}, nil, fmt.Errorf("modifier with no key")
	}
	if sp, ok := specialNames[strings.ToLower(rest)]; ok {
		return Key{Mods: mods, Special: sp}, nil, nil
	}
	r := []rune(rest)
	if len(r) != 1 {
		return Key{}, nil, fmt.Errorf("unknown key name %q", rest)
	}
	if mods == 0 {
		// `<x>` with no modifier is not notation we accept; it is almost
		// always a typo for a special name.
		return Key{}, nil, fmt.Errorf("unknown key name %q", rest)
	}
	return Key{Mods: mods, Rune: r[0]}, nil, nil
}

func indexRune(rs []rune, want rune) int {
	for i, r := range rs {
		if r == want {
			return i
		}
	}
	return -1
}

// Equal reports whether two key sequences are identical.
func Equal(a, b []Key) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// Notation renders a key sequence back to a single notation string.
func Notation(ks []Key) string {
	var b strings.Builder
	for _, k := range ks {
		b.WriteString(k.String())
	}
	return b.String()
}
