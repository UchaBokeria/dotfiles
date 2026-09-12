package render

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
)

// Delivery glyphs.
const (
	tickPending   = "⧗"
	tickSent      = "✓"
	tickDelivered = "✓✓"
	tickRead      = "✓✓"
	tickFailed    = "✗"
	quoteBar      = "▎"
)

// Options control how a message is drawn.
type Options struct {
	// Width is the whole message pane.
	Width int
	// MaxBubble caps the bubble, so a one-word reply is not stretched across a
	// wide terminal.
	MaxBubble int
	// Timestamp is a Go time layout.
	Timestamp string
	// ShowSender puts a name above messages from other people, which is only
	// useful in a group.
	ShowSender bool
	// Selected draws the cursor marker beside the bubble.
	Selected bool
	Styles   theme.Styles
	// Now is the reference time for "Today" and "Yesterday". The zero value
	// means the wall clock; tests set it so a golden file does not change
	// meaning overnight.
	Now time.Time

	// Media renders an attachment into terminal rows. Nil disables previews,
	// which is what the golden tests want: an image is machine-specific and
	// would pin a photograph into a text fixture.
	Media MediaPreviewer
	// MediaRows caps how tall an inline preview may be, so one photograph
	// cannot push a conversation off the screen.
	MediaRows int
	// Links makes URLs clickable with OSC 8.
	Links bool

	// forceInner pins the wrap width once the box size is settled.
	forceInner int
}

// MediaPreviewer draws an attachment. The renderer knows nothing about image
// formats or ffmpeg; it asks for rows and places them.
type MediaPreviewer interface {
	// PreviewLines returns the rows to draw and a one-line caption. An empty
	// result means there is nothing to show, which is not an error.
	PreviewLines(m domain.Message, cols, rows int) (lines []string, caption string)
}

func (o Options) now() time.Time {
	if o.Now.IsZero() {
		return time.Now()
	}
	return o.Now
}

// withInner overrides the wrap width, so the body is wrapped to the width the
// box actually settled on rather than the theoretical maximum.
func (o Options) withInner(n int) Options {
	o.forceInner = n
	return o
}

func (o Options) innerWidth() int {
	if o.forceInner > 0 {
		return o.forceInner
	}
	// Two border columns and one space of padding on each side.
	max := o.MaxBubble
	if max <= 0 || max > o.Width-2 {
		max = o.Width - 2
	}
	inner := max - 4
	if inner < 1 {
		inner = 1
	}
	return inner
}

// Bubble renders one message.
//
// The time and delivery ticks live on the bottom border rather than on a line
// of their own, so a one-word reply stays three rows tall. For our own
// messages the time sits in the left gutter and the ticks past the right
// corner, which is what makes a glance down the right edge read as "did this
// arrive".
// bubbleProbe is rendered through a style to recover its opening escape
// sequence. Any character does; this one cannot appear in a real body line.
const bubbleProbe = "\x00"

