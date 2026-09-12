package vim

import (
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
)

func k(notation string) []keys.Key { return keys.MustParse(notation) }

// testEngine builds an engine with a keymap close to the shipped defaults.
func testEngine(t *testing.T) *Engine {
	t.Helper()
	km := NewKeymap()

	actions := map[string]string{
		"j": "nav.down", "k": "nav.up", "gg": "nav.top", "G": "nav.bottom",
		"<C-d>": "nav.half_down", "i": "mode.insert", "<Esc>": "search.clear",
		"y": "edit.operator_yank", "d": "edit.operator_delete",
		"c": "edit.operator_change", "gu": "edit.operator_lower",
		"gU": "edit.operator_upper", "x": "edit.delete_char",
		"p": "edit.put_after", "P": "edit.put_before",
		"u": "edit.undo", "<C-r>": "edit.redo", ".": "repeat.last",
		"q": "macro.record", "@": "macro.play", "m": "mark.set",
		"'": "mark.jump", "<Tab>": "pane.toggle", "ZZ": "app.quit",
	}
	for notation, action := range actions {
		if err := km.Bind(Normal, k(notation), Target{Kind: TargetAction, Name: action}); err != nil {
			t.Fatal(err)
		}
	}
	motions := map[string]string{
		"h": "left", "l": "right", "0": "line_start", "$": "line_end",
		"w": "word_next", "b": "word_prev", "e": "word_end", "ge": "word_end_prev",
		"f": "find_char", "F": "find_char_back", "t": "till_char",
		"%": "match_pair", "gg": "buffer_start", "G": "buffer_end",
	}
	for notation, motion := range motions {
		for _, mode := range []Mode{Normal, OpPending} {
			if err := km.Bind(mode, k(notation), Target{Kind: TargetMotion, Name: motion}); err != nil {
				t.Fatal(err)
			}
		}
	}
	// Normal-mode action bindings win over a motion on the same key.
	for notation, action := range actions {
		km.Bind(Normal, k(notation), Target{Kind: TargetAction, Name: action})
	}
	km.Bind(Insert, k("<Esc>"), Target{Kind: TargetAction, Name: "mode.normal"})
	km.Bind(Insert, k("<CR>"), Target{Kind: TargetAction, Name: "insert.accept"})
	km.Bind(Insert, k("<C-w>"), Target{Kind: TargetAction, Name: "insert.delete_word_back"})

	return NewEngine(km, NewRegisters(nil, false), Options{
		TimeoutLen: 50 * time.Millisecond,
		TextObjects: map[rune]string{
			'w': "word", '"': "quote_double", '(': "paren", 'p': "paragraph",
		},
	})
}

// feed sends notation through the engine and returns everything resolved.
func feed(e *Engine, notation string) []Resolved {
	var out []Resolved
	for _, key := range k(notation) {
		out = append(out, e.Feed(key)...)
	}
	return out
}

func only(t *testing.T, got []Resolved) Resolved {
	t.Helper()
	if len(got) != 1 {
		t.Fatalf("expected exactly one resolved command, got %d: %+v", len(got), got)
	}
	return got[0]
}

func TestLookupDistinguishesPrefixFromMatch(t *testing.T) {
	km := NewKeymap()
	km.Bind(Normal, k("gg"), Target{Kind: TargetAction, Name: "nav.top"})
	km.Bind(Normal, k("gu"), Target{Kind: TargetAction, Name: "edit.operator_lower"})

	if _, prefix, ok := km.Lookup(Normal, k("g")); ok || !prefix {
		t.Error("g should be a prefix, not a match")
	}
	if target, _, ok := km.Lookup(Normal, k("gg")); !ok || target.Name != "nav.top" {
		t.Errorf("gg = %+v, ok=%v", target, ok)
	}
	if _, prefix, ok := km.Lookup(Normal, k("gx")); ok || prefix {
		t.Error("gx is neither a match nor a prefix")
	}
}

func TestBindRejectsNonsense(t *testing.T) {
	km := NewKeymap()
	if err := km.Bind(Normal, nil, Target{Name: "x"}); err == nil {
		t.Error("an empty sequence must be rejected")
	}
	if err := km.Bind(Normal, k("x"), Target{}); err == nil {
		t.Error("binding to an empty target must be rejected")
	}
}

