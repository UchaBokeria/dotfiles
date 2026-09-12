package vim

import (
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
)

// Motions and actions that consume the next keystroke as an argument. The
// engine has to know these, because it must not try to resolve that keystroke
// as a binding: the `d` in `fd` is a target character, not the delete operator.
var motionsTakingChar = map[string]bool{
	"find_char":      true,
	"find_char_back": true,
	"till_char":      true,
	"till_char_back": true,
}

var actionsTakingChar = map[string]bool{
	"mark.set":          true,
	"mark.jump":         true,
	"mark.jump_exact":   true,
	"macro.record":      true,
	"macro.play":        true,
	"edit.replace_char": true,
}

// operatorFor maps the action a key is bound to onto the operator it starts.
// Operators live in the action table so they can be rebound like anything
// else, but the grammar that follows them belongs to the engine.
var operatorFor = map[string]string{
	"edit.operator_yank":        "yank",
	"edit.operator_delete":      "delete",
	"edit.operator_change":      "change",
	"edit.operator_lower":       "lower",
	"edit.operator_upper":       "upper",
	"edit.operator_toggle_case": "toggle_case",
}

// Options configure the engine.
type Options struct {
	// TimeoutLen is how long an ambiguous prefix waits for more input.
	TimeoutLen time.Duration
	// TextObjects maps a key to a text object name, from keys.textobj.
	TextObjects map[rune]string
}

// Engine turns keystrokes into commands.
//
// Every key travels one path - macro recording, then counts, then a register
// prefix, then the trie - so a replayed macro cannot behave differently from
// the typing that recorded it.
type Engine struct {
	km   *Keymap
	regs *Registers
	opts Options

	mode    Mode
	pending []keys.Key
	count   int
	// countSeen distinguishes "no count" from a count of zero, which matters
	// because a bare `0` is the line-start motion.
	countSeen bool
	register  rune

	// awaiting a character argument
	wantChar bool
	charFor  Resolved

	// operator-pending state
	operator      string
	operatorCount int
	// pendingObject is set once `i` or `a` has been seen in operator-pending
	// mode and the engine is waiting for the object key.
	pendingObject rune

	// macros
	recording    rune
	recorded     []keys.Key
	lastPlayed   rune
	replayDepth  int
	lastRepeat   *Resolved
	suppressFeed bool
}

// NewEngine returns an engine in normal mode.
func NewEngine(km *Keymap, regs *Registers, opts Options) *Engine {
	if opts.TimeoutLen <= 0 {
		opts.TimeoutLen = 300 * time.Millisecond
	}
	return &Engine{km: km, regs: regs, opts: opts, mode: Normal}
}

// Mode reports the current mode.
func (e *Engine) Mode() Mode { return e.mode }

// SetMode changes mode and clears any half-typed command, which is what Esc
// must do.
func (e *Engine) SetMode(m Mode) {
	e.mode = m
	e.reset()
}

// TimeoutLen is how long the caller should wait before calling Timeout.
func (e *Engine) TimeoutLen() time.Duration { return e.opts.TimeoutLen }

// Pending is the partially typed sequence, for the status line.
func (e *Engine) Pending() []keys.Key { return append([]keys.Key{}, e.pending...) }

// PendingCount is the count typed so far, for the status line.
func (e *Engine) PendingCount() int { return e.count }

// Operator is the operator awaiting a motion, if any.
func (e *Engine) Operator() string { return e.operator }

// Registers is the register set, for operators the caller applies itself.
func (e *Engine) Registers() *Registers { return e.regs }

// Keymap is the active keymap, for the help view and :map with no arguments.
func (e *Engine) Keymap() *Keymap { return e.km }

func (e *Engine) reset() {
	e.pending = nil
	e.count = 0
	e.countSeen = false
	e.register = 0
	e.wantChar = false
	e.charFor = Resolved{}
	e.pendingObject = 0
	if e.mode != OpPending {
		e.operator = ""
		e.operatorCount = 0
	}
}

