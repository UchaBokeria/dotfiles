package domain

import "time"

// Chat is one conversation in the list.
type Chat struct {
	JID  JID
	Kind ChatKind
	Name string

	LastMessageTS time.Time
	LastSnippet   string

	Archived   bool
	Pinned     bool
	MutedUntil time.Time

	Unread      bool
	UnreadCount int
}

// Muted reports whether the chat is muted as of now. WhatsApp stores mutes as
// an expiry, so "muted" is a question about a moment, not a flag.
func (c Chat) Muted(now time.Time) bool {
	return !c.MutedUntil.IsZero() && c.MutedUntil.After(now)
}

// DisplayName falls back to the JID when the chat has no name, which happens
// for a contact who has never been in the address book.
func (c Chat) DisplayName() string {
	if c.Name != "" {
		return c.Name
	}
	return c.JID.Display()
}

// IsGroup reports whether the chat has more than one other participant.
func (c Chat) IsGroup() bool { return c.Kind == KindGroup }
