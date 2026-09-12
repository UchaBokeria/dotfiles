// Package store reads wacli's local database.
//
// Reads go straight to the SQLite file rather than through the wacli command
// line, because a warm `wacli --json` invocation costs 11-15 ms and the
// interface issues a query per keystroke while searching. The file is opened
// read-only; nothing here ever writes. Writes belong to the wacli package,
// which owns the store lock.
//
// Reading while a sync process holds the lock is safe: wacli.db is in WAL mode,
// so a reader never blocks the writer or vice versa.
package store

import (
	"context"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// Reader is the read side of the store. Two implementations exist: one over
// SQLite and one over the wacli command line, chosen at startup by a schema
// probe.
type Reader interface {
	Chats(ctx context.Context, f ChatFilter) ([]domain.Chat, error)
	Chat(ctx context.Context, jid domain.JID) (domain.Chat, error)
	Messages(ctx context.Context, f MessageFilter) ([]domain.Message, error)
	Message(ctx context.Context, chat domain.JID, id string) (domain.Message, error)
	Search(ctx context.Context, q Query) ([]domain.Message, error)
	Contact(ctx context.Context, jid domain.JID) (domain.Contact, error)
	Stats(ctx context.Context) (Stats, error)
	Close() error
}

// ChatFilter selects and narrows the chat list. The booleans are inclusive
// filters: setting Unread means "only unread", not "also unread".
type ChatFilter struct {
	Query string
	Limit int

	Unread   bool
	Pinned   bool
	Archived bool
	Muted    bool
	Groups   bool
	DMs      bool

	// IncludeArchived shows archived chats alongside the rest. Archived chats
	// are hidden by default, as in the phone app.
	IncludeArchived bool
}

// MessageFilter selects a page of messages. Paging is keyset rather than
// OFFSET: an offset re-walks every skipped row and drifts when a message
// arrives mid-scroll.
type MessageFilter struct {
	Chat  domain.JID
	Limit int

	// BeforeTS and BeforeRowID form the cursor for paging backwards through
	// history. Both are set from the oldest message of the previous page.
	BeforeTS    time.Time
	BeforeRowID int64

	// AfterTS and AfterRowID page forwards, for catching up after an event.
	AfterTS    time.Time
	AfterRowID int64

	// Ascending returns oldest first. The default is newest first, which is
	// the order a chat is opened in.
	Ascending bool
}

// Query is a full-text search.
type Query struct {
	Text     string
	Chat     domain.JID
	Limit    int
	HasMedia bool
	Starred  bool
	FromMe   bool
	// Since narrows to messages at or after this time. Zero means no bound.
	Since time.Time
}

// Stats summarises the store. MaxRowID and LastMessageTS are what the polling
// live source compares between ticks.
type Stats struct {
	Messages      int
	Chats         int
	Contacts      int
	Groups        int
	MaxRowID      int64
	LastMessageTS time.Time
}

// Degradation records that the fast path was unavailable and why. It is
// surfaced once in the status line rather than swallowed, so a wacli upgrade
// that changes the schema is visible instead of merely slow.
type Degradation struct {
	Used   bool
	Reason string
}

func limitOr(n, fallback int) int {
	if n <= 0 {
		return fallback
	}
	return n
}
