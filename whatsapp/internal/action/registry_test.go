package action

import (
	"errors"
	"strings"
	"testing"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/vim"
)

func noop(Context) error { return nil }

func TestRegisterAndLookup(t *testing.T) {
	r := NewRegistry()
	if err := r.Register(Action{
		Name: "scroll.half_down", Summary: "half a page down",
		Modes: []vim.Mode{vim.Normal}, Run: noop,
	}); err != nil {
		t.Fatal(err)
	}
	if !r.Has("scroll.half_down") {
		t.Error("Has did not find a registered action")
	}
	if r.Has("scroll.nope") {
		t.Error("Has invented an action")
	}
	if _, ok := r.Lookup("scroll.half_down"); !ok {
		t.Error("Lookup failed")
	}
}

func TestRegisterRejectsBadInput(t *testing.T) {
	r := NewRegistry()
	cases := []struct {
		name string
		a    Action
		want string
	}{
		{"no name", Action{Run: noop}, "name"},
		{"no namespace", Action{Name: "quit", Run: noop}, "namespace"},
		{"no run function", Action{Name: "app.quit"}, "Run"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			err := r.Register(c.a)
			if err == nil {
				t.Fatalf("%+v was accepted", c.a)
			}
			if !strings.Contains(err.Error(), c.want) {
				t.Errorf("err = %v, want it to mention %q", err, c.want)
			}
		})
	}
}

func TestDuplicateRegistrationIsAnError(t *testing.T) {
	r := NewRegistry()
	a := Action{Name: "app.quit", Run: noop}
	if err := r.Register(a); err != nil {
		t.Fatal(err)
	}
	if err := r.Register(a); err == nil {
		t.Fatal("registering the same name twice must fail")
	}
}

func TestNamesAreSorted(t *testing.T) {
	r := NewRegistry()
	for _, n := range []string{"b.z", "a.q", "c.a"} {
		r.Register(Action{Name: n, Run: noop})
	}
	got := r.Names()
	if len(got) != 3 || got[0] != "a.q" || got[1] != "b.z" || got[2] != "c.a" {
		t.Errorf("Names = %v, want sorted", got)
	}
}

func TestNamesReflectLaterRegistrations(t *testing.T) {
	r := NewRegistry()
	r.Register(Action{Name: "a.one", Run: noop})
	_ = r.Names() // populate the cache
	r.Register(Action{Name: "a.two", Run: noop})
	if len(r.Names()) != 2 {
		t.Errorf("the sorted-name cache went stale: %v", r.Names())
	}
}

func TestForMode(t *testing.T) {
	r := NewRegistry()
	r.Register(Action{Name: "n.only", Modes: []vim.Mode{vim.Normal}, Run: noop})
	r.Register(Action{Name: "i.only", Modes: []vim.Mode{vim.Insert}, Run: noop})
	r.Register(Action{Name: "any.mode", Run: noop})

	normal := r.ForMode(vim.Normal)
	if len(normal) != 2 {
		t.Fatalf("normal-mode actions = %d, want 2: %+v", len(normal), normal)
	}
	insert := r.ForMode(vim.Insert)
	if len(insert) != 2 {
		t.Fatalf("insert-mode actions = %d, want 2", len(insert))
	}
}

func TestRunPassesTheContext(t *testing.T) {
	r := NewRegistry()
	var got Context
	r.Register(Action{Name: "x.y", Run: func(c Context) error { got = c; return nil }})

	if err := r.Run("x.y", Context{Count: 5, Register: 'a', Arg: 'z'}); err != nil {
		t.Fatal(err)
	}
	if got.Count != 5 || got.Register != 'a' || got.Arg != 'z' {
		t.Errorf("context = %+v", got)
	}
}

func TestRunOfAnUnknownActionNamesIt(t *testing.T) {
	r := NewRegistry()
	err := r.Run("nope.nope", Context{})
	if err == nil || !strings.Contains(err.Error(), "nope.nope") {
		t.Errorf("err = %v, want it to name the action", err)
	}
}

func TestRunPropagatesTheError(t *testing.T) {
	r := NewRegistry()
	boom := errors.New("boom")
	r.Register(Action{Name: "x.y", Run: func(Context) error { return boom }})
	if err := r.Run("x.y", Context{}); !errors.Is(err, boom) {
		t.Errorf("err = %v, want boom", err)
	}
}

func TestEffectiveCountDefaultsToOne(t *testing.T) {
	if got := (Context{}).EffectiveCount(); got != 1 {
		t.Errorf("EffectiveCount = %d, want 1", got)
	}
	if got := (Context{Count: 7}).EffectiveCount(); got != 7 {
		t.Errorf("EffectiveCount = %d, want 7", got)
	}
}

func TestRepeatable(t *testing.T) {
	r := NewRegistry()
	r.Register(Action{Name: "edit.delete_char", Repeatable: true, Run: noop})
	r.Register(Action{Name: "nav.down", Run: noop})
	if !r.Repeatable("edit.delete_char") {
		t.Error("edit.delete_char should be repeatable")
	}
	if r.Repeatable("nav.down") {
		t.Error("movement should not be repeatable")
	}
	if r.Repeatable("nope") {
		t.Error("an unknown action is not repeatable")
	}
}
