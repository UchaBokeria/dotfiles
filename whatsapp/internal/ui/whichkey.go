package ui

import (
	"fmt"
	"sort"
	"strings"

	"github.com/charmbracelet/lipgloss"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/action"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
)

// The key popup.
//
// A key sequence under way is invisible: the prompt shows what has been
// pressed, and nothing says what may follow. Every binding is discoverable
// with <leader>? , but a list of two hundred is a reference, not a prompt -
// the question in the moment is "I pressed the leader, now what", and the
// answer is the handful of keys that continue this particular sequence.
//
// It is the same idea as which-key: show the continuations, label the groups,
// and let backspace walk back out of one.

// maxWhichKeyRows caps the popup so a prefix with many bindings cannot take
// the conversation off the screen.
const maxWhichKeyRows = 8

// maxWhichKeyRootRows is the cap for the whole top level, which has ten times
// as many keys as any group under it and is worth more of the screen.
const maxWhichKeyRootRows = 16

// minBodyRows is how much of the conversation the popup always leaves.
const minBodyRows = 2

// whichKeyEntry is one key that may be pressed next.
type whichKeyEntry struct {
	Key   string
	Label string
	Group bool
}

// whichKeyRows lists what may follow the pending sequence.
//
// Labels come from the action registry, which already carries a one-line
// summary of everything bindable, so the popup describes what a key does
// rather than naming the function it calls.
func whichKeyRows(km *vim.Keymap, reg *action.Registry, mode vim.Mode,
	pending []keys.Key, groups map[string]string) []whichKeyEntry {

	children := km.Children(mode, pending)
	if len(children) == 0 {
		return nil
	}

	out := make([]whichKeyEntry, 0, len(children))
	for _, c := range children {
		seq := append(append([]keys.Key{}, pending...), c.Key)
		e := whichKeyEntry{Key: c.Key.String(), Group: c.Group && c.Target.Name == ""}

		switch {
		case e.Group:
			e.Label = "+" + groupLabel(km, mode, seq, groups)
		case c.Target.Name != "":
			e.Label = describeTarget(reg, c.Target)
			if c.Group {
				// Bound and a prefix at once: it does this now, and more
				// follows if you keep typing. Saying only the first would
				// hide the rest of the tree behind a key that looks final.
				e.Label += " …"
			}
		default:
			e.Label = "+" + groupLabel(km, mode, seq, groups)
			e.Group = true
		}
		out = append(out, e)
	}
	return out
}

// describeTarget is what a bound key does, in a few words.
func describeTarget(reg *action.Registry, t vim.Target) string {
	if reg != nil {
		if a, ok := reg.Lookup(t.Name); ok && a.Summary != "" {
			return a.Summary
		}
	}
	// A motion is not an action and has no summary in the registry, so the
	// popup would otherwise list "word_end_big" and leave the reader to guess.
	if s, ok := motionSummaries[t.Name]; ok {
		return s
	}
	return t.Name
}

// motionSummaries are the words for the motions, which the registry does not
// carry because a motion is not an action.
var motionSummaries = map[string]string{
	"left":                "left",
	"right":               "right",
	"up":                  "up",
	"down":                "down",
	"line_start":          "to the start of the line",
	"line_first_nonblank": "to the first non-blank",
	"line_end":            "to the end of the line",
	"word_next":           "forward a word",
	"word_next_big":       "forward a WORD",
	"word_prev":           "back a word",
	"word_prev_big":       "back a WORD",
	"word_end":            "to the end of the word",
	"word_end_big":        "to the end of the WORD",
	"word_end_prev":       "back to the end of a word",
	"find_char":           "to the next character you type",
	"find_char_back":      "back to the character you type",
	"till_char":           "up to the next character you type",
	"till_char_back":      "back up to the character you type",
	"repeat_find":         "repeat that character search",
	"repeat_find_reverse": "repeat it backwards",
	"match_pair":          "to the matching bracket",
	"sentence_prev":       "back a sentence",
	"sentence_next":       "forward a sentence",
	"paragraph_prev":      "back a paragraph",
	"paragraph_next":      "forward a paragraph",
	"buffer_start":        "to the top",
	"buffer_end":          "to the bottom",
}

// groupLabel names a prefix.
//
// A name from the configuration wins. Failing that the label is taken from
// what is underneath: bindings share a namespace far more often than not, so
// "media.download" and "media.open" under one prefix make it "+media" without
// anybody having to say so.
func groupLabel(km *vim.Keymap, mode vim.Mode, seq []keys.Key, groups map[string]string) string {
	if name, ok := groups[keys.Notation(seq)]; ok && name != "" {
		return name
	}
	if ns := commonNamespace(km, mode, seq); ns != "" {
		return ns
	}
	return "more"
}