func Bubble(m domain.Message, o Options) []string {
	if o.Width < 8 {
		// Too narrow for a box; a bare line beats a broken one.
		return []string{Truncate(m.Body(), o.Width)}
	}

	stamp := m.TS.Format(layoutOr(o.Timestamp))
	ticks := ""
	if m.FromMe {
		ticks = tickFor(m, o.Styles)
	}

	// Space the footer decorations need outside the box. Reserving it here is
	// what keeps the footer inside the pane: computing the box first and
	// appending afterwards overflows on a wide terminal, where the box grows
	// to the full bubble width and the time has nowhere to go.
	right := ""
	if ticks != "" {
		right = " " + ticks
	}
	reserve := VisibleWidth(right)
	if m.FromMe {
		reserve += VisibleWidth(stamp) + 1
	} else {
		reserve += VisibleWidth(stamp) + 1
	}

	avail := o.Width - reserve - 1 // one column of gutter
	if avail < 6 {
		avail = 6
	}

	inner := measure(bodyLines(m, o), o, avail)
	body := bodyLines(m, o.withInner(inner))

	b := o.Styles.Border
	if b.Top == "" {
		b = theme.New(o.Styles.Palette, "rounded").Border
	}
	boxWidth := inner + 4

	fill := o.Styles.BubbleTheirs
	if m.FromMe {
		fill = o.Styles.BubbleMine
	}

	// A bubble row is drawn in one style, background included, and anything
	// styled inside it ends with a full reset. Without putting the row's own
	// sequence back after each of those, the box loses its colour from the
	// first link, quote or marker onwards - the rest of the line, padding and
	// right border included, is drawn on the terminal's default background.
	if open := StylePrefix(fill.Render(bubbleProbe), bubbleProbe); open != "" {
		for i, l := range body {
			body[i] = ReopenAfterResets(l, open)
		}
	}

	var lines []string
	if !m.FromMe && o.ShowSender && m.SenderName != "" {
		lines = append(lines, " "+o.Styles.SenderStyle(m.SenderName).Render(
			Truncate(m.SenderName, o.Width-1)))
	}

	// A solid bubble's top and bottom rows are half blocks in the bubble's own
	// colour on the terminal's background. Drawn with the fill as their
	// background instead, as a framed bubble's are, the half the glyph leaves
	// empty is filled anyway and the soft edge becomes a square one.
	edge := fill
	if o.Styles.Solid {
		edge = lipgloss.NewStyle().Foreground(fill.GetBackground())
	}
	top := edge.Render(b.TopLeft + strings.Repeat(b.Top, inner+2) + b.TopRight)
	bottom := edge.Render(b.BottomLeft + strings.Repeat(b.Bottom, inner+2) + b.BottomRight)

	if !m.FromMe {
		lines = append(lines, " "+top)
		for _, l := range body {
			lines = append(lines, " "+fill.Render(b.Left+" "+Pad(l, inner)+" "+b.Right))
		}
		lines = append(lines, " "+bottom+" "+o.Styles.Timestamp.Render(stamp))
		return lines
	}

	pad := o.Width - boxWidth - VisibleWidth(right)
	if pad < 0 {
		pad = 0
	}
	prefix := strings.Repeat(" ", pad)

	lines = append(lines, prefix+top)
	for _, l := range body {
		lines = append(lines, prefix+fill.Render(b.Left+" "+Pad(l, inner)+" "+b.Right))
	}

	footerLeft := prefix
	if stampCell := VisibleWidth(stamp) + 1; pad >= stampCell {
		footerLeft = PadLeft(o.Styles.Timestamp.Render(stamp)+" ", pad)
	}
	lines = append(lines, footerLeft+bottom+right)
	return lines
}

// measure picks the bubble's inner width: the widest body line, capped by both
// the configured maximum and the space actually available.
//
// Half-block image rows are measured by counting their cells rather than by
// VisibleWidth: every cell carries two colour escapes, and although those are
// stripped for measurement, doing it per row of a photograph is the one place
// where the cost shows.
func measure(body []string, o Options, avail int) int {
	inner := 0
	for _, l := range body {
		w := VisibleWidth(l)
		if n := strings.Count(l, "▀"); n > 0 {
			w = n
		}
		if w > inner {
			inner = w
		}
	}
	max := o.innerWidth()
	if cap := avail - 4; cap < max {
		max = cap
	}
	if inner > max {
		inner = max
	}
	if inner < 1 {
		inner = 1
	}
	return inner
}

func layoutOr(l string) string {
	if l == "" {
		return "15:04"
	}
	return l
}

func tickFor(m domain.Message, s theme.Styles) string {
	switch m.Delivery {
	case domain.Pending:
		return s.TickPending.Render(tickPending)
	case domain.Sent:
		return s.TickSent.Render(tickSent)
	case domain.Delivered:
		return s.TickDelivered.Render(tickDelivered)
	case domain.Read:
		return s.TickRead.Render(tickRead)
	case domain.Failed:
		return s.TickFailed.Render(tickFailed)
	}
	return ""
}