// Feed consumes one keystroke.
//
// It returns zero results when the key extends a pending sequence, one for a
// resolved command, and occasionally more when a macro is replayed.
func (e *Engine) Feed(k keys.Key) []Resolved {
	if e.recording != 0 && !e.suppressFeed {
		e.recorded = append(e.recorded, k)
	}

	if e.wantChar {
		return e.applyChar(k)
	}

	switch e.mode {
	case Insert:
		return e.feedInsert(k)
	case CmdLine, Search:
		return e.feedLine(k)
	case OpPending:
		return e.feedOpPending(k)
	default:
		return e.feedNormal(k)
	}
}

// feedInsert passes printable keys through as literals and resolves the rest
// against the insert keymap, so <Esc> and <C-w> work while `a` inserts an `a`.
func (e *Engine) feedInsert(k keys.Key) []Resolved {
	e.pending = append(e.pending, k)
	target, prefix, ok := e.km.Lookup(Insert, e.pending)
	switch {
	case ok && !prefix:
		r := Resolved{Action: target.Name, Keys: e.pending}
		e.reset()
		return e.finish(r)
	case prefix:
		return nil
	}

	// Not bound. A single printable key inserts itself.
	if len(e.pending) == 1 {
		if r, isPrintable := k.Printable(); isPrintable {
			key := k
			out := Resolved{Literal: &key, Keys: e.pending}
			_ = r
			e.reset()
			return []Resolved{out}
		}
	}
	e.reset()
	return nil
}

// feedLine handles the command line and the search prompt: bound keys act,
// everything printable is text.
func (e *Engine) feedLine(k keys.Key) []Resolved {
	e.pending = append(e.pending, k)
	target, prefix, ok := e.km.Lookup(e.mode, e.pending)
	switch {
	case ok && !prefix:
		r := Resolved{Action: target.Name, Keys: e.pending}
		e.reset()
		return e.finish(r)
	case prefix:
		return nil
	}
	if len(e.pending) == 1 {
		if _, isPrintable := k.Printable(); isPrintable {
			key := k
			out := Resolved{Literal: &key, Keys: e.pending}
			e.reset()
			return []Resolved{out}
		}
	}
	e.reset()
	return nil
}

func (e *Engine) feedNormal(k keys.Key) []Resolved {
	// A count, unless a bare zero with no count already started - that is the
	// line-start motion.
	if len(e.pending) == 0 {
		if d, isDigit := k.Digit(); isDigit && (d != 0 || e.countSeen) {
			e.count = e.count*10 + d
			e.countSeen = true
			return nil
		}
		// A register prefix.
		if e.register == 0 && k.Mods == 0 && k.Special == keys.None && k.Rune == '"' {
			e.wantChar = true
			e.charFor = Resolved{Action: registerPrefixMarker}
			return nil
		}
	}

	e.pending = append(e.pending, k)
	target, prefix, ok := e.km.Lookup(e.mode, e.pending)

	if ok && !prefix {
		return e.dispatch(target)
	}
	if prefix {
		return nil
	}
	// Unbound: drop the sequence rather than guessing.
	e.reset()
	return nil
}

// registerPrefixMarker is an internal sentinel: the `"` prefix consumes the
// next key as a register name rather than producing a command.
const registerPrefixMarker = "\x00register"

// dispatch turns a resolved target into a command, entering operator-pending
// mode or waiting for a character argument when the target calls for it.
func (e *Engine) dispatch(t Target) []Resolved {
	seq := e.pending
	count := e.count
	reg := e.register

	if t.Kind == TargetAction {
		if op, isOperator := operatorFor[t.Name]; isOperator {
			e.operator = op
			e.operatorCount = count
			e.mode = OpPending
			e.pending = nil
			e.count = 0
			e.countSeen = false
			return nil
		}
		r := Resolved{Action: t.Name, Count: count, Register: reg, Keys: seq}
		// `q` while recording stops the recording; it does not ask which
		// register to record into, so it must not wait for a character.
		stopsRecording := t.Name == "macro.record" && e.recording != 0
		if actionsTakingChar[t.Name] && !stopsRecording {
			e.wantChar = true
			e.charFor = r
			e.pending = nil
			return nil
		}
		e.reset()
		return e.finish(r)
	}

	r := Resolved{Motion: t.Name, Count: count, Register: reg, Keys: seq}
	if motionsTakingChar[t.Name] {
		e.wantChar = true
		e.charFor = r
		e.pending = nil
		return nil
	}
	e.reset()
	return e.finish(r)
}

