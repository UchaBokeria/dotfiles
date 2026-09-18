package theme

import (
	"fmt"
	"sort"
	"strings"
)

// Icons are the small pictures the interface uses instead of words where a
// picture is quicker to read: a pin, a muted bell, a paperclip.
//
// Three sets, because a glyph that is not in the font is a box with a
// question mark in it, which is worse than the word. Nerd is the default - the
// rice's kitty maps every Nerd Font range - and a server reached from some
// other terminal can drop to unicode or ascii without losing meaning.
type IconSet int

const (
	IconsNerd IconSet = iota
	IconsUnicode
	IconsASCII
)

// ParseIconSet reads the configured name.
func ParseIconSet(name string) (IconSet, error) {
	switch strings.ToLower(strings.TrimSpace(name)) {
	case "", "nerd", "nerdfont", "nerd-font":
		return IconsNerd, nil
	case "unicode":
		return IconsUnicode, nil
	case "ascii", "none", "plain":
		return IconsASCII, nil
	}
	return IconsNerd, fmt.Errorf("%q is not an icon set (nerd, unicode, ascii)", name)
}

func (s IconSet) String() string {
	switch s {
	case IconsUnicode:
		return "unicode"
	case IconsASCII:
		return "ascii"
	}
	return "nerd"
}

// icon is one picture in each of the three sets.
type icon struct{ nerd, unicode, ascii string }

// iconTable is every icon the interface draws. The Nerd glyphs are Material
// Design Icons (U+F0001 and up) and powerline, both mapped by the rice's kitty
// config, and chosen to read as one family: the same weight, the same optical
// size, no mixing of outline and filled styles within a row.
var iconTable = map[string]icon{
	"account":   {"\U000F0004", "◉", "@"},
	"group":     {"\U000F0849", "◎", "#"},
	"chat":      {"\U000F0369", "◌", ">"},
	"pin":       {"\U000F0403", "⚲", "^"},
	"muted":     {"\U000F075F", "⊘", "~"},
	"archived":  {"\U000F003C", "▣", "a"},
	"favourite": {"\U000F04CE", "★", "*"},
	"attach":    {"\U000F03E2", "⌁", "+"},
	"send":      {"\U000F048A", "➤", ">"},
	"image":     {"\U000F02E9", "▨", "img"},
	"video":     {"\U000F0567", "▶", "vid"},
	"audio":     {"\U000F075A", "♪", "aud"},
	"voice":     {"\U000F036C", "◖", "mic"},
	"document":  {"\U000F0219", "▤", "doc"},
	"archive":   {"\U000F05C4", "▥", "zip"},
	"sticker":   {"\U000F0785", "☺", ":)"},
	"link":      {"\U000F0337", "⛓", "url"},
	"search":    {"\U000F0349", "⌕", "/"},
	"lock":      {"\U000F033E", "⚿", "L"},
	"sync":      {"\U000F04E6", "⟳", "s"},
	"offline":   {"\U000F0164", "⊗", "x"},
	"reply":     {"\U000F045A", "↩", "<"},
	"forward":   {"\U000F0214", "↪", ">"},
	"download":  {"\U000F01DA", "↓", "v"},
	"contacts":  {"\U000F06CB", "☰", "c"},
	"filter":    {"\U000F0232", "▽", "f"},
	"tag":       {"\U000F04F9", "⌗", "t"},
	"edit":      {"\U000F03EB", "✎", "e"},
	"keyboard":  {"\U000F030C", "⌨", "k"},
	"clock":     {"\U000F0954", "◷", "."},
	"sent":      {"\U000F012C", "✓", "v"},
	"delivered": {"\U000F012D", "✓✓", "vv"},
	"read":      {"\U000F012D", "✓✓", "vv"},
	"failed":    {"\U000F0026", "!", "!"},
	"close":     {"\U000F0156", "✕", "x"},
	"whatsapp":  {"\U000F05A3", "◍", "wa"},
	"mode":      {"\U000F030C", "▸", ">"},
	"list":      {"\U000F0279", "☰", "="},
	"compose":   {"\U000F03EB", "✎", "_"},
	"dot":       {"\U000F0765", "●", "*"},
}

// Icons resolves pictures for one set, with the user's replacements on top.
type Icons struct {
	set       IconSet
	overrides map[string]string
}

// NewIcons returns the icons for a set. Overrides replace individual glyphs by
// name, whatever the set, so a single picture that a font lacks can be swapped
// without giving up the rest.
func NewIcons(set IconSet, overrides map[string]string) Icons {
	return Icons{set: set, overrides: overrides}
}

// Get is the glyph for a name, or empty for a name nobody defined.
func (i Icons) Get(name string) string {
	if g, ok := i.overrides[name]; ok {
		return g
	}
	ic, ok := iconTable[name]
	if !ok {
		return ""
	}
	switch i.set {
	case IconsUnicode:
		return ic.unicode
	case IconsASCII:
		return ic.ascii
	}
	return ic.nerd
}

// Set is the configured set.
func (i Icons) Set() IconSet { return i.set }

// IconNames lists every icon, for :help and for validating overrides.
func IconNames() []string {
	out := make([]string, 0, len(iconTable))
	for k := range iconTable {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
