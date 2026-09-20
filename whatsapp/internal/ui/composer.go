package ui

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/charmbracelet/lipgloss"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
)

// maxComposerHeight caps how much of the pane a draft may take, so a long
// message does not squeeze the conversation off the screen.
const maxComposerHeight = 8

// attachGlyph is the paperclip in front of the prompt. Clicking it opens the
// file browser. There is a key for that too, but a button you can see is how
// anyone finds out the feature is there.
const attachGlyph = "📎"

// draft is one chat's unsent message, its edit history, and anything attached
// to it.
type draft struct {
	buf  *vim.Buffer
	undo *vim.Undo
	// attachments are files that go with the next send. They are per draft
	// because a picture pasted into one chat must not follow you into another.
	attachments []string
}

func newDraft() *draft {
	b := vim.NewBuffer()
	return &draft{buf: b, undo: vim.NewUndo(b)}
}

// Composer is the message input.
//
// Each chat keeps its own buffer and its own undo stack: switching away
// mid-sentence and coming back should find the sentence, and pressing u in one
// chat must never rewrite a draft in another.
type Composer struct {
	styles theme.Styles
	width  int

	drafts  map[string]*draft
	current *draft
	chat    domain.JID

	prompt string
}

// NewComposer returns an empty composer.
func NewComposer(st theme.Styles, width int) *Composer {
	c := &Composer{
		styles: st,
		width:  width,
		drafts: map[string]*draft{},
		prompt: "› ",
	}
	c.current = newDraft()
	return c
}

// SwitchDraft moves to a chat's draft, creating one on first visit.
func (c *Composer) SwitchDraft(j domain.JID) {
	if c.chat == j && c.current != nil {
		return
	}
	key := j.String()
	d, ok := c.drafts[key]
	if !ok {
		d = newDraft()
		c.drafts[key] = d
	}
	c.chat = j
	c.current = d
}

// Buffer is the active draft's text buffer.
func (c *Composer) Buffer() *vim.Buffer { return c.current.buf }

// Undo is the active draft's undo stack.
func (c *Composer) Undo() *vim.Undo { return c.current.undo }

// Text is the draft's contents.
func (c *Composer) Text() string { return c.current.buf.Text() }

// Attach adds a file to the next send.
func (c *Composer) Attach(path string) {
	c.current.attachments = append(c.current.attachments, path)
}

// Attachments are the files going with the next send.
func (c *Composer) Attachments() []string { return c.current.attachments }

// ClearAttachments drops them, for a send that went out or was abandoned.
func (c *Composer) ClearAttachments() { c.current.attachments = nil }

// DropAttachment removes the last file added, which is what undoing a paste
// means.
func (c *Composer) DropAttachment() (string, bool) {
	n := len(c.current.attachments)
	if n == 0 {
		return "", false
	}
	last := c.current.attachments[n-1]
	c.current.attachments = c.current.attachments[:n-1]
	return last, true
}

// Empty reports whether there is nothing to send. An attachment counts: a
// picture with no words is a message.
func (c *Composer) Empty() bool {
	return strings.TrimSpace(c.Text()) == "" && len(c.current.attachments) == 0
}

// Take returns the draft and clears it, which is what sending does.
func (c *Composer) Take() string {
	text := c.current.buf.Text()
	c.current.buf.SetText("")
	c.current.buf.SetCursor(vim.Pos{})
	c.drafts[c.chat.String()] = newDraft()
	c.current = c.drafts[c.chat.String()]
	return text
}

// Restore puts text back into the draft, for a send that failed.
func (c *Composer) Restore(text string) {
	c.current.buf.SetText(text)
	c.current.buf.SetCursor(vim.Pos{Line: c.current.buf.Lines() - 1,
		Col: c.current.buf.LineLen(c.current.buf.Lines() - 1)})
}

// Resize sets the width.
func (c *Composer) Resize(width int) { c.width = width }

// gutter is everything drawn to the left of the text: the attach button and
// the prompt. Every width calculation measures this, not the prompt alone.
func (c *Composer) gutter() string {
	if c.styles.Shape == theme.ShapePill {
		// The field's own cap, a space, the paperclip, a space.
		l, _ := c.styles.Shape.Caps()
		return l + " " + c.styles.Icon("attach") + " "
	}
	return attachGlyph + " " + c.prompt
}

