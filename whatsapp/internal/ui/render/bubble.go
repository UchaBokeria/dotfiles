package render

import (
	"fmt"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

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
	// markGlyph is the multi-selection tick, in the gutter.
	markGlyph = "✓"
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
	// Marked says this message is one of a multi-selection, which is drawn as
	// a tick in the gutter: a selection you cannot see is one you act on by
	// accident.
	Marked bool
	Styles theme.Styles
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
	// Highlight is the search pattern to mark inside the text, empty for
	// none. Searching that only moves a cursor makes you hunt for the word
	// that matched; marking it is the whole point of searching.
	Highlight string
	// HighlightFold matches the pattern regardless of case, following the
	// same rule the search itself used.
	HighlightFold bool
	// HighlightCur marks this message as the match the search is sitting on,
	// so the one you jumped to is not the same colour as the seven others on
	// screen.
	HighlightCur bool

	// Padding is the space inside a bubble between its edge and the text.
	Padding int
	// CardEdges is how a bubble of several rows draws its sides: "half" (the
	// default) caps the first and last rows and gives the rows between
	// half-block sides; "ends" keeps those sides full width; "all" caps every
	// row. Chosen by eye in the terminal: "ends" steps at every corner and
	// "all" scallops, where "half" reads as one rounded card.
	CardEdges string

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
	if o.Styles.Shape == theme.ShapePill {
		return pillBubble(m, o)
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
	// The selected message says so with its own edge. A cursor in a gutter is
	// easy to lose in a wall of bubbles, and the eye is already on the bubble.
	if o.Selected {
		if o.Styles.Solid {
			edge = lipgloss.NewStyle().Foreground(o.Styles.BubbleSel.GetForeground())
		} else {
			edge = fill.Foreground(o.Styles.BubbleSel.GetForeground())
		}
	}
	top := edge.Render(b.TopLeft + strings.Repeat(b.Top, inner+2) + b.TopRight)
	bottom := edge.Render(b.BottomLeft + strings.Repeat(b.Bottom, inner+2) + b.BottomRight)

	// A multi-selected message wears a tick in the gutter beside its first
	// row. Marks that cannot be seen are marks acted on by accident.
	mark := " "
	if o.Marked {
		mark = o.Styles.BubbleSel.Render(markGlyph)
	}

	if !m.FromMe {
		lines = append(lines, mark+top)
		for _, l := range body {
			lines = append(lines, " "+fill.Render(b.Left+" "+Pad(l, inner)+" "+b.Right))
		}
		lines = append(lines, " "+bottom+" "+o.Styles.Timestamp.Render(stamp))
		return fitWidth(lines, o.Width)
	}

	pad := o.Width - boxWidth - VisibleWidth(right)
	if pad < 0 {
		pad = 0
	}
	prefix := strings.Repeat(" ", pad)

	firstPrefix := prefix
	if o.Marked && pad > 0 {
		firstPrefix = mark + strings.Repeat(" ", pad-1)
	}
	lines = append(lines, firstPrefix+top)
	for _, l := range body {
		lines = append(lines, prefix+fill.Render(b.Left+" "+Pad(l, inner)+" "+b.Right))
	}

	footerLeft := prefix
	if stampCell := VisibleWidth(stamp) + 1; pad >= stampCell {
		footerLeft = PadLeft(o.Styles.Timestamp.Render(stamp)+" ", pad)
	}
	lines = append(lines, footerLeft+bottom+right)
	return fitWidth(lines, o.Width)
}

// fitWidth is the last word on a bubble's width. At the narrowest widths the
// box, the time and the ticks together need more room than there is, and a
// row one column too wide wraps in the terminal and shoves every row under it
// down a line. Cutting the overflow keeps the layout; it only ever triggers
// where the pane is too narrow to read anyway.
func fitWidth(lines []string, width int) []string {
	for i, l := range lines {
		if VisibleWidth(l) > width {
			lines[i] = Truncate(l, width)
		}
	}
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
		out = append(out, styleAll(Wrap(mediaChip(*m.Media, o.Styles), inner), o.Styles.MediaChip)...)
	}

	if body := m.Body(); body != "" {
		if o.Links {
			for _, runs := range WrapLinks(body, inner) {
				out = append(out, o.renderRuns(runs))
			}
		} else {
			for _, l := range Wrap(body, inner) {
				out = append(out, o.markMatches(l))
			}
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
			b.WriteString(o.markMatches(r.Text))
			continue
		}
		// A match inside a URL is left alone: the link is already coloured and
		// already whole, and splicing a second style through the middle of it
		// is how you end up with a half-underlined address.
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
func mediaChip(m domain.MediaRef, st theme.Styles) string {
	// Icons from the configured set rather than emoji: an emoji is drawn in
	// its own colours, whatever the theme, and at a width terminals disagree
	// about.
	icon := st.Icon("attach")
	switch m.Type {
	case "image":
		icon = st.Icon("image")
	case "video":
		icon = st.Icon("video")
	case "audio":
		icon = st.Icon("audio")
	case "ptt":
		icon = st.Icon("voice")
	case "sticker":
		icon = st.Icon("sticker")
	case "document":
		icon = st.Icon("document")
		if isArchiveName(m.Filename) {
			icon = st.Icon("archive")
		}
	}
	name := m.Filename
	if name == "" {
		name = m.Type
	}
	// An attachment WhatsApp no longer holds cannot be fetched, and saying so
	// on the chip is the difference between "I have not downloaded this yet"
	// and "this cannot be downloaded".
	suffix := ""
	if m.Expired() {
		suffix = "  · expired"
	}
	if m.Length > 0 {
		return fmt.Sprintf("%s %s  %s%s", icon, name, humanSize(m.Length), suffix)
	}
	return fmt.Sprintf("%s %s%s", icon, name, suffix)
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
	// A small chip in the middle rather than a rule across the pane: the day
	// is a quiet marker, and a full-width line is the loudest thing a
	// conversation can contain.
	if o.Styles.Shape == theme.ShapePill {
		p := o.Styles.Palette
		chip := o.Styles.Chip(strings.TrimSpace(label), p.Muted, p.Raised, false)
		left := (o.Width - VisibleWidth(chip)) / 2
		if left < 0 {
			return Truncate(chip, o.Width)
		}
		return strings.Repeat(" ", left) + chip
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

// markMatches paints the search pattern where it appears in a line.
//
// The line is plain text at this point, before any styling: marking styled
// text would mean parsing escapes back out of it, and the only thing that
// needs marking is the message's own words.
func (o Options) markMatches(line string) string {
	if o.Highlight == "" || line == "" {
		return line
	}
	st := o.Styles.Match
	if o.HighlightCur {
		st = o.Styles.MatchCur
	}

	var b strings.Builder
	rest := line
	for {
		i, n := indexPattern(rest, o.Highlight, o.HighlightFold)
		if i < 0 || n == 0 {
			b.WriteString(rest)
			return b.String()
		}
		b.WriteString(rest[:i])
		b.WriteString(st.Render(rest[i : i+n]))
		rest = rest[i+n:]
	}
}

// indexPattern finds pattern in s and returns where it starts and how many
// bytes of s it covers, or -1.
//
// Lowercasing both sides and searching that would be shorter, but folding can
// change a string's length - Turkish \u0130 folds to two runes - and an index into
// the folded string is then not an index into this one.
func indexPattern(s, pattern string, fold bool) (int, int) {
	if !fold {
		return strings.Index(s, pattern), len(pattern)
	}
	for i := range s {
		if n := foldPrefix(s[i:], pattern); n >= 0 {
			return i, n
		}
	}
	return -1, 0
}

// foldPrefix returns how many bytes of s match pattern ignoring case, or -1.
func foldPrefix(s, pattern string) int {
	n := 0
	for len(pattern) > 0 {
		if n >= len(s) {
			return -1
		}
		sr, sw := utf8.DecodeRuneInString(s[n:])
		pr, pw := utf8.DecodeRuneInString(pattern)
		if unicode.ToLower(sr) != unicode.ToLower(pr) {
			return -1
		}
		n, pattern = n+sw, pattern[pw:]
	}
	return n
}

// pillBubble draws a message as a rounded surface.
//
// A one-line message is a capsule, the same shape as the rice's tmux and
// waybar segments. A longer one is a rounded card: its first and last rows end
// in the half circles and the rows between have straight sides. There are no
// half-block rows above and below any more; those were what made a bubble look
// stepped, pixelated and twice as tall as its text.
//
// The time and the delivery state sit inside, at the end of the last row, the
// way a phone draws them. Outside, they floated in the gutter and the eye had
// to travel to connect them to their message.
func pillBubble(m domain.Message, o Options) []string {
	st := o.Styles
	p := st.Palette
	pad := o.Padding
	if pad < 0 {
		pad = 0
	}

	fillHex := p.BubbleTheirs
	if m.FromMe {
		fillHex = p.BubbleMine
	}
	// The selected message comes forward: its fill lifts toward the accent and
	// its rounded ends take the accent itself, which is the bubble's border
	// changing colour in a shape that has no border. The palette's selection
	// role, tried first, was a shade away from the bubble and invisible.
	edgeHex := fillHex
	if o.Selected {
		fillHex = p.SelectedFill(fillHex)
		edgeHex = p.Accent
	}
	fill := lipgloss.NewStyle().Foreground(lipgloss.Color(p.Fg)).Background(lipgloss.Color(fillHex))
	edge := lipgloss.NewStyle().Foreground(lipgloss.Color(edgeHex))
	if !st.Glass {
		edge = edge.Background(lipgloss.Color(p.Bg))
	}
	lcap, rcap := st.Shape.Caps()

	// The time is quiet, but it must stay legible on whatever the bubble is
	// filled with - on a selected bubble the faint colour all but vanished.
	stampHex := theme.Readable(p.Faint, fillHex, p.Fg, 3.0)
	footer := lipgloss.NewStyle().Foreground(lipgloss.Color(stampHex)).Render(m.TS.Format(layoutOr(o.Timestamp)))
	if m.FromMe {
		if tick := tickIcon(m, st); tick != "" {
			footer += " " + tick
		}
	}
	footerW := VisibleWidth(footer)

	// The widest the text may be: the bubble cap, less the two edges, the
	// padding and a column for the selection mark.
	maxInner := o.innerWidth()
	if lim := o.Width - 3 - 2*pad; lim < maxInner {
		maxInner = lim
	}
	if maxInner < 4 {
		maxInner = 4
	}

	withSender := func(body []string) []string {
		if m.FromMe || !o.ShowSender || m.SenderName == "" {
			return body
		}
		nameHex := p.Accent
		if c, ok := st.SenderStyle(m.SenderName).GetForeground().(lipgloss.Color); ok {
			nameHex = string(c)
		}
		nameHex = theme.Readable(nameHex, fillHex, p.Fg, 3.0)
		name := lipgloss.NewStyle().Foreground(lipgloss.Color(nameHex)).Bold(true).Render(Truncate(m.SenderName, maxInner))
		return append([]string{name}, body...)
	}

	natural := withSender(bodyLines(m, o.withInner(maxInner)))
	inner := 0
	for _, l := range natural {
		w := VisibleWidth(l)
		if n := strings.Count(l, "▀"); n > 0 {
			w = n
		}
		if w > inner {
			inner = w
		}
	}
	last := VisibleWidth(natural[len(natural)-1])
	sameRow := last+2+footerW <= maxInner
	if sameRow {
		inner = maxInt(inner, last+2+footerW)
	} else {
		inner = maxInt(inner, footerW)
	}
	if inner > maxInner {
		inner = maxInner
	}
	body := withSender(bodyLines(m, o.withInner(inner)))

	// Reactions are wrapped into the tail of the body by bodyLines - the same
	// call, with the same inner, so re-wrapping the summary here counts
	// exactly the rows it produced there.
	reactionRows := 0
	if chips := m.ReactionSummary(); len(chips) > 0 {
		reactionRows = len(Wrap(strings.Join(chips, " "), inner))
	}
	decorFrom := maxInt(1, len(body)-reactionRows)

	if !sameRow || VisibleWidth(body[len(body)-1])+2+footerW > inner {
		body = append(body, "")
		sameRow = false
	}

	open := StylePrefix(fill.Render(bubbleProbe), bubbleProbe)
	space := strings.Repeat(" ", pad)
	decorSpace := strings.Repeat(" ", pad+1)
	rows := make([]string, len(body))
	for i, l := range body {
		content := Pad(l, inner)
		if i == len(body)-1 {
			if sameRow {
				content = Pad(l, inner-footerW) + footer
			} else {
				content = PadLeft(footer, inner)
			}
		}

		// A lone timestamp, and the reactions above it, are decoration under
		// the message rather than more of it: filling their row in the
		// bubble's own colour grew the bubble downward for a caption that is
		// not conversation text. They sit under it instead, plain, matching
		// the width so a right-aligned message still lines its caption up
		// with the bubble above.
		if i >= decorFrom {
			rows[i] = decorSpace + content + decorSpace
			continue
		}

		if open != "" {
			content = ReopenAfterResets(content, open)
		}
		left, right := edge.Render(lcap), edge.Render(rcap)
		// cardLast is the last row still part of the bubble itself, not a
		// trailing decor row (a lone timestamp or reactions): that row is
		// what carries the round bottom cap, even after a decor row got
		// appended past it.
		cardLast := decorFrom - 1
		switch {
		case cardLast == 1:
			// Exactly two rows - a sender name over one line of text is the
			// common case - with nothing between them to carry the seam: two
			// round ends stacked directly pinch into an hourglass instead of
			// reading as one bubble, so this pair goes flat instead.
			left, right = fill.Render(" "), fill.Render(" ")
		case o.CardEdges != "all" && cardLast > 1 && i != 0 && i != cardLast:
			left, right = edge.Render("▐"), edge.Render("▌")
			if o.CardEdges == "ends" {
				left, right = fill.Render(" "), fill.Render(" ")
			}
		}
		rows[i] = left + fill.Render(space+content+space) + right
	}

	boxW := inner + 2*pad + 2
	mark := " "
	if o.Marked {
		mark = st.BubbleSel.Render(markGlyph)
	}
	out := make([]string, len(rows))
	for i, r := range rows {
		lead := " "
		if i == 0 {
			lead = mark
		}
		if m.FromMe {
			gap := o.Width - boxW - 1
			if gap < 0 {
				gap = 0
			}
			out[i] = strings.Repeat(" ", gap) + lead + r
			continue
		}
		out[i] = lead + r
	}
	return fitWidth(out, o.Width)
}

// tickIcon is the delivery state as an icon from the configured set.
func tickIcon(m domain.Message, st theme.Styles) string {
	switch m.Delivery {
	case domain.Pending:
		return st.TickPending.Render(st.Icon("clock"))
	case domain.Sent:
		return st.TickSent.Render(st.Icon("sent"))
	case domain.Delivered:
		return st.TickDelivered.Render(st.Icon("delivered"))
	case domain.Read:
		return st.TickRead.Render(st.Icon("read"))
	case domain.Failed:
		return st.TickFailed.Render(st.Icon("failed"))
	}
	return ""
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// isArchiveName says a document is a pile of other files.
func isArchiveName(name string) bool {
	lower := strings.ToLower(name)
	for _, ext := range []string{".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".xz", ".bz2", ".zst"} {
		if strings.HasSuffix(lower, ext) {
			return true
		}
	}
	return false
}
