package ui

import (
	"fmt"
	"github.com/charmbracelet/lipgloss"
	"strings"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// headerRows is how tall the top bar is. One row, always: a bar that comes and
// goes would move the whole conversation under the reader.
const headerRows = 1

// headerLine is the bar across the top of the screen.
//
// It answers the two questions a chat client is asked constantly and otherwise
// makes you work out from context: whose account is this, and which
// conversation am I looking at.
func (a *App) headerLine() string {
	st := a.styles
	p := st.Palette

	// The account sits over the chat list, as tmux's session pill sits at the
	// left of its bar, so the two halves of the header line up with the
	// columns under them.
	left := ""
	if !a.narrow() {
		label := render.Truncate(st.Icon("whatsapp")+" "+a.accountName(), maxInt(1, a.listWidth()-2))
		left = render.Pad(st.Chip(label, p.Fg, p.Raised, true), a.listWidth()) +
			strings.Repeat(" ", a.gap())
	}

	m := strings.Repeat(" ", a.margin())
	room := a.width - 2*a.margin() - render.VisibleWidth(left)
	if room < 4 {
		return m + render.Truncate(left, maxInt(1, a.width-2*a.margin()))
	}
	middle := render.Pad(render.Truncate(a.headerChat(), room), room)
	return m + left + middle + m
}

// accountName is the linked account, as a person would name it.
//
// The number is a last resort. Somebody who knows their own phone number by
// heart still does not read it as "me".
func (a *App) accountName() string {
	if a.deps.Self.IsZero() {
		return "wa"
	}
	if a.selfName != "" {
		return a.selfName
	}
	return a.deps.Self.Display()
}

// headerChat describes the open conversation: what it is, and anything about
// it that changes how a message will be treated.
func (a *App) headerChat() string {
	st := a.styles
	p := st.Palette
	c := a.pane.Chat()
	if c.JID.IsZero() {
		return st.ListSnip.Render("no conversation open")
	}

	kind := "account"
	if c.Kind == domain.KindGroup {
		kind = "group"
	}
	// The conversation has no chip of its own, so its title is where focus
	// shows: the accent while the keyboard is in the conversation or its
	// input box, the plain foreground while it is in the list.
	nameStyle := st.ListName.Bold(true)
	if a.focus != FocusList {
		nameStyle = nameStyle.Foreground(lipgloss.Color(p.Accent))
	}
	title := st.ListFilter.Render(st.Icon(kind)) + " " + nameStyle.Render(a.list.DisplayName(c))

	var meta []string
	if k := chatKindLabel(c); k != "" {
		meta = append(meta, k)
	}
	// How many people can read what you are about to type is worth knowing
	// before you type it.
	if c.Members > 0 {
		meta = append(meta, plural(c.Members, "member", "members"))
	}
	out := title
	if len(meta) > 0 {
		out += st.Timestamp.Render("  " + strings.Join(meta, " · "))
	}
	// States as icons: they are glanced at, not read.
	if icons := chatMarkers(c, st); len(icons) > 0 {
		out += "  " + strings.Join(icons, " ")
	}
	if c.UnreadCount > 0 {
		out += "  " + st.Chip(fmt.Sprintf("%d", c.UnreadCount), p.OnAccent, p.Accent, true)
	}
	return out
}

func chatKindLabel(c domain.Chat) string {
	switch c.Kind {
	case domain.KindGroup:
		return "group"
	case domain.KindBroadcast:
		return "broadcast"
	case domain.KindNewsletter:
		return "channel"
	}
	return ""
}

// chatMarkers are the states worth seeing before you type: a muted chat will
// not notify, an archived one is meant to be out of the way, and a pinned one
// was put where it is on purpose.
func chatMarkers(c domain.Chat, st theme.Styles) []string {
	var out []string
	if c.Pinned {
		out = append(out, st.ListPin.Render(st.Icon("pin")))
	}
	if c.Muted(time.Now()) {
		out = append(out, st.ListMute.Render(st.Icon("muted")))
	}
	if c.Archived {
		out = append(out, st.ListMute.Render(st.Icon("archived")))
	}
	return out
}
