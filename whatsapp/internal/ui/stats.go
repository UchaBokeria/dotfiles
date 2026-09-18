package ui

import (
	"context"
	"fmt"
	"github.com/charmbracelet/lipgloss"
	"sort"
	"strings"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
)

// The profile page.
//
// WhatsApp's contact screen answers "how much of this is there": how many
// messages, how many pictures, how many documents. wa can answer it better,
// because the whole history is in a database rather than behind a scroll.

// showChatStats draws the numbers for one conversation.
func (a *App) showChatStats(c domain.Chat) error {
	if a.deps.Store == nil {
		return fmt.Errorf("no store")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	st, err := a.deps.Store.ChatStats(ctx, c.JID)
	if err != nil {
		return err
	}
	contact, _ := a.deps.Store.Contact(ctx, c.JID)

	lines := statsLines(a.chatName(c.JID), c, contact, st)
	a.overlay.Open("profile · "+a.chatName(c.JID), a.decorateStats(lines))
	return nil
}

// statsLines lays the profile out. Kept apart from the store call so it can be
// tested without one.
func statsLines(name string, c domain.Chat, contact domain.Contact, st store.ChatStats) []string {
	lines := []string{
		"",
		"  " + name,
		"  " + c.JID.String(),
	}
	if contact.About != "" {
		lines = append(lines, "  "+render1line(contact.About, 60))
	}
	if len(contact.Tags) > 0 {
		lines = append(lines, "  "+strings.Join(contact.Tags, ", "))
	}
	if contact.Business {
		lines = append(lines, "  business account")
	}

	lines = append(lines,
		"",
		"  messages",
		row("total", st.Messages),
		row("sent", st.Sent),
		row("received", st.Received),
	)
	if st.Reactions > 0 {
		lines = append(lines, row("reactions", st.Reactions))
	}
	if st.Starred > 0 {
		lines = append(lines, row("starred", st.Starred))
	}
	if st.Edited > 0 {
		lines = append(lines, row("edited", st.Edited))
	}
	if st.Deleted > 0 {
		lines = append(lines, row("deleted", st.Deleted))
	}
	if st.Links > 0 {
		lines = append(lines, row("links", st.Links))
	}

	if total := kindTotal(st.Kinds); total > 0 {
		lines = append(lines, "", "  attachments", row("total", total))
		for _, k := range sortedKinds(st.Kinds) {
			lines = append(lines, row(kindName(k), st.Kinds[k]))
		}
		if st.Archives > 0 {
			lines = append(lines, row("  of those, archives", st.Archives))
		}
		if st.Documents > 0 {
			lines = append(lines, row("  of those, documents", st.Documents))
		}
		if st.Bytes > 0 {
			lines = append(lines, "    "+pad("on the wire", 22)+media.HumanSize(st.Bytes))
		}
	}

	if !st.First.IsZero() {
		lines = append(lines,
			"",
			"  history",
			"    "+pad("first", 22)+st.First.Format("2006-01-02 15:04"),
			"    "+pad("last", 22)+st.Last.Format("2006-01-02 15:04"),
			"    "+pad("span", 22)+humanSpan(st.Last.Sub(st.First)),
		)
		if days := int(st.Last.Sub(st.First).Hours()/24) + 1; days > 0 && st.Messages > 0 {
			lines = append(lines, "    "+pad("a day, on average", 22)+
				fmt.Sprintf("%.1f", float64(st.Messages)/float64(days)))
		}
	}

	lines = append(lines,
		"",
		"  state",
		"    "+pad("pinned", 22)+yesNo(c.Pinned),
		"    "+pad("archived", 22)+yesNo(c.Archived),
		"    "+pad("muted", 22)+yesNo(c.Muted(time.Now())),
		"    "+pad("unread", 22)+itoa(c.UnreadCount),
	)
	return lines
}

func row(label string, n int) string { return "    " + pad(label, 22) + itoa(n) }

func pad(s string, w int) string {
	if len(s) >= w {
		return s + " "
	}
	return s + strings.Repeat(" ", w-len(s))
}

func kindTotal(kinds map[string]int) int {
	n := 0
	for _, v := range kinds {
		n += v
	}
	return n
}

func sortedKinds(kinds map[string]int) []string {
	out := make([]string, 0, len(kinds))
	for k := range kinds {
		out = append(out, k)
	}
	// Commonest first: the shape of the pile is the point.
	sort.Slice(out, func(i, j int) bool {
		if kinds[out[i]] != kinds[out[j]] {
			return kinds[out[i]] > kinds[out[j]]
		}
		return out[i] < out[j]
	})
	return out
}

// kindName spells wacli's media types the way a person would.
func kindName(k string) string {
	switch k {
	case "ptt":
		return "voice notes"
	case "image":
		return "pictures"
	case "video":
		return "video"
	case "audio":
		return "audio"
	case "document":
		return "documents"
	case "sticker":
		return "stickers"
	case "":
		return "other"
	}
	return k
}

// humanSpan is a duration in the units a conversation is measured in.
func humanSpan(d time.Duration) string {
	days := int(d.Hours() / 24)
	switch {
	case days >= 730:
		return fmt.Sprintf("%d years", days/365)
	case days >= 365:
		return "a year and " + itoa((days-365)/30) + " months"
	case days >= 60:
		return itoa(days/30) + " months"
	case days >= 1:
		return itoa(days) + " days"
	default:
		return itoa(int(d.Hours())) + " hours"
	}
}

// decorateStats puts an icon in front of each section heading and draws the
// headings in the accent, so the page reads as four groups rather than as one
// column of words. statsLines stays plain text, which is what its tests check.
func (a *App) decorateStats(lines []string) []string {
	st := a.styles
	icons := map[string]string{
		"messages": "chat", "attachments": "attach", "history": "clock", "state": "filter",
	}
	head := lipgloss.NewStyle().Foreground(lipgloss.Color(st.Palette.Accent)).Bold(true)
	out := make([]string, len(lines))
	for i, l := range lines {
		name := strings.TrimSpace(l)
		if icon, ok := icons[name]; ok && strings.HasPrefix(l, "  ") && !strings.HasPrefix(l, "    ") {
			out[i] = "  " + head.Render(st.Icon(icon)+" "+name)
			continue
		}
		out[i] = l
	}
	return out
}
