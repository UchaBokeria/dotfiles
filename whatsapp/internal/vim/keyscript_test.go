package vim

import (
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
)

// harness wires the engine to a buffer the way the composer will, so a key
// script exercises the same path the application uses rather than a
// test-only shortcut.
type harness struct {
	t    *testing.T
	e    *Engine
	b    *Buffer
	u    *Undo
	regs *Registers
}

func newHarness(t *testing.T, start string) *harness {
	t.Helper()
	e := testEngine(t)
	b := NewBuffer()
	b.SetText(start)
	b.SetCursor(Pos{0, 0})
	return &harness{t: t, e: e, b: b, u: NewUndo(b), regs: e.regs}
}

func (h *harness) feed(notation string) {
	h.t.Helper()
	for _, key := range keys.MustParse(notation) {
		for _, r := range h.e.Feed(key) {
			h.apply(r)
		}
	}
}

// apply is the miniature of what the composer does with a Resolved.
func (h *harness) apply(r Resolved) {
	switch {
	case r.Literal != nil:
		if ch, ok := r.Literal.Printable(); ok {
			h.b.Insert(string(ch))
		}
		return

	case r.IsOperator():
		h.u.Checkpoint()
		from := h.b.Cursor()
		var span Span
		var ok bool
		if r.TextObject != "" {
			span, ok = TextObject(h.b, r.TextObject, r.Around)
		} else {
			m := Move(h.b, r.Motion, r.EffectiveCount(), r.Arg)
			if !m.Valid && r.Motion != "line" {
				return
			}
			span, ok = SpanForMotion(h.b, m, from), true
		}
		if !ok {
			return
		}
		if Apply(h.b, r.Operator, span, h.regs, r.Register) {
			h.e.SetMode(Insert)
		}
		return

	case r.Motion != "":
		if m := Move(h.b, r.Motion, r.EffectiveCount(), r.Arg); m.Valid {
			h.b.SetCursor(m.To)
		}
		return
	}

	switch r.Action {
	// The real interface routes nav.* to whichever pane has focus. Here the
	// focus is always the buffer, so they are cursor motions.
	case "nav.down":
		if m := Move(h.b, "down", r.EffectiveCount(), 0); m.Valid {
			h.b.SetCursor(m.To)
		}
	case "nav.up":
		if m := Move(h.b, "up", r.EffectiveCount(), 0); m.Valid {
			h.b.SetCursor(m.To)
		}
	case "mode.insert":
		h.u.Checkpoint()
		h.e.SetMode(Insert)
	case "mode.normal":
		h.e.SetMode(Normal)
	case "edit.delete_char":
		h.u.Checkpoint()
		for i := 0; i < r.EffectiveCount(); i++ {
			cur := h.b.Cursor()
			if cur.Col >= h.b.LineLen(cur.Line) {
				break
			}
			h.b.Delete(Span{From: cur, To: cur, Kind: Inclusive})
		}
	case "edit.put_after":
		h.u.Checkpoint()
		Put(h.b, h.regs.Get(r.Register), true)
	case "edit.put_before":
		h.u.Checkpoint()
		Put(h.b, h.regs.Get(r.Register), false)
	case "edit.undo":
		h.u.Undo()
	case "edit.redo":
		h.u.Redo()
	}
}

func run(t *testing.T, start, script string) string {
	t.Helper()
	h := newHarness(t, start)
	h.feed(script)
	return h.b.Text()
}

