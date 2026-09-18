package domain

import "time"

// EventKind is the sort of live update the sync process reported.
type EventKind string

const (
	EventMessage      EventKind = "message"
	EventReceipt      EventKind = "receipt"
	EventChatPresence EventKind = "chat_presence"
)

// Event is a live update. It is deliberately thin: the UI treats an event as a
// hint that a chat changed and re-reads the authoritative rows from the store,
// so a dropped event costs latency and never correctness.
type Event struct {
	Kind      EventKind
	Chat      JID
	MessageID string
	At        time.Time
	// MessageIDs is the whole batch a receipt covers. WhatsApp acknowledges
	// several messages in one receipt, and posting one event per message would
	// throw away the fact that they arrived together.
	MessageIDs []string
	// Receipt is how far the messages got, for EventReceipt. Zero elsewhere.
	Receipt DeliveryState
	// Sender is who the receipt came from, which in a group is one participant
	// rather than the chat.
	Sender JID
	// State is the typing state, for EventChatPresence: "composing",
	// "recording" or "paused".
	State string
}