// topPadRow is 1 when the pill card draws a blank filled row above the first
// line, which it does whenever it draws a card at all - Height, AttachHit and
// pillView all have to agree on this or a click lands one row off and the
// reported height stops matching what View actually drew.
func (c *Composer) topPadRow() int {
	if c.styles.Shape == theme.ShapePill {
		return 1
	}
	return 0
}

// AttachHit says whether a click at this column, on the composer's row-th row,
// landed on the attach button.
func (c *Composer) AttachHit(x, row int) bool {
	if row != len(c.attachmentLines())+c.topPadRow() || x < 0 {
		return false
	}
	if c.styles.Shape == theme.ShapePill {
		// The cap, the padding and the icon are all the button.
		return x < 4
	}
	return x < render.VisibleWidth(attachGlyph)
}

// Height is how many rows the composer needs, including its prompt.
func (c *Composer) Height() int {
	// The pill card's own blank rows above the first line and below the
	// last: a filled row is still a row, and View draws exactly this many.
	pad := 2 * c.topPadRow()
	n := len(c.wrapped()) + len(c.attachmentLines()) + pad
	if n < 1 {
		n = 1
	}
	if n > maxComposerHeight {
		n = maxComposerHeight
	}
	return n
}

func (c *Composer) wrapped() []string {
	inner := maxInt(1, c.width-render.VisibleWidth(c.gutter()))
	var out []string
	for i := 0; i < c.current.buf.Lines(); i++ {
		out = append(out, render.Wrap(c.current.buf.Line(i), inner)...)
	}
	if len(out) == 0 {
		out = []string{""}
	}
	return out
}

// attachmentLines name the files going with the next send.
//
// They are shown because an attachment is invisible otherwise: a picture
// pasted into the wrong chat, or forgotten and sent with the next sentence,
// is the kind of mistake that cannot be taken back.
func (c *Composer) attachmentLines() []string {
	if len(c.current.attachments) == 0 {
		return nil
	}
	inner := maxInt(1, c.width-render.VisibleWidth(c.gutter()))
	out := make([]string, 0, len(c.current.attachments))
	for _, f := range c.current.attachments {
		label := c.styles.Icon("attach") + " " + filepath.Base(f)
		if fi, err := os.Stat(f); err == nil {
			label += "  " + media.HumanSize(fi.Size())
		}
		out = append(out, render.Truncate(label, inner))
	}
	return out
}

// View renders the composer. showCursor draws a block at the cursor, which the
// caller enables only when the composer has focus.
func (c *Composer) View(showCursor bool) string {
	if c.styles.Shape == theme.ShapePill {
		return c.pillView(showCursor)
	}
	attached := c.attachmentLines()
	lines := c.wrapped()
	if room := maxComposerHeight - len(attached); len(lines) > room && room > 0 {
		lines = lines[len(lines)-room:]
	}

	inner := maxInt(1, c.width-render.VisibleWidth(c.gutter()))
	promptStyle := c.styles.Placeholder
	if showCursor {
		promptStyle = c.styles.FocusEdge
	}

	button := c.styles.MediaChip.Render(attachGlyph) + " "
	blank := strings.Repeat(" ", render.VisibleWidth(c.gutter()))

	var b strings.Builder
	for _, l := range attached {
		b.WriteString(blank)
		b.WriteString(c.styles.MediaChip.Render(render.Pad(l, inner)))
		b.WriteString("\n")
	}
	for i, l := range lines {
		if i > 0 {
			b.WriteString("\n")
		}
		if i == 0 {
			b.WriteString(button + promptStyle.Render(c.prompt))
		} else {
			b.WriteString(blank)
		}
		b.WriteString(c.styles.Composer.Render(render.Pad(render.Truncate(l, inner), inner)))
	}

	if c.Empty() && !showCursor {
		return button + promptStyle.Render(c.prompt) +
			c.styles.Placeholder.Render(render.Pad("write a message", inner))
	}
	return b.String()
}

