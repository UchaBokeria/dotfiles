package domain

import "time"

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
	ID      string

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

	Media *MediaRef

	Revoked      bool
	DeletedForMe bool
	Edited       bool
	EditedTS     time.Time

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
// rather than an entry of its own.
func (m Message) IsReaction() bool { return m.ReactionTo != "" }

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
