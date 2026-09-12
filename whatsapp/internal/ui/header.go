package ui

import (
	"fmt"
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
// conversation am I looking at. The clock is there because a terminal in a
// full-screen window usually hides the one on the desktop.
func (a *App) headerLine() string {
	st := a.styles
	clock := st.ListTime.Render(time.Now().Format("15:04") + " ")

	// The left segment is exactly as wide as the chat list, so the name of the
	// open conversation begins directly above the conversation. A header whose
	// halves do not line up with the columns under them reads as one long
	// sentence rather than as two labels.
	left := " " + a.accountName()
	leftWidth := a.listWidth() + 1
	if a.narrow() || leftWidth > a.width/2 {
		leftWidth = minInt(a.width, render.VisibleWidth(left)+1)
	}
	left = render.Pad(render.Truncate(left, leftWidth), leftWidth)

	gap := a.width - leftWidth - render.VisibleWidth(clock)
	if gap < 1 {
		return st.Status.Render(render.Pad(render.Truncate(left, a.width), a.width))
	}
	// Truncated with its own indent included: cutting the text to the gap and
	// then indenting it puts it back over the edge.
	middle := render.Pad(render.Truncate(" "+a.headerChat(), gap), gap)

	return st.Status.Render(st.StatusKey.Render(left)) + st.Status.Render(middle+clock)
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
	c := a.pane.Chat()
	if c.JID.IsZero() {
		return a.styles.ListSnip.Render("no conversation open")
	}

	parts := []string{a.styles.ListName.Render(a.list.DisplayName(c))}
	if kind := chatKindLabel(c); kind != "" {
		parts = append(parts, a.styles.ListSnip.Render(kind))
	}
	if c.UnreadCount > 0 {
		parts = append(parts, a.styles.ListBadge.Render(
			fmt.Sprintf(" %d unread ", c.UnreadCount)))
	}
	for _, m := range chatMarkers(c, a.styles) {
		parts = append(parts, m)
	}
	return strings.Join(parts, a.styles.ListTime.Render(" · "))
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
		out = append(out, st.ListPin.Render("pinned"))
	}
	if c.Muted(time.Now()) {
		out = append(out, st.ListMute.Render("muted"))
	}
	if c.Archived {
		out = append(out, st.ListMute.Render("archived"))
	}
	return out
}