func TestKeyScripts(t *testing.T) {
	cases := []struct{ name, start, script, want string }{
		{"delete word", "the quick brown", "dw", "quick brown"},
		{"delete two words", "the quick brown fox", "2dw", "brown fox"},
		{"delete with a count on the operator", "a b c d e", "3dw", "d e"},
		{"delete to end of word", "the quick", "de", " quick"},
		{"change inner word", "the quick brown", "wciwslow<Esc>", "the slow brown"},
		{"delete inside quotes", `say "hi" now`, `f"di"`, `say "" now`},
		{"change inside parens", "fn(a, b)", "f(ci(x<Esc>", "fn(x)"},
		{"delete a whole word with a", "the quick brown", "wdaw", "the brown"},
		{"x deletes a character", "abcdef", "x", "bcdef"},
		{"x with a count", "abcdef", "3x", "def"},
		{"delete a line", "one\ntwo\nthree", "jdd", "one\nthree"},
		{"yank and put a word", "one ", "yiwP", "oneone "},
		{"undo a change", "abc", "xxu", "bc"},
		{"redo after undo", "abc", "xxu<C-r>", "c"},
		{"undo everything", "abc", "xxxuuu", "abc"},
		{"dot repeats a word delete", "a b c d", "dw.", "c d"},
		{"uppercase a word", "abc def", "gUiw", "ABC def"},
		{"lowercase a word", "ABC def", "guiw", "abc def"},
		{"insert text", "bc", "ia<Esc>", "abc"},
		{"delete to line end", "hello world", "wd$", "hello "},
		{"delete to line start", "hello world", "wd0", "world"},
		{"find and delete", "a,b,c", "df,", "b,c"},
		{"till and delete", "a,b,c", "dt,", ",b,c"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := run(t, c.start, c.script); got != c.want {
				t.Errorf("start %q, keys %q\n got %q\nwant %q", c.start, c.script, got, c.want)
			}
		})
	}
}

func TestKeyScriptRegisters(t *testing.T) {
	h := newHarness(t, "hello world")
	h.feed(`"ayiw`)
	if got := h.regs.Get('a').Text; got != "hello" {
		t.Errorf("register a = %q, want hello", got)
	}
	// The unnamed register mirrors it, so a bare p still works.
	if got := h.regs.Get('"').Text; got != "hello" {
		t.Errorf("unnamed register = %q", got)
	}
}

func TestKeyScriptYankRegisterSurvivesADelete(t *testing.T) {
	h := newHarness(t, "keep drop")
	h.feed("yiw")  // yank "keep"
	h.feed("wdiw") // delete "drop"
	if got := h.regs.Get('0').Text; got != "keep" {
		t.Errorf("register 0 = %q, want the yank to survive the delete", got)
	}
}

func TestKeyScriptCursorAfterYank(t *testing.T) {
	h := newHarness(t, "the quick brown")
	h.feed("wyiw")
	if got := h.b.Cursor(); got.Col != 4 {
		t.Errorf("cursor after yank = %+v, want the start of the range", got)
	}
}

func TestKeyScriptChangeEntersInsert(t *testing.T) {
	h := newHarness(t, "abc def")
	h.feed("ciw")
	if h.e.Mode() != Insert {
		t.Fatalf("mode after ciw = %v, want Insert", h.e.Mode())
	}
	h.feed("xyz<Esc>")
	if h.b.Text() != "xyz def" {
		t.Errorf("text = %q", h.b.Text())
	}
}

func TestKeyScriptFailedMotionChangesNothing(t *testing.T) {
	// `dw` at the very end has nowhere to go and must not eat the last word.
	h := newHarness(t, "word")
	h.b.SetCursor(Pos{0, 3})
	h.feed("dl")
	if got := h.b.Text(); got != "wor" {
		t.Errorf("text = %q, want the final character removed", got)
	}
	h.feed("dl")
	if got := h.b.Text(); got != "wor" {
		t.Errorf("a motion with nowhere to go changed the text: %q", got)
	}
}

func TestKeyScriptMacroOverText(t *testing.T) {
	h := newHarness(t, "a b c d e")
	h.feed("qqdwq") // record: delete a word
	if got := h.b.Text(); got != "b c d e" {
		t.Fatalf("recording did not perform the edit: %q", got)
	}
	h.feed("2@q")
	if got := h.b.Text(); got != "d e" {
		t.Errorf("after 2@q: %q, want %q", got, "d e")
	}
}