func TestUnbind(t *testing.T) {
	km := NewKeymap()
	km.Bind(Normal, k("x"), Target{Kind: TargetAction, Name: "edit.delete_char"})
	km.Unbind(Normal, k("x"))
	if _, _, ok := km.Lookup(Normal, k("x")); ok {
		t.Error("the binding survived Unbind")
	}
}

func TestSimpleAction(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "j"))
	if r.Action != "nav.down" || r.Count != 0 {
		t.Errorf("resolved = %+v", r)
	}
}

func TestCountAccumulates(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "12j"))
	if r.Action != "nav.down" || r.Count != 12 {
		t.Errorf("resolved = %+v, want nav.down with count 12", r)
	}
}

func TestZeroIsAMotionUnlessACountIsPending(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "0"))
	if r.Motion != "line_start" {
		t.Fatalf("bare 0 = %+v, want the line_start motion", r)
	}

	e = testEngine(t)
	r = only(t, feed(e, "10j"))
	if r.Count != 10 {
		t.Fatalf("10j = %+v, want count 10", r)
	}
}

func TestRegisterPrefix(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "\"ax"))
	if r.Register != 'a' || r.Action != "edit.delete_char" {
		t.Errorf("resolved = %+v", r)
	}
}

func TestMotionFallsThroughWhenNoActionIsBound(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "w"))
	if r.Motion != "word_next" || r.Action != "" {
		t.Errorf("resolved = %+v, want the word_next motion", r)
	}
}

func TestActionWinsOverAMotionOnTheSameKey(t *testing.T) {
	// j is both nav.down and the `down` motion. The interface's action wins,
	// because it is what routes to whichever pane has focus.
	e := testEngine(t)
	r := only(t, feed(e, "j"))
	if r.Action != "nav.down" {
		t.Errorf("resolved = %+v", r)
	}
}

func TestFindCharConsumesItsArgument(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "fx"))
	if r.Motion != "find_char" || r.Arg != 'x' {
		t.Errorf("resolved = %+v", r)
	}
}

func TestFindCharTargetIsNotResolvedAsABinding(t *testing.T) {
	// `fd` must find a 'd', not start the delete operator.
	e := testEngine(t)
	r := only(t, feed(e, "fd"))
	if r.Motion != "find_char" || r.Arg != 'd' {
		t.Fatalf("resolved = %+v", r)
	}
	if e.Mode() != Normal {
		t.Errorf("mode = %v, want Normal", e.Mode())
	}
}

func TestOperatorWithMotion(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "dw"))
	if r.Operator != "delete" || r.Motion != "word_next" {
		t.Errorf("resolved = %+v", r)
	}
	if e.Mode() != Normal {
		t.Errorf("mode after the operator = %v, want Normal", e.Mode())
	}
}

func TestOperatorEntersOperatorPending(t *testing.T) {
	e := testEngine(t)
	if got := feed(e, "d"); len(got) != 0 {
		t.Fatalf("an operator alone resolved to %+v", got)
	}
	if e.Mode() != OpPending {
		t.Errorf("mode = %v, want OpPending", e.Mode())
	}
	if e.Operator() != "delete" {
		t.Errorf("Operator() = %q", e.Operator())
	}
}

func TestOperatorWithTextObject(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "diw"))
	if r.Operator != "delete" || r.TextObject != "word" || r.Around {
		t.Errorf("resolved = %+v, want delete inner word", r)
	}

	e = testEngine(t)
	r = only(t, feed(e, "daw"))
	if !r.Around {
		t.Errorf("daw = %+v, want Around", r)
	}
}

func TestOperatorWithQuoteObject(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "ci\""))
	if r.Operator != "change" || r.TextObject != "quote_double" {
		t.Errorf("resolved = %+v", r)
	}
}

func TestDoubledOperatorIsLinewise(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "dd"))
	if r.Operator != "delete" || r.Motion != "line" {
		t.Errorf("resolved = %+v, want a linewise delete", r)
	}
}

func TestOperatorCountsMultiply(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "2d3w"))
	if r.Count != 6 {
		t.Errorf("2d3w count = %d, want 6", r.Count)
	}
}

