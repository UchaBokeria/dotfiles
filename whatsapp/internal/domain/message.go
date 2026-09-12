package domain

import (
	"strconv"
	"time"
)

// DeliveryState is how far a message we sent has travelled. Messages we
// received are always Read from our side and carry no ticks.
type DeliveryState int

const (
	// Pending is an optimistic local message that has not been acknowledged.
	Pending DeliveryState = iota
	Sent
	Delivered
	Read
	Failed
)

// MediaRef describes an attachment. A nil *MediaRef means the message has none.
type MediaRef struct {
	Type         string // image, video, audio, document, sticker
	Caption      string
	Filename     string
	MimeType     string
	LocalPath    string
	Length       int64
	DownloadedAt time.Time
}

// Downloaded reports whether a local copy of the attachment exists.
func (m MediaRef) Downloaded() bool {
	return m.LocalPath != "" && !m.DownloadedAt.IsZero()
}

// Message is one entry in a conversation.
type Message struct {
	RowID   int64
	ChatJID JID
	// StoredChatJID is the address the row is actually filed under, which is
	// not always ChatJID: WhatsApp files some messages under a "@lid" address
	// and the store keeps whichever it was given. ChatJID is folded onto the
	// phone number so the interface sees one conversation; wacli looks a
	// message up by the address it stored, so every command that names a
	// message has to use this one.
	StoredChatJID JID
	ID            string

	SenderJID  JID
	SenderName string
	TS         time.Time
	FromMe     bool

	Text string

	QuotedID     string
	QuotedSender JID
	QuotedText   string

	Forwarded bool

	ReactionTo    string
	ReactionEmoji string
	// Reactions are the emoji other people put on this message. WhatsApp
	// stores each reaction as a message of its own; the store folds them onto
	// their target so they render as a chip rather than as a bubble that
	// covers the text it is reacting to.
	Reactions []Reaction

	Media *MediaRef

	Revoked      bool
	DeletedForMe bool
	// Unsupported is a message wacli could not decode - a poll, a contact
	// card, a group notice. Its text is wacli's "(message)" placeholder, which
	// drawn as a bubble reads as if somebody had typed it.
	Unsupported bool
	Edited      bool
	EditedTS    time.Time

	Delivery DeliveryState

	// Local marks an optimistic message that the UI drew before the store knew
	// about it. It is cleared once the real row arrives.
	Local bool
	// Err carries the failure reason for a message whose send did not succeed.
	Err string
}

// Body is the text to render: the message text when there is one, otherwise the
// media caption, so a captioned image is not drawn as an empty bubble.
func (m Message) Body() string {
	if m.Text != "" {
		return m.Text
	}
	if m.Media != nil {
		return m.Media.Caption
	}
	return ""
}

// IsReaction reports whether the message is a reaction to another message
// rather than an entry of its own. These are never shown in the stream.
func (m Message) IsReaction() bool { return m.ReactionTo != "" }

// Reaction is one emoji somebody put on a message.
type Reaction struct {
	Emoji  string
	By     JID
	ByName string
	FromMe bool
	At     time.Time
}

// ReactionSummary groups the reactions by emoji, the way the phone app shows
// them: one chip per emoji with a count, most recent first.
func (m Message) ReactionSummary() []string {
	if len(m.Reactions) == 0 {
		return nil
	}
	order := make([]string, 0, len(m.Reactions))
	count := map[string]int{}
	for _, r := range m.Reactions {
		if r.Emoji == "" {
			continue
		}
		if count[r.Emoji] == 0 {
			order = append(order, r.Emoji)
		}
		count[r.Emoji]++
	}
	out := make([]string, 0, len(order))
	for _, e := range order {
		if n := count[e]; n > 1 {
			out = append(out, e+strconv.Itoa(n))
		} else {
			out = append(out, e)
		}
	}
	return out
}

// MyReaction is the emoji this account put on the message, if any. Sending the
// same one again removes it, as tapping it does in the app.
func (m Message) MyReaction() string {
	for _, r := range m.Reactions {
		if r.FromMe {
			return r.Emoji
		}
	}
	return ""
}

// HasMedia reports whether an attachment is present.
func (m Message) HasMedia() bool { return m.Media != nil && m.Media.Type != "" }

// Contact is local metadata about a person.
type Contact struct {
	JID      JID
	Name     string
	PushName string
	Alias    string
	Tags     []string
	About    string
	Business bool
}

// DisplayName prefers the name the user chose over the one WhatsApp supplies.
func (c Contact) DisplayName() string {
	switch {
	case c.Alias != "":
		return c.Alias
	case c.Name != "":
		return c.Name
	case c.PushName != "":
		return c.PushName
	default:
		return c.JID.Display()
	}
}

// StoreJID is the address to give wacli when naming this message. It falls
// back to ChatJID for messages built by anything that does not track the
// distinction, such as an optimistic bubble the composer just drew.
func (m Message) StoreJID() JID {
	if !m.StoredChatJID.IsZero() {
		return m.StoredChatJID
	}
	return m.ChatJID
}