// commonNamespace is the part before the dot that every action under a prefix
// shares, or empty when they disagree.
func commonNamespace(km *vim.Keymap, mode vim.Mode, seq []keys.Key) string {
	names := actionNames(km, mode, seq, 0)
	if len(names) == 0 {
		return ""
	}
	first := ""
	for _, n := range names {
		ns := n
		if dot := strings.IndexByte(n, '.'); dot > 0 {
			ns = n[:dot]
		}
		if first == "" {
			first = ns
			continue
		}
		if ns != first {
			return ""
		}
	}
	return first
}

// actionNames collects the actions bound anywhere under a prefix. The depth
// limit is a guard against a keymap that somehow contains a cycle; a trie
// cannot, but the recursion is cheap to bound and expensive to debug.
func actionNames(km *vim.Keymap, mode vim.Mode, seq []keys.Key, depth int) []string {
	if depth > 8 {
		return nil
	}
	var out []string
	for _, c := range km.Children(mode, seq) {
		if c.Target.Name != "" {
			out = append(out, c.Target.Name)
		}
		if c.Group {
			out = append(out, actionNames(km, mode, append(append([]keys.Key{}, seq...), c.Key), depth+1)...)
		}
	}
	return out
}

// normalizeGroups rewrites configured prefixes into the notation the keymap
// itself uses.
//
// A prefix is written "<leader>s" in the configuration, because that is how
// every other binding is written there, but the trie has resolved the leader
// by the time a popup asks about it and calls the same prefix "<Space>s".
// Without this the name is simply never found.
func normalizeGroups(groups map[string]string, leader []keys.Key) map[string]string {
	out := make(map[string]string, len(groups))
	for prefix, name := range groups {
		key := prefix
		if parsed, err := keys.Parse(prefix, leader); err == nil {
			key = keys.Notation(parsed)
		}
		out[key] = name
	}
	return out
}

// whichKeyView draws the popup: one key per row, then a line saying what has
// been pressed and how to get out.
func whichKeyView(st theme.Styles, width int, pending []keys.Key, rows []whichKeyEntry) string {
	return whichKeyViewRows(st, width, maxWhichKeyRows, 0, pending, rows)
}

// whichKeyViewRows is whichKeyView with the row cap the screen allows and the
// popup's own scroll position, for a group with more continuations than fit.
func whichKeyViewRows(st theme.Styles, width, maxRows, scroll int, pending []keys.Key, rows []whichKeyEntry) string {
	return whichKeyListView(st, width, maxRows, scroll, rows,
		" "+keys.Notation(pending)+" »", "<BS> back  <Esc> close ")
}

// whichKeyListView draws the popup someone is actually watching mid-sequence:
// one key per row with the label in full, and a scroll rather than more
// columns when there are more continuations than the screen has room for.
// Columns saved height at the cost of cutting every label to a quarter of
// the width; a scroll costs a keystroke instead of the words that say what a
// key does.
func whichKeyListView(st theme.Styles, width, maxRows, scroll int, rows []whichKeyEntry, left, right string) string {
	if width < 20 || len(rows) == 0 {
		return ""
	}
	sorted := append([]whichKeyEntry{}, rows...)
	sort.SliceStable(sorted, func(i, j int) bool {
		if sorted[i].Group != sorted[j].Group {
			return sorted[i].Group
		}
		return sorted[i].Key < sorted[j].Key
	})

	card := st.Shape != theme.ShapeSquare
	if card {
		width -= 2
	}

	maxScroll := maxInt(0, len(sorted)-maxRows)
	scroll = clampInt(scroll, 0, maxScroll)
	visible := sorted[scroll:]
	if len(visible) > maxRows {
		visible = visible[:maxRows]
	}

	var b strings.Builder
	for i, r := range visible {
		if i > 0 {
			b.WriteString("\n")
		}
		key := st.StatusKey.Render(" " + r.Key + " ")
		if card {
			key = st.ChipOn(r.Key, st.Palette.Accent, st.Palette.RaisedHi, st.Palette.Raised, true)
		}
		labelRoom := maxInt(4, width-render.VisibleWidth(key)-2)
		line := key + " " + labelStyle(st, r).Render(render.Truncate(r.Label, labelRoom))
		b.WriteString(st.Picker.Render(render.Pad(render.Truncate(line, width), width)))
	}

	// The scroll position is worth a mention, but never at the cost of
	// dropping how to get out: on a narrow terminal a long one is worse than
	// none.
	footRight := right
	if maxScroll > 0 {
		long := fmt.Sprintf("%d-%d/%d  <C-d>/<C-u> scroll  %s",
			scroll+1, scroll+len(visible), len(sorted), right)
		short := fmt.Sprintf("%d/%d  %s", scroll/maxRows+1, maxScroll/maxRows+1, right)
		switch {
		case render.VisibleWidth(left)+render.VisibleWidth(long) < width:
			footRight = long
		case render.VisibleWidth(left)+render.VisibleWidth(short) < width:
			footRight = short
		}
	}

	b.WriteString("\n")
	b.WriteString(whichKeyFooter(st, width, left, footRight))
	if !card {
		return b.String()
	}
	panel := strings.Split(b.String(), "\n")
	return strings.Join(st.Card(panel, st.Palette.Raised), "\n")
}