func TestOperatorWithACharMotion(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "dfx"))
	if r.Operator != "delete" || r.Motion != "find_char" || r.Arg != 'x' {
		t.Errorf("resolved = %+v", r)
	}
}

func TestEscapeCancelsAnOperator(t *testing.T) {
	e := testEngine(t)
	feed(e, "d")
	if got := feed(e, "<Esc>"); len(got) != 0 {
		t.Errorf("Esc in operator-pending resolved to %+v", got)
	}
	if e.Mode() != Normal || e.Operator() != "" {
		t.Errorf("mode = %v, operator = %q", e.Mode(), e.Operator())
	}
}

func TestUnknownTextObjectCancels(t *testing.T) {
	e := testEngine(t)
	if got := feed(e, "diz"); len(got) != 0 {
		t.Errorf("an unknown text object resolved to %+v", got)
	}
	if e.Mode() != Normal {
		t.Errorf("mode = %v, want Normal", e.Mode())
	}
}

func TestInsertModePassesLiterals(t *testing.T) {
	e := testEngine(t)
	e.SetMode(Insert)

	r := only(t, feed(e, "h"))
	if r.Literal == nil || r.Literal.Rune != 'h' {
		t.Fatalf("resolved = %+v, want a literal h", r)
	}
	r = only(t, feed(e, "<Esc>"))
	if r.Action != "mode.normal" {
		t.Errorf("Esc in insert = %+v", r)
	}
}

func TestInsertModeSpaceIsALiteral(t *testing.T) {
	e := testEngine(t)
	e.SetMode(Insert)
	r := only(t, feed(e, "<Space>"))
	if r.Literal == nil {
		t.Fatalf("space did not insert: %+v", r)
	}
	if got, _ := r.Literal.Printable(); got != ' ' {
		t.Errorf("literal = %q, want a space", got)
	}
}

func TestInsertModeBoundControlKeyIsNotALiteral(t *testing.T) {
	e := testEngine(t)
	e.SetMode(Insert)
	r := only(t, feed(e, "<C-w>"))
	if r.Action != "insert.delete_word_back" || r.Literal != nil {
		t.Errorf("resolved = %+v", r)
	}
}

func TestTimeoutResolvesTheShorterBinding(t *testing.T) {
	km := NewKeymap()
	km.Bind(Normal, k("g"), Target{Kind: TargetAction, Name: "goto"})
	km.Bind(Normal, k("gg"), Target{Kind: TargetAction, Name: "nav.top"})
	e := NewEngine(km, NewRegisters(nil, false), Options{TimeoutLen: time.Millisecond})

	if got := feed(e, "g"); len(got) != 0 {
		t.Fatalf("an ambiguous prefix must wait, got %+v", got)
	}
	r := only(t, e.Timeout())
	if r.Action != "goto" {
		t.Errorf("timeout resolved %+v, want goto", r)
	}
}

func TestTimeoutOnAnIncompletePrefixResolvesNothing(t *testing.T) {
	e := testEngine(t)
	feed(e, "g")
	if got := e.Timeout(); len(got) != 0 {
		t.Errorf("a prefix that is no binding resolved to %+v", got)
	}
}

func TestSetModeClearsAHalfTypedCommand(t *testing.T) {
	e := testEngine(t)
	feed(e, "12")
	e.SetMode(Normal)
	r := only(t, feed(e, "j"))
	if r.Count != 0 {
		t.Errorf("the count survived a mode change: %+v", r)
	}
}

func TestUnboundKeyDropsTheSequence(t *testing.T) {
	e := testEngine(t)
	if got := feed(e, "Z"); len(got) != 0 {
		t.Fatalf("Z alone resolved to %+v", got)
	}
	if got := feed(e, "Q"); len(got) != 0 {
		t.Errorf("ZQ resolved to %+v", got)
	}
	r := only(t, feed(e, "j"))
	if r.Action != "nav.down" {
		t.Errorf("the engine did not recover: %+v", r)
	}
}

func TestMarkTakesACharacter(t *testing.T) {
	e := testEngine(t)
	r := only(t, feed(e, "ma"))
	if r.Action != "mark.set" || r.Arg != 'a' {
		t.Errorf("resolved = %+v", r)
	}
}

