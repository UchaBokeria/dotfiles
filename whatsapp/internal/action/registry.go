// Package action is the seam between keymaps and the interface.
//
// Configuration binds a key to an action *name*; the registry is what turns
// that string into behaviour. That indirection is what makes "everything is
// configurable" true by construction: the registry is exactly what :actions
// lists, what the keymap picker enumerates, and what configuration validation
// checks against. A name that is not registered cannot be bound.
package action

import (
	"fmt"
	"sort"
	"strings"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
)

// Context is what an action is given when it runs.
type Context struct {
	// Count is the numeric prefix the user typed, zero when there was none.
	Count int
	// Register is the register prefix, zero when there was none.
	Register rune
	// Arg is the character argument for actions that take one: the mark name
	// in "ma", the register in "@a".
	Arg rune
	// Line is the command-line text, for actions invoked from ":".
	Line string
}

// EffectiveCount is Count, defaulting to one.
func (c Context) EffectiveCount() int {
	if c.Count <= 0 {
		return 1
	}
	return c.Count
}

// Action is one named behaviour.
type Action struct {
	Name    string
	Summary string
	// Modes the action is meaningful in. Empty means every mode, which is
	// right for app.* actions.
	Modes []vim.Mode
	// Repeatable marks an action "." should replay.
	Repeatable bool
	Run        func(Context) error
}

// Registry holds the actions.
type Registry struct {
	byName map[string]Action
	names  []string // sorted; invalidated on registration
}

// NewRegistry returns an empty registry.
func NewRegistry() *Registry {
	return &Registry{byName: map[string]Action{}}
}

// Register adds an action.
//
// It rejects a nil Run at registration rather than at key press: a binding
// that resolves to nothing is a startup problem, and discovering it when the
// user presses the key is far too late.
func (r *Registry) Register(a Action) error {
	switch {
	case a.Name == "":
		return fmt.Errorf("an action needs a name")
	case !strings.Contains(a.Name, "."):
		return fmt.Errorf("%q needs a namespace, as in nav.down", a.Name)
	case a.Run == nil:
		return fmt.Errorf("%q has no Run function", a.Name)
	}
	if _, exists := r.byName[a.Name]; exists {
		return fmt.Errorf("%q is registered twice", a.Name)
	}
	r.byName[a.Name] = a
	r.names = nil
	return nil
}

// MustRegister panics on failure. For the built-in table, where a duplicate or
// a missing Run is a programming error found on the first run.
func (r *Registry) MustRegister(a Action) {
	if err := r.Register(a); err != nil {
		panic("action: " + err.Error())
	}
}

// Lookup finds an action by name.
func (r *Registry) Lookup(name string) (Action, bool) {
	a, ok := r.byName[name]
	return a, ok
}

// Has reports whether a name is registered. This is what configuration
// validation calls.
func (r *Registry) Has(name string) bool {
	_, ok := r.byName[name]
	return ok
}

// Names lists every action, sorted.
func (r *Registry) Names() []string {
	if r.names == nil {
		r.names = make([]string, 0, len(r.byName))
		for name := range r.byName {
			r.names = append(r.names, name)
		}
		sort.Strings(r.names)
	}
	return append([]string{}, r.names...)
}

// ForMode lists the actions meaningful in a mode, sorted by name.
func (r *Registry) ForMode(m vim.Mode) []Action {
	var out []Action
	for _, name := range r.Names() {
		a := r.byName[name]
		if len(a.Modes) == 0 {
			out = append(out, a)
			continue
		}
		for _, am := range a.Modes {
			if am == m {
				out = append(out, a)
				break
			}
		}
	}
	return out
}

// Run looks an action up and runs it.
func (r *Registry) Run(name string, ctx Context) error {
	a, ok := r.byName[name]
	if !ok {
		return fmt.Errorf("%q is not an action (try :actions)", name)
	}
	return a.Run(ctx)
}

// Repeatable reports whether "." should replay this action.
func (r *Registry) Repeatable(name string) bool {
	a, ok := r.byName[name]
	return ok && a.Repeatable
}