// feedOpPending resolves what an operator applies to: a motion, a text object
// introduced by `i` or `a`, or the operator's own key again for the whole line.
func (e *Engine) feedOpPending(k keys.Key) []Resolved {
	if e.pendingObject != 0 {
		object, known := e.opts.TextObjects[k.Rune]
		around := e.pendingObject == 'a'
		e.pendingObject = 0
		if !known {
			e.abortOperator()
			return nil
		}
		r := Resolved{
			Operator:   e.operator,
			TextObject: object,
			Around:     around,
			Count:      e.operatorCount,
			Register:   e.register,
		}
		e.finishOperator()
		return e.finish(r)
	}

	if len(e.pending) == 0 {
		if d, isDigit := k.Digit(); isDigit && (d != 0 || e.countSeen) {
			e.count = e.count*10 + d
			e.countSeen = true
			return nil
		}
		if k.Mods == 0 && k.Special == keys.None && (k.Rune == 'i' || k.Rune == 'a') {
			e.pendingObject = k.Rune
			return nil
		}
	}

	e.pending = append(e.pending, k)

	// A doubled operator acts on the whole line: dd, yy, cc.
	if target, _, ok := e.km.Lookup(Normal, e.pending); ok {
		if op, isOperator := operatorFor[target.Name]; isOperator && op == e.operator {
			r := Resolved{
				Operator: e.operator,
				Motion:   "line",
				Count:    combineCounts(e.operatorCount, e.count),
				Register: e.register,
			}
			e.finishOperator()
			return e.finish(r)
		}
	}

	target, prefix, ok := e.km.Lookup(OpPending, e.pending)
	if ok && !prefix {
		r := Resolved{
			Operator: e.operator,
			Motion:   target.Name,
			Count:    combineCounts(e.operatorCount, e.count),
			Register: e.register,
		}
		if motionsTakingChar[target.Name] {
			e.wantChar = true
			e.charFor = r
			e.pending = nil
			return nil
		}
		e.finishOperator()
		return e.finish(r)
	}
	if prefix {
		return nil
	}

	// Anything else cancels the operator, as in vim.
	e.abortOperator()
	return nil
}

// combineCounts multiplies the counts either side of an operator: 2d3w deletes
// six words.
func combineCounts(before, after int) int {
	switch {
	case before <= 0 && after <= 0:
		return 0
	case before <= 0:
		return after
	case after <= 0:
		return before
	default:
		return before * after
	}
}

func (e *Engine) finishOperator() {
	e.operator = ""
	e.operatorCount = 0
	e.mode = Normal
	e.reset()
}

func (e *Engine) abortOperator() {
	e.operator = ""
	e.operatorCount = 0
	e.mode = Normal
	e.reset()
}

// applyChar consumes a keystroke that a motion or action was waiting for.
func (e *Engine) applyChar(k keys.Key) []Resolved {
	e.wantChar = false
	pendingFor := e.charFor
	e.charFor = Resolved{}

	// The `"` prefix: this keystroke names a register.
	if pendingFor.Action == registerPrefixMarker {
		if k.Mods == 0 && k.Special == keys.None && k.Rune != 0 {
			e.register = k.Rune
		}
		return nil
	}

	r, isPrintable := k.Printable()
	if !isPrintable {
		// Esc, or anything else with no character: abandon the command.
		if e.mode == OpPending {
			e.abortOperator()
		} else {
			e.reset()
		}
		return nil
	}
	pendingFor.Arg = r

	if pendingFor.Operator != "" {
		e.finishOperator()
	} else {
		e.reset()
	}
	return e.finish(pendingFor)
}

