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
}
