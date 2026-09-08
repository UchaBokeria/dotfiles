package vim

import (
	"strings"
	"sync"
	"unicode"
)

// Clipboard is the system clipboard. The terminal implementation writes OSC 52,
// which reaches the clipboard through kitty and tmux alike.
type Clipboard interface {
	Read() (string, error)
	Write(string) error
}

// Content is one register's contents.
type Content struct {
	Text string
	// Linewise marks text yanked as whole lines, which pastes above or below
	// rather than inside the current line.
	Linewise bool
}

// Registers holds the named registers.
//
// The special names follow vim: `"` unnamed, `0` the last yank, `_` the black
// hole, `+` and `*` the system clipboard. An upper-case name appends to its
// lower-case register.
type Registers struct {
	mu   sync.Mutex
	regs map[rune]Content
	clip Clipboard
	// unnamedPlus mirrors Neovim's clipboard=unnamedplus: the unnamed register
	// and the system clipboard are the same thing.
	unnamedPlus bool
}

// NewRegisters returns an empty set. A nil Clipboard makes `+` an ordinary
// register, which is what tests want and what a terminal without OSC 52 gets.
func NewRegisters(clip Clipboard, unnamedPlus bool) *Registers {
	return &Registers{regs: map[rune]Content{}, clip: clip, unnamedPlus: unnamedPlus}
}

// Set writes a register.
func (r *Registers) Set(name rune, text string, linewise bool) {
	if name == '_' {
		return // the black hole discards everything
	}
	r.mu.Lock()
	defer r.mu.Unlock()

	if name == 0 {
		name = '"'
	}
	if unicode.IsUpper(name) {
		lower := unicode.ToLower(name)
		prev := r.regs[lower]
		r.regs[lower] = Content{Text: prev.Text + text, Linewise: linewise || prev.Linewise}
		r.mirror(lower, r.regs[lower])
		return
	}

	c := Content{Text: text, Linewise: linewise}
	r.regs[name] = c

	// A yank into an explicit register still updates the unnamed one, as in
	// vim, so a bare `p` afterwards pastes what was just yanked.
	if name != '"' {
		r.regs['"'] = c
	}
	r.mirror(name, c)
}

// mirror keeps the system clipboard and the unnamed register in step. The
// caller holds the lock.
func (r *Registers) mirror(name rune, c Content) {
	if r.clip == nil {
		return
	}
	switch {
	case name == '+' || name == '*':
		_ = r.clip.Write(c.Text)
	case r.unnamedPlus && (name == '"' || !isSpecial(name)):
		_ = r.clip.Write(c.Text)
	}
}

func isSpecial(name rune) bool {
	return name == '"' || name == '0' || name == '_' || name == '+' || name == '*'
}

// Get reads a register.
func (r *Registers) Get(name rune) Content {
	r.mu.Lock()
	defer r.mu.Unlock()

	if name == 0 {
		name = '"'
	}
	if name == '_' {
		return Content{}
	}
	if unicode.IsUpper(name) {
		name = unicode.ToLower(name)
	}

	if r.clip != nil {
		if name == '+' || name == '*' || (r.unnamedPlus && name == '"') {
			if text, err := r.clip.Read(); err == nil {
				return Content{Text: text, Linewise: strings.HasSuffix(text, "\n")}
			}
		}
	}
	return r.regs[name]
}

// Yank records a yank: register 0 always holds the most recent one, so a later
// delete does not clobber it.
func (r *Registers) Yank(name rune, text string, linewise bool) {
	r.Set(name, text, linewise)
	if name == 0 || name == '"' {
		r.mu.Lock()
		r.regs['0'] = Content{Text: text, Linewise: linewise}
		r.mu.Unlock()
	}
}

// Names lists the registers that hold something, for :registers.
func (r *Registers) Names() []rune {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make([]rune, 0, len(r.regs))
	for name, c := range r.regs {
		if c.Text != "" {
			out = append(out, name)
		}
	}
	return out
}

// SetMacro stores a recorded key sequence. Macros share the register namespace
// with text, exactly as in vim.
func (r *Registers) SetMacro(name rune, notation string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.regs[unicode.ToLower(name)] = Content{Text: notation}
}