func TestMacroRecordAndReplay(t *testing.T) {
	e := testEngine(t)

	if got := feed(e, "qq"); len(got) != 0 {
		t.Fatalf("starting a recording resolved to %+v", got)
	}
	if name, on := e.Recording(); !on || name != 'q' {
		t.Fatalf("Recording() = %q, %v", name, on)
	}

	// The recorded action still happens while recording.
	if r := only(t, feed(e, "x")); r.Action != "edit.delete_char" {
		t.Fatalf("recording suppressed the action: %+v", r)
	}
	if got := feed(e, "q"); len(got) != 0 {
		t.Fatalf("stopping resolved to %+v", got)
	}
	if _, on := e.Recording(); on {
		t.Fatal("still recording after q")
	}

	got := feed(e, "@q")
	if len(got) != 1 || got[0].Action != "edit.delete_char" {
		t.Fatalf("@q produced %+v", got)
	}
}

func TestMacroReplayWithACount(t *testing.T) {
	e := testEngine(t)
	feed(e, "qqxq")
	got := feed(e, "3@q")
	if len(got) != 3 {
		t.Fatalf("3@q produced %d commands, want 3: %+v", len(got), got)
	}
}

func TestAtAtRepeatsTheLastMacro(t *testing.T) {
	e := testEngine(t)
	feed(e, "qqxq")
	feed(e, "@q")
	got := feed(e, "@@")
	if len(got) != 1 || got[0].Action != "edit.delete_char" {
		t.Fatalf("@@ produced %+v", got)
	}
}

func TestRecordingDoesNotCaptureTheTerminatingQ(t *testing.T) {
	// If it did, replaying the macro would start a new recording.
	e := testEngine(t)
	feed(e, "qqxq")
	feed(e, "@q")
	if _, on := e.Recording(); on {
		t.Error("replaying the macro started a recording")
	}
}

func TestReplayedKeysAreNotRecorded(t *testing.T) {
	e := testEngine(t)
	feed(e, "qaxq")  // macro a: x
	feed(e, "qb@aq") // macro b: play a
	// Playing b must run x once, not grow macro b.
	got := feed(e, "@b")
	if len(got) != 1 {
		t.Fatalf("@b produced %d commands, want 1: %+v", len(got), got)
	}
}

func TestSelfPlayingMacroTerminates(t *testing.T) {
	e := testEngine(t)
	// A macro that plays itself. It must stop rather than recurse forever.
	e.regs.SetMacro('r', "@r")
	done := make(chan struct{})
	go func() {
		feed(e, "@r")
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("a self-playing macro did not terminate")
	}
}

func TestDotRepeatsTheLastChange(t *testing.T) {
	e := testEngine(t)
	feed(e, "dw")
	got := feed(e, ".")
	if len(got) != 1 || got[0].Operator != "delete" || got[0].Motion != "word_next" {
		t.Fatalf(". produced %+v", got)
	}
}

func TestDotDoesNotRepeatMovement(t *testing.T) {
	e := testEngine(t)
	feed(e, "dw")
	feed(e, "j") // movement, not a change
	got := feed(e, ".")
	if len(got) != 1 || got[0].Operator != "delete" {
		t.Fatalf("movement clobbered the repeat register: %+v", got)
	}
}

func TestDotWithANewCount(t *testing.T) {
	e := testEngine(t)
	feed(e, "dw")
	got := feed(e, "3.")
	if len(got) != 1 || got[0].Count != 3 {
		t.Fatalf("3. produced %+v", got)
	}
}

func TestDotWithNothingToRepeat(t *testing.T) {
	e := testEngine(t)
	if got := feed(e, "."); len(got) != 0 {
		t.Errorf(". with no prior change produced %+v", got)
	}
}

func TestBindingsListing(t *testing.T) {
	e := testEngine(t)
	got := e.km.Bindings(Normal)
	if got["j"].Name != "nav.down" {
		t.Errorf("bindings listing = %+v", got["j"])
	}
	if got["gg"].Name == "" {
		t.Error("a multi-key binding is missing from the listing")
	}
}