// finish is the last step for every resolved command: it records the command
// for dot-repeat and handles the macro verbs, which the engine owns because
// they operate on the key stream itself.
func (e *Engine) finish(r Resolved) []Resolved {
	switch r.Action {
	case "macro.record":
		return e.handleRecord(r)
	case "macro.play":
		return e.handlePlay(r)
	case "repeat.last":
		return e.handleRepeat(r)
	}
	if isRepeatable(r) {
		copy := r
		e.lastRepeat = &copy
	}
	return []Resolved{r}
}

// isRepeatable reports whether `.` should replay this. Movement is not a
// change, so repeating it would be surprising; operators and edits are.
func isRepeatable(r Resolved) bool {
	if r.Operator != "" {
		return true
	}
	switch r.Action {
	case "edit.delete_char", "edit.substitute_char", "edit.delete_to_end",
		"edit.change_to_end", "edit.put_after", "edit.put_before",
		"edit.replace_char":
		return true
	}
	return false
}

func (e *Engine) handleRecord(r Resolved) []Resolved {
	if e.recording != 0 {
		// The terminating q was appended by Feed; drop it so replay does not
		// stop the recording it just started.
		if n := len(e.recorded); n > 0 {
			e.recorded = e.recorded[:n-1]
		}
		e.regs.SetMacro(e.recording, keys.Notation(e.recorded))
		e.recording = 0
		e.recorded = nil
		return nil
	}
	if r.Arg == 0 {
		return nil
	}
	e.recording = r.Arg
	e.recorded = nil
	return nil
}

// Recording reports the register being recorded into.
func (e *Engine) Recording() (rune, bool) { return e.recording, e.recording != 0 }

const maxReplayDepth = 100

func (e *Engine) handlePlay(r Resolved) []Resolved {
	name := r.Arg
	if name == '@' {
		name = e.lastPlayed
	}
	if name == 0 {
		return nil
	}
	e.lastPlayed = name

	notation := e.regs.Get(name).Text
	if notation == "" {
		return nil
	}
	seq, err := keys.Parse(notation, nil)
	if err != nil {
		return nil
	}

	// A macro that plays itself would recurse forever; vim stops too.
	if e.replayDepth >= maxReplayDepth {
		return nil
	}
	e.replayDepth++
	defer func() { e.replayDepth-- }()

	// Replayed keys must not be recorded into an in-progress recording, or
	// the macro would grow every time it ran.
	wasSuppressed := e.suppressFeed
	e.suppressFeed = true
	defer func() { e.suppressFeed = wasSuppressed }()

	var out []Resolved
	for i := 0; i < r.EffectiveCount(); i++ {
		for _, k := range seq {
			out = append(out, e.Feed(k)...)
		}
	}
	return out
}

func (e *Engine) handleRepeat(r Resolved) []Resolved {
	if e.lastRepeat == nil {
		return nil
	}
	again := *e.lastRepeat
	if r.Count > 0 {
		again.Count = r.Count
	}
	return []Resolved{again}
}

// Timeout resolves a pending sequence that is both a complete binding and the
// prefix of a longer one. The caller calls it when TimeoutLen has elapsed with
// no further key.
func (e *Engine) Timeout() []Resolved {
	if len(e.pending) == 0 {
		return nil
	}
	mode := e.mode
	if mode == OpPending {
		if target, _, ok := e.km.Lookup(OpPending, e.pending); ok {
			r := Resolved{
				Operator: e.operator,
				Motion:   target.Name,
				Count:    combineCounts(e.operatorCount, e.count),
				Register: e.register,
			}
			e.finishOperator()
			return e.finish(r)
		}
		e.abortOperator()
		return nil
	}

	target, _, ok := e.km.Lookup(mode, e.pending)
	if !ok {
		e.reset()
		return nil
	}
	return e.dispatch(target)
}
