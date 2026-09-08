// Package domain holds the value types every other package speaks. It performs
// no I/O and imports nothing from the rest of the project, so it can be used
// from tests without dragging in a store, a subprocess, or a terminal.
package domain

import (
	"errors"
	"strings"
)

// WhatsApp server parts. A bare phone number is assumed to be a direct message.
const (
	ServerDM         = "s.whatsapp.net"
	ServerGroup      = "g.us"
	ServerBroadcast  = "broadcast"
	ServerNewsletter = "newsletter"
	ServerLID        = "lid"
)

// ChatKind is the sort of conversation a JID addresses.
type ChatKind string

const (
	KindDM         ChatKind = "dm"
	KindGroup      ChatKind = "group"
	KindBroadcast  ChatKind = "broadcast"
	KindNewsletter ChatKind = "newsletter"
	KindUnknown    ChatKind = "unknown"
)

// ErrBadJID is returned for input that cannot be a JID.
var ErrBadJID = errors.New("not a JID")

// JID addresses a WhatsApp user, group, channel, or broadcast list.
type JID struct {
	User   string
	Server string
	Device string
}

// ParseJID accepts the wire forms ("<user>@s.whatsapp.net", "<id>@g.us",
// "<id>@newsletter", "status@broadcast", "<user>:<device>@...") and also a bare
// phone number, which is treated as a direct message. Punctuation commonly
// pasted with a phone number - spaces, dashes, a leading plus - is stripped.
func ParseJID(s string) (JID, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return JID{}, ErrBadJID
	}

	user, server := s, ""
	if at := strings.LastIndex(s, "@"); at >= 0 {
		user, server = s[:at], s[at+1:]
	}

	device := ""
	if colon := strings.LastIndex(user, ":"); colon >= 0 {
		user, device = user[:colon], user[colon+1:]
	}

	if server == "" {
		user = stripPhonePunctuation(user)
		server = ServerDM
	}
	if user == "" || server == "" {
		return JID{}, ErrBadJID
	}
	return JID{User: user, Server: server, Device: device}, nil
}

// stripPhonePunctuation removes the characters people paste around a number.
func stripPhonePunctuation(s string) string {
	var b strings.Builder
	for _, r := range s {
		switch {
		case r >= '0' && r <= '9':
			b.WriteRune(r)
		case r == '.':
			// Kept: whatsmeow writes agent-suffixed users as "<number>.<agent>".
			b.WriteRune(r)
		}
	}
	return b.String()
}

// IsZero reports whether the JID addresses nothing.
func (j JID) IsZero() bool { return j.User == "" && j.Server == "" }

// String renders the wire form. The zero JID renders empty rather than "@".
func (j JID) String() string {
	if j.IsZero() {
		return ""
	}
	if j.Device != "" {
		return j.User + ":" + j.Device + "@" + j.Server
	}
	return j.User + "@" + j.Server
}

// Kind classifies the JID by its server part.
func (j JID) Kind() ChatKind {
	switch j.Server {
	case ServerDM, ServerLID:
		return KindDM
	case ServerGroup:
		return KindGroup
	case ServerBroadcast:
		return KindBroadcast
	case ServerNewsletter:
		return KindNewsletter
	default:
		return KindUnknown
	}
}

// Display is the JID as it should be shown when no contact name is known: a
// dialable number for a direct message, the bare identifier otherwise.
func (j JID) Display() string {
	if j.IsZero() {
		return ""
	}
	if j.Kind() == KindDM && j.Server == ServerDM {
		return "+" + j.User
	}
	return j.User
}