// CursorColumn is where the terminal cursor should sit, for the caller to
// place it. It is the visual column, prompt included.
func (c *Composer) CursorColumn() int {
	cur := c.current.buf.Cursor()
	line := c.current.buf.Line(cur.Line)
	runes := []rune(line)
	if cur.Col > len(runes) {
		cur.Col = len(runes)
	}
	return render.VisibleWidth(c.gutter()) + render.VisibleWidth(string(runes[:cur.Col]))
}

// DraftCount is how many chats have unsent text, for the status line.
func (c *Composer) DraftCount() int {
	n := 0
	for _, d := range c.drafts {
		if strings.TrimSpace(d.buf.Text()) != "" {
			n++
		}
	}
	return n
}

// pillView draws the input box as a field: a rounded surface the width of the
// conversation, with the paperclip inside it at the left.
//
// It is the one place in the interface you type, and it should look like it.
// A bare prompt character at the bottom of the screen read as a line of the
// conversation that happened to be empty. A multi-line draft is one card, not
// one per line: the edges are drawn by [theme.Styles.Card], the same helper
// the menus and pickers use, so every line but the first and the last gets
// the shape's vertical side rather than a repeated end-cap - a straight wall
// instead of a rounded seam popping in and out of every row.
func (c *Composer) pillView(focused bool) string {
	st := c.styles
	p := st.Palette

	fillHex, iconFg := p.Raised, p.Faint
	if focused {
		fillHex, iconFg = p.RaisedHi, p.Accent
	}
	fill := lipgloss.NewStyle().Foreground(lipgloss.Color(p.Fg)).Background(lipgloss.Color(fillHex))
	icon := lipgloss.NewStyle().Foreground(lipgloss.Color(iconFg)).Background(lipgloss.Color(fillHex))

	// The gutter reserves a cell for the cap Card is about to draw; the
	// prefix built here is that same width minus the cap, so the text still
	// starts exactly where CursorColumn and AttachHit expect it.
	gutterW := render.VisibleWidth(c.gutter())
	iconPrefix := fill.Render(" ") + icon.Render(st.Icon("attach")) + fill.Render(" ")
	blankPrefix := fill.Render(strings.Repeat(" ", maxInt(0, gutterW-1)))

	rowWidth := maxInt(1, c.width-2)
	// Two cells of padding on each side of the text, inside the box, so a
	// draft never sits flush against the edge it is framed by.
	inner := maxInt(1, rowWidth-(gutterW-1)-4)
	open := render.StylePrefix(fill.Render("\u2063"), "\u2063")

	var out []string
	for _, l := range c.attachmentLines() {
		chip := st.Chip(l, p.Link, p.Raised, false)
		out = append(out, strings.Repeat(" ", 2)+chip)
	}

	pad := 2 * c.topPadRow()
	lines := c.wrapped()
	room := maxComposerHeight - len(out) - pad
	if len(lines) > room && room > 0 {
		lines = lines[len(lines)-room:]
	}
	empty := c.Empty() && !focused

	cardRows := make([]string, 0, len(lines)+pad)
	if pad > 0 {
		cardRows = append(cardRows, fill.Render(strings.Repeat(" ", rowWidth)))
	}
	for i, l := range lines {
		content := render.Pad(render.Truncate(l, inner), inner)
		if empty && i == 0 {
			content = st.Placeholder.Background(lipgloss.Color(fillHex)).Render(render.Pad("write a message", inner))
		}
		if open != "" {
			content = render.ReopenAfterResets(content, open)
		}
		prefix := blankPrefix
		if i == 0 {
			prefix = iconPrefix
		}
		row := prefix + fill.Render("  ") + fill.Render(content) + fill.Render("  ")
		cardRows = append(cardRows, render.Pad(render.Truncate(row, rowWidth), rowWidth))
	}
	if pad > 0 {
		cardRows = append(cardRows, fill.Render(strings.Repeat(" ", rowWidth)))
	}
	return strings.Join(append(out, st.Card(cardRows, fillHex)...), "\n")
}

// SetStyles replaces the style set, for a reload.
func (c *Composer) SetStyles(st theme.Styles) { c.styles = st }
