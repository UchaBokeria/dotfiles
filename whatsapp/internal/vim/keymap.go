package vim

import (
	"fmt"
	"sort"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/keys"
)

// node is one step of a key sequence.
type node struct {
	children map[keys.Key]*node
	target   *Target
}

func newNode() *node { return &node{children: map[keys.Key]*node{}} }

// Keymap holds the bindings for every mode.
//
// One trie per mode carries both action bindings and motion bindings, tagged
// by kind. Keeping them in one structure is what makes prefix detection
// correct: `g` is a prefix of the action `gu` and of the motion `ge`, and two
// separate tries would each conclude, wrongly, that it is unambiguous.
type Keymap struct {
	modes map[Mode]*node
}

// NewKeymap returns an empty keymap.
func NewKeymap() *Keymap {
	return &Keymap{modes: map[Mode]*node{}}
}

// Bind attaches a target to a key sequence. Binding the same sequence twice
// replaces it, which is what :map must do.
func (k *Keymap) Bind(m Mode, seq []keys.Key, t Target) error {
	if len(seq) == 0 {
		return fmt.Errorf("cannot bind an empty key sequence")
	}
	if t.Name == "" {
		return fmt.Errorf("cannot bind %s to nothing", keys.Notation(seq))
	}
	root := k.modes[m]
	if root == nil {
		root = newNode()
		k.modes[m] = root
	}
	cur := root
	for _, key := range seq {
		next := cur.children[key]
		if next == nil {
			next = newNode()
			cur.children[key] = next
		}
		cur = next
	}
	target := t
	cur.target = &target
	return nil
}

// Unbind removes a binding. Intermediate nodes are left in place; they are
// harmless and keeping them avoids a tree walk on every :unmap.
func (k *Keymap) Unbind(m Mode, seq []keys.Key) {
	cur := k.modes[m]
	for _, key := range seq {
		if cur == nil {
			return
		}
		cur = cur.children[key]
	}
	if cur != nil {
		cur.target = nil
	}
}

// Lookup resolves a key sequence.
//
// prefix reports whether a longer sequence starting with these keys exists, so
// the engine knows to wait. Both can be true at once: `g` bound alone while
// `gg` also exists is a match that must still wait for timeoutlen.
func (k *Keymap) Lookup(m Mode, seq []keys.Key) (t Target, prefix bool, ok bool) {
	cur := k.modes[m]
	if cur == nil {
		return Target{}, false, false
	}
	for _, key := range seq {
		cur = cur.children[key]
		if cur == nil {
			return Target{}, false, false
		}
	}
	return targetOf(cur), len(cur.children) > 0, cur.target != nil
}

func targetOf(n *node) Target {
	if n.target == nil {
		return Target{}
	}
	return *n.target
}

// Bindings lists a mode's bindings as notation to target name, for the keymap
// picker and :map with no arguments.
func (k *Keymap) Bindings(m Mode) map[string]Target {
	out := map[string]Target{}
	walkNode(k.modes[m], nil, out)
	return out
}

func walkNode(n *node, prefix []keys.Key, out map[string]Target) {
	if n == nil {
		return
	}
	if n.target != nil {
		out[keys.Notation(prefix)] = *n.target
	}
	// Sorted so the listing is stable between runs.
	ks := make([]keys.Key, 0, len(n.children))
	for key := range n.children {
		ks = append(ks, key)
	}
	sort.Slice(ks, func(i, j int) bool { return ks[i].String() < ks[j].String() })
	for _, key := range ks {
		walkNode(n.children[key], append(append([]keys.Key{}, prefix...), key), out)
	}
}

// Modes lists the modes that have at least one binding.
func (k *Keymap) Modes() []Mode {
	out := make([]Mode, 0, len(k.modes))
	for m := range k.modes {
		out = append(out, m)
	}
	sort.Slice(out, func(i, j int) bool { return out[i] < out[j] })
	return out
}
