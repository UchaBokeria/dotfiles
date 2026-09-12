// Package vim is a modal editing engine.
//
// It knows nothing about WhatsApp. It consumes keystrokes and produces
// Resolved values naming an action, a motion, or an operator applied to a
// range; what those mean is the caller's business. That isolation is what
// makes a full vim surface - counts, operators, text objects, registers,
// macros, dot-repeat - testable without a terminal, a database, or a network.
package vim

import "github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"

// Mode is the editing mode.
type Mode uint8

const (
	Normal Mode = iota
	Insert
	Visual
	VisualLine
	// OpPending is entered between an operator and the motion or text object
	// it applies to: the `w` in `dw`.
	OpPending
	CmdLine
	Search
)

func (m Mode) String() string {
	switch m {
	case Normal:
		return "NORMAL"
	case Insert:
		return "INSERT"
	case Visual:
		return "VISUAL"
	case VisualLine:
		return "V-LINE"
	case OpPending:
		return "OP-PENDING"
	case CmdLine:
		return "COMMAND"
	case Search:
		return "SEARCH"
	default:
		return "?"
	}
}

// ModeName maps a configuration table name to a mode.
func ModeName(name string) (Mode, bool) {
	switch name {
	case "normal":
		return Normal, true
	case "insert":
		return Insert, true
	case "visual":
		return Visual, true
	case "cmdline":
		return CmdLine, true
	case "search":
		return Search, true
	default:
		return Normal, false
	}
}

// TargetKind distinguishes what a key resolves to.
type TargetKind uint8

const (
	// TargetAction is a named action the caller looks up in its registry.
	TargetAction TargetKind = iota
	// TargetMotion is a cursor movement the engine itself understands.
	TargetMotion
)

// Target is what a bound key sequence produces.
type Target struct {
	Kind TargetKind
	Name string
}

// Resolved is one decoded command.
type Resolved struct {
	// Action is set for a TargetAction binding.
	Action string
	// Motion is set for a bare motion, and for the motion half of an operator.
	Motion string
	// Operator, TextObject and Around describe an operator application:
	// `daw` is Operator "delete", TextObject "word", Around true.
	Operator   string
	TextObject string
	Around     bool

	Count    int
	Register rune
	// Arg is the character a motion or action asked for: the `x` in `fx`, the
	// register name in `qa`, the mark in `ma`.
	Arg rune

	// Literal is set in insert mode for a key that inserts a character.
	Literal *keys.Key
	// Keys is the raw sequence that produced this, for macro recording.
	Keys []keys.Key
}

// IsOperator reports whether this resolves to an operator application.
func (r Resolved) IsOperator() bool { return r.Operator != "" }

// EffectiveCount returns the count, defaulting to one.
func (r Resolved) EffectiveCount() int {
	if r.Count <= 0 {
		return 1
	}
	return r.Count
}