// whichKeyPanel lays the keys out in columns under a footer.
func whichKeyPanel(st theme.Styles, width int, rows []whichKeyEntry, maxRows int,
	left, right string) string {

	if width < 20 || len(rows) == 0 {
		return ""
	}

	// Groups first, then leaves, each alphabetically: the shape of the list
	// stays put as a sequence is typed deeper, which is what makes it
	// readable at a glance rather than a thing to re-read.
	sorted := append([]whichKeyEntry{}, rows...)
	sort.SliceStable(sorted, func(i, j int) bool {
		if sorted[i].Group != sorted[j].Group {
			return sorted[i].Group
		}
		return sorted[i].Key < sorted[j].Key
	})

	card := st.Shape != theme.ShapeSquare
	if card {
		// The card's own two edge columns.
		width -= 2
	}
	cells := make([]string, 0, len(sorted))
	widest := 0
	for _, r := range sorted {
		key := st.StatusKey.Render(" " + r.Key + " ")
		if card {
			key = st.ChipOn(r.Key, st.Palette.Accent, st.Palette.RaisedHi, st.Palette.Raised, true)
		}
		// The label is cut to fit, never the key: a chip that loses its right
		// cap reads as a broken shape, and the key is the part being looked
		// for.
		labelRoom := maxInt(4, width/4-render.VisibleWidth(key)-2)
		cell := key + " " + labelStyle(st, r).Render(render.Truncate(r.Label, labelRoom))
		cells = append(cells, cell)
		if w := render.VisibleWidth(cell); w > widest {
			widest = w
		}
	}

	// As many columns as fit at the natural width, then as many as the row cap
	// demands - and the columns are re-measured afterwards, because forcing a
	// fourth column into a three-column width is what cuts the last one in
	// half rather than making the others narrower.
	perCol := widest + 2
	cols := maxInt(1, width/maxInt(perCol, 1))
	rowsNeeded := (len(cells) + cols - 1) / cols
	if rowsNeeded > maxRows {
		rowsNeeded = maxRows
		cols = (len(cells) + rowsNeeded - 1) / rowsNeeded
	}
	if cols*perCol > width {
		perCol = maxInt(12, width/maxInt(cols, 1))
	}

	var b strings.Builder
	for r := 0; r < rowsNeeded; r++ {
		if r > 0 {
			b.WriteString("\n")
		}
		var line strings.Builder
		for c := 0; c < cols; c++ {
			i := c*rowsNeeded + r
			if i >= len(cells) {
				break
			}
			line.WriteString(render.Pad(render.Truncate(cells[i], perCol-1), perCol))
		}
		b.WriteString(st.Picker.Render(render.Pad(render.Truncate(line.String(), width), width)))
	}

	b.WriteString("\n")
	b.WriteString(whichKeyFooter(st, width, left, right))
	if !card {
		return b.String()
	}
	// Inside a card the rows sit on the raised fill, with the card's rounded
	// ends outside them; the footer is the card's last row.
	panel := strings.Split(b.String(), "\n")
	return strings.Join(st.Card(panel, st.Palette.Raised), "\n")
}

// whichKeyRootView draws every key of the current mode: what backspace shows
// after it has walked out of the last group, and the one list that answers
// "what does j do here" without leaving what you were doing.
func whichKeyRootView(st theme.Styles, width, maxRows int, mode vim.Mode, rows []whichKeyEntry) string {
	return whichKeyPanel(st, width, rows, maxRows,
		" all keys · "+strings.ToLower(mode.String())+" mode »", "<Esc> close ")
}

func labelStyle(st theme.Styles, r whichKeyEntry) lipgloss.Style {
	if r.Group {
		return st.ListFilter
	}
	return st.ListSnip
}

// whichKeyFooter says where you are and how to leave.
func whichKeyFooter(st theme.Styles, width int, left, right string) string {
	gap := width - render.VisibleWidth(left) - render.VisibleWidth(right)
	if gap < 1 {
		return st.Status.Render(render.Pad(render.Truncate(left, width), width))
	}
	return st.Status.Render(st.ListTitle.Render(left) +
		strings.Repeat(" ", gap) + st.ListTime.Render(right))
}