// bodyLines builds the wrapped contents of a bubble: the quoted reply, the
// media chip, the text, and any markers.
func bodyLines(m domain.Message, o Options) []string {
	inner := o.innerWidth()
	var out []string

	if m.Revoked {
		return styleAll(Wrap("this message was deleted", inner), o.Styles.Placeholder)
	}
	if m.Unsupported {
		return styleAll(Wrap("a message wa cannot show - open it on your phone", inner),
			o.Styles.Placeholder)
	}

	if m.QuotedID != "" {
		quoted := m.QuotedText
		if quoted == "" {
			quoted = "…"
		}
		for _, l := range Wrap(quoted, inner-2) {
			out = append(out, o.Styles.Quote.Render(quoteBar+" "+l))
		}
	}

	if m.HasMedia() {
		// The preview first, then the chip naming the file: the picture is
		// what the eye wants, the filename is what the hand needs.
		if o.Media != nil {
			rows := o.MediaRows
			if rows <= 0 {
				rows = 10
			}
			if lines, caption := o.Media.PreviewLines(m, inner, rows); len(lines) > 0 {
				out = append(out, lines...)
				if caption != "" {
					out = append(out, o.Styles.Timestamp.Render(caption))
				}
			}
		}
		// Wrapped, not just appended: a long filename plus a size is easily
		// wider than a narrow bubble, and an overflowing line breaks the box.
		out = append(out, styleAll(Wrap(mediaChip(*m.Media), inner), o.Styles.MediaChip)...)
	}

	if body := m.Body(); body != "" {
		if o.Links {
			for _, runs := range WrapLinks(body, inner) {
				out = append(out, o.renderRuns(runs))
			}
		} else {
			out = append(out, Wrap(body, inner)...)
		}
	}

	if m.Edited {
		out = append(out, styleAll(Wrap("(edited)", inner), o.Styles.Placeholder)...)
	}
	// Reactions sit under the message they are on, as a chip. wacli stores
	// each one as a message of its own; drawing them that way put a bubble
	// saying "Reacted 👍 to message" on top of the conversation.
	if chips := m.ReactionSummary(); len(chips) > 0 {
		out = append(out, styleAll(Wrap(strings.Join(chips, " "), inner), o.Styles.Reaction)...)
	}
	if len(out) == 0 {
		out = []string{""}
	}
	return out
}

// renderRuns turns one wrapped line back into a string, making the URLs
// clickable and colouring them.
//
// The escape sequence is emitted whatever the terminal is: one that does not
// understand OSC 8 ignores it and shows the text unchanged, so there is
// nothing to detect and nothing to get wrong.
func (o Options) renderRuns(runs []Run) string {
	var b strings.Builder
	for _, r := range runs {
		if r.URL == "" {
			b.WriteString(r.Text)
			continue
		}
		b.WriteString(Hyperlink(r.URL, underlineOn+o.Styles.Link.Render(r.Text)))
	}
	return b.String()
}

// styleAll applies a style to each already-wrapped line. Wrapping has to come
// first: the escape codes a style adds are invisible but not free to a
// character-counting wrap.
func styleAll(lines []string, st lipgloss.Style) []string {
	out := make([]string, len(lines))
	for i, l := range lines {
		out[i] = st.Render(l)
	}
	return out
}

// mediaChip names an attachment under whatever preview was drawn for it: the
// picture is what the eye wants, the filename and size are what the hand
// needs before deciding to download or open it.
func mediaChip(m domain.MediaRef) string {
	icon := "📎"
	switch m.Type {
	case "image":
		icon = "🖼"
	case "video":
		icon = "🎬"
	case "audio":
		icon = "🎵"
	case "sticker":
		icon = "🏷"
	case "document":
		icon = "📄"
	}
	name := m.Filename
	if name == "" {
		name = m.Type
	}
	if m.Length > 0 {
		return fmt.Sprintf("%s %s  %s", icon, name, humanSize(m.Length))
	}
	return fmt.Sprintf("%s %s", icon, name)
}

func humanSize(n int64) string {
	const unit = 1024
	if n < unit {
		return fmt.Sprintf("%dB", n)
	}
	div, exp := int64(unit), 0
	for v := n / unit; v >= unit; v /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f%cB", float64(n)/float64(div), "KMGT"[exp])
}

// DaySeparator is the divider drawn between calendar days.
func DaySeparator(t time.Time, o Options, layout string) string {
	if layout == "" {
		layout = "Monday, 2 January 2006"
	}
	label := " " + t.Format(layout) + " "
	if s := relativeDay(t, o.now()); s != "" {
		label = " " + s + " "
	}
	width := o.Width
	rule := width - VisibleWidth(label)
	if rule < 2 {
		return o.Styles.DaySep.Render(Truncate(label, width))
	}
	left := rule / 2
	right := rule - left
	return o.Styles.DaySep.Render(
		strings.Repeat("─", left) + label + strings.Repeat("─", right))
}

// relativeDay names today and yesterday, which is how the phone app reads.
func relativeDay(t, now time.Time) string {
	y, m, d := now.Date()
	today := time.Date(y, m, d, 0, 0, 0, 0, now.Location())
	switch {
	case !t.Before(today):
		return "Today"
	case !t.Before(today.AddDate(0, 0, -1)):
		return "Yesterday"
	}
	return ""
}
