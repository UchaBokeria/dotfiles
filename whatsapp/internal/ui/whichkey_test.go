package ui

import (
	"strings"
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// leaderKey is what every sequence in these tests starts with.
func leaderKey(t *testing.T) keys.Key {
	t.Helper()
	ks := config.Default().Leader()
	if len(ks) != 1 {
		t.Fatalf("the leader is %d keys", len(ks))
	}
	return ks[0]
}

func TestThePopupListsWhatMayFollowTheLeader(t *testing.T) {
	// A half-typed sequence is otherwise invisible: the prompt shows what has
	// been pressed and nothing says what may follow.
	a := newTestApp(t)
	rows := whichKeyRows(a.engine.Keymap(), a.reg, a.engine.Mode(),
		[]keys.Key{leaderKey(t)}, a.wkGroups)

	if len(rows) < 5 {
		t.Fatalf("only %d continuations of the leader", len(rows))
	}
	for _, r := range rows {
		if r.Key == "" || r.Label == "" {
			t.Errorf("a row says nothing: %+v", r)
		}
	}
}

func TestALeafIsLabelledWithWhatItDoes(t *testing.T) {
	a := newTestApp(t)
	rows := whichKeyRows(a.engine.Keymap(), a.reg, a.engine.Mode(),
		[]keys.Key{leaderKey(t)}, a.wkGroups)

	for _, r := range rows {
		if r.Key != "d" {
			continue
		}
		if r.Group {
			t.Fatalf("<leader>d is a group: %+v", r)
		}
		if !strings.Contains(strings.ToLower(r.Label), "download") {
			t.Errorf("label = %q, want the action's own summary", r.Label)
		}
		return
	}
	t.Fatal("<leader>d is not bound in the default keymap")
}

func TestAGroupIsLabelledFromWhatIsUnderIt(t *testing.T) {
	// Bindings share a namespace far more often than not, so a prefix whose
	// children are all "settings.*" can name itself without being told.
	a := newTestApp(t)
	rows := whichKeyRows(a.engine.Keymap(), a.reg, a.engine.Mode(),
		[]keys.Key{leaderKey(t)}, map[string]string{})

	var groups int
	for _, r := range rows {
		if !r.Group {
			continue
		}
		groups++
		if !strings.HasPrefix(r.Label, "+") {
			t.Errorf("group %q is not marked as one", r.Label)
		}
	}
	if groups == 0 {
		t.Fatal("no groups among the leader's continuations")
	}
}

func TestAConfiguredNameWinsForAGroup(t *testing.T) {
	a := newTestApp(t)
	lead := leaderKey(t)
	groups := normalizeGroups(map[string]string{"<leader>s": "settings and keys"},
		config.Default().Leader())
	rows := whichKeyRows(a.engine.Keymap(), a.reg, a.engine.Mode(), []keys.Key{lead}, groups)

	for _, r := range rows {
		if r.Key == "s" {
			if r.Label != "+settings and keys" {
				t.Errorf("label = %q, want the configured name", r.Label)
			}
			return
		}
	}
	t.Fatal("<leader>s is not a group in the default keymap")
}

func TestThePopupFitsItsWidthAndSaysHowToLeave(t *testing.T) {
	a := newTestApp(t)
	pending := []keys.Key{leaderKey(t)}
	rows := whichKeyRows(a.engine.Keymap(), a.reg, a.engine.Mode(), pending, a.wkGroups)

	for _, width := range []int{40, 80, 120} {
		got := whichKeyView(a.styles, width, pending, rows)
		if got == "" {
			t.Fatalf("width %d drew nothing", width)
		}
		for i, line := range strings.Split(got, "\n") {
			if w := render.VisibleWidth(line); w > width {
				t.Errorf("width %d: row %d is %d columns", width, i, w)
			}
		}
		if !strings.Contains(got, "<BS> back") || !strings.Contains(got, "<Esc> close") {
			t.Errorf("width %d: the way out is not shown", width)
		}
	}
}

func TestThePopupIsCappedInHeight(t *testing.T) {
	a := newTestApp(t)
	pending := []keys.Key{leaderKey(t)}
	rows := whichKeyRows(a.engine.Keymap(), a.reg, a.engine.Mode(), pending, a.wkGroups)

	// Narrow enough that everything would want its own row.
	got := whichKeyView(a.styles, 40, pending, rows)
	if n := strings.Count(got, "\n") + 1; n > maxWhichKeyRows+1 {
		t.Errorf("the popup is %d rows tall, cap is %d plus a footer", n, maxWhichKeyRows)
	}
}

func TestAKeyThatIsBothBoundAndAPrefixSaysSo(t *testing.T) {
	// <leader>i toggles the quickfix list and also starts <leader>in. Showing
	// only the action would hide the rest of the tree behind a key that looks
	// like the end of the sequence.
	a := newTestApp(t)
	rows := whichKeyRows(a.engine.Keymap(), a.reg, a.engine.Mode(),
		[]keys.Key{leaderKey(t)}, a.wkGroups)

	for _, r := range rows {
		if r.Key != "i" {
			continue
		}
		if r.Group {
			t.Fatalf("<leader>i is bound, so it is not a bare group: %+v", r)
		}
		if !strings.HasSuffix(r.Label, "…") {
			t.Errorf("label = %q, want a mark that more may follow", r.Label)
		}
		return
	}
	t.Fatal("<leader>i is not bound in the default keymap")
}

func TestGlassIsDecidedByTheSetting(t *testing.T) {
	if !GlassWanted("on") {
		t.Error(`"on" did not turn glass on`)
	}
	if GlassWanted("off") {
		t.Error(`"off" did not turn glass off`)
	}
	// "auto" asks the compositor, and there is none in a test.
	t.Setenv("HYPRLAND_INSTANCE_SIGNATURE", "")
	if GlassWanted("auto") {
		t.Error("auto turned glass on with no compositor to show through")
	}
	if on, why := GlassAvailable(); on || why == "" {
		t.Errorf("GlassAvailable = %v, %q outside Hyprland", on, why)
	}
}

func TestBackspaceAtTheTopShowsEveryKey(t *testing.T) {
	// Space then backspace used to leave a blank screen. The top level is
	// exactly what someone walking backwards out of a group wants to see.
	a := newTestApp(t)
	a.wkDelay = 0
	a.feed(t, "<Space>")
	a.View()
	if a.wkPanel == "" {
		t.Fatal("the leader popup did not open")
	}

	a.feed(t, "<BS>")
	view := a.View()
	if !a.wkRoot {
		t.Fatal("backspace at the top did not open the root list")
	}
	for _, want := range []string{"all keys", "j", "k"} {
		if !strings.Contains(view, want) {
			t.Errorf("the root list does not mention %q:\n%s", want, view)
		}
	}
	// "Tab" sorts past what the first screen shows; paging with ctrl-d is how
	// it, and everything else past the first page, comes into view.
	seen := view
	for i := 0; i < 6; i++ {
		a.feed(t, "<C-d>")
		seen += a.View()
	}
	if !strings.Contains(seen, "Tab") {
		t.Errorf("the root list never mentions %q while paging through it:\n%s", "Tab", seen)
	}
}

func TestTheRootListNamesWhatEveryTopLevelKeyDoes(t *testing.T) {
	a := newTestApp(t)
	a.wkDelay = 0
	a.resize(160, 45)
	a.feed(t, "<Space>")
	a.View()
	a.feed(t, "<BS>")

	// The root has ten times the bindings any group does, past what any
	// screen shows at once, so it is a scroll rather than a one-shot look -
	// paging with ctrl-d covers what fits on the first screen and everything
	// past it besides. The scroll itself keeps climbing past the list's own
	// end (the popup clamps it only when drawing), so this pages a fixed
	// number of times rather than waiting for it to stop moving.
	seen := render.StripEscapes(a.View())
	pages := len(a.engine.Keymap().Children(a.engine.Mode(), nil))/maxInt(1, maxWhichKeyRootRows-1) + 2
	for i := 0; i < pages; i++ {
		a.feed(t, "<C-d>")
		seen += render.StripEscapes(a.View())
	}

	// Every top-level binding of the mode turns up somewhere in the pages
	// seen, whatever it is bound to: this is the answer to "am I missing
	// keys from the menu".
	km := a.engine.Keymap()
	for _, c := range km.Children(a.engine.Mode(), nil) {
		if !strings.Contains(seen, c.Key.String()) {
			t.Errorf("the root list is missing %q", c.Key.String())
		}
	}
}

func TestEscapeClosesTheRootList(t *testing.T) {
	a := newTestApp(t)
	a.wkDelay = 0
	a.feed(t, "<Space>")
	a.View()
	a.feed(t, "<BS>")
	a.feed(t, "<Esc>")
	if a.wkRoot {
		t.Error("escape left the root list up")
	}
	if strings.Contains(a.View(), "all keys") {
		t.Error("the root list is still drawn")
	}
}

func TestAKeyFromTheRootListActsOnIt(t *testing.T) {
	// The list is a prompt, not a mode: pressing a key does what the key does.
	a := newTestApp(t)
	a.wkDelay = 0
	a.feed(t, "<Space>")
	a.View()
	a.feed(t, "<BS>")

	before := a.Focus()
	a.feed(t, "<Tab>")
	if a.wkRoot {
		t.Error("a key press left the root list up")
	}
	if a.Focus() == before {
		t.Error("Tab did nothing")
	}
}

func TestMotionsAreDescribedInWords(t *testing.T) {
	// A motion has no registry entry, and a popup that says "word_end_big"
	// has told the reader nothing.
	a := newTestApp(t)
	a.wkDelay = 0
	a.resize(160, 45)
	a.feed(t, "<Space>")
	a.View()
	a.feed(t, "<BS>")
	view := render.StripEscapes(a.View())

	for _, raw := range []string{"word_end_big", "match_pair", "sentence_prev", "find_char"} {
		if strings.Contains(view, raw) {
			t.Errorf("the root list still shows the raw motion name %q", raw)
		}
	}
	if !strings.Contains(view, "bracket") && !strings.Contains(view, "to the top") {
		t.Errorf("the root list describes no motion in words:\n%s", view)
	}
}

func TestEveryActionHasAKeyAndEveryKeyHasWords(t *testing.T) {
	// Two halves of the same complaint: a menu that misses keys, and a menu
	// that lists a key without saying what it does.
	a := newTestApp(t)

	bound := map[string]bool{}
	for mode, binds := range config.Default().Keys {
		if mode == "motion" || mode == "textobj" {
			continue
		}
		for notation, name := range binds {
			bound[name] = true
			act, ok := a.reg.Lookup(name)
			if !ok {
				t.Errorf("%s %q is bound to %q, which is not an action", mode, notation, name)
				continue
			}
			if act.Summary == "" {
				t.Errorf("%s has no summary, so %q shows a bare name in the menu", name, notation)
			}
		}
	}

	var unbound []string
	for _, name := range a.reg.Names() {
		if !bound[name] {
			unbound = append(unbound, name)
		}
	}
	if len(unbound) > 0 {
		t.Errorf("these actions have no key at all, so nothing in the menu reaches them: %v", unbound)
	}
}

func TestEveryMotionInTheMenuIsDescribed(t *testing.T) {
	// The motions have no registry entry; the popup has its own words for
	// them, and a new one must not slip through as a bare identifier.
	for _, name := range config.Default().Keys["motion"] {
		if _, ok := motionSummaries[name]; !ok {
			t.Errorf("the motion %q has no description for the key menu", name)
		}
	}
}
