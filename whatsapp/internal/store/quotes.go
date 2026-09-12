package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// QuoteLog remembers what wa's own sends were replying to.
//
// wacli sends the quote - the other side sees the reply attached to the right
// message - but the row it writes to its own store has no quoted_msg_id. The
// phone never fills it in either, because the message is already there under
// that id. So a reply sent from wa shows as a reply everywhere except in wa,
// which is the one place the person who sent it is looking.
//
// This is wa's own record of its own sends, kept beside its other state. It is
// small, it is advisory, and losing it costs nothing but the quote bar.
type QuoteLog struct {
	path string

	mu      sync.RWMutex
	entries map[string]Quote
	dirty   bool
}

// Quote is what a message was replying to.
type Quote struct {
	QuotedID     string `json:"quoted_id"`
	QuotedSender string `json:"quoted_sender,omitempty"`
	QuotedText   string `json:"quoted_text,omitempty"`
	At           int64  `json:"at"`
}

// maxQuotes bounds the file. Ten thousand replies is years of use, and the
// oldest are the ones already scrolled past.
const maxQuotes = 10_000

// OpenQuoteLog reads the log, or starts an empty one. A missing or corrupt
// file is not an error: the worst case is a quote bar that does not appear.
func OpenQuoteLog(path string) *QuoteLog {
	q := &QuoteLog{path: path, entries: map[string]Quote{}}

	b, err := os.ReadFile(path)
	if err != nil {
		return q
	}
	var got map[string]Quote
	if err := json.Unmarshal(b, &got); err != nil {
		return q
	}
	q.entries = got
	return q
}

// Record notes what a message replied to.
func (q *QuoteLog) Record(msgID string, e Quote) {
	if q == nil || msgID == "" || e.QuotedID == "" {
		return
	}
	if e.At == 0 {
		e.At = time.Now().Unix()
	}
	q.mu.Lock()
	q.entries[msgID] = e
	q.dirty = true
	q.mu.Unlock()
}

// Lookup returns what a message replied to.
func (q *QuoteLog) Lookup(msgID string) (Quote, bool) {
	if q == nil {
		return Quote{}, false
	}
	q.mu.RLock()
	defer q.mu.RUnlock()
	e, ok := q.entries[msgID]
	return e, ok
}

// Apply fills in the quote on a message that the store does not know about.
// A quote already in the store always wins: it came from WhatsApp.
func (q *QuoteLog) Apply(m domain.Message) domain.Message {
	if q == nil || m.QuotedID != "" || !m.FromMe {
		return m
	}
	e, ok := q.Lookup(m.ID)
	if !ok {
		return m
	}
	m.QuotedID = e.QuotedID
	m.QuotedText = e.QuotedText
	if e.QuotedSender != "" {
		if j, err := domain.ParseJID(e.QuotedSender); err == nil {
			m.QuotedSender = j
		}
	}
	return m
}

// Save writes the log if anything changed.
func (q *QuoteLog) Save() error {
	if q == nil || q.path == "" {
		return nil
	}
	q.mu.Lock()
	if !q.dirty {
		q.mu.Unlock()
		return nil
	}
	q.trimLocked()
	b, err := json.Marshal(q.entries)
	q.dirty = false
	q.mu.Unlock()

	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(q.path), 0o700); err != nil {
		return err
	}
	// Written through a temporary file: a half-written log would be dropped
	// on the next start, taking every quote with it.
	tmp := q.path + ".tmp"
	if err := os.WriteFile(tmp, b, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, q.path)
}

// trimLocked drops the oldest entries past the cap.
func (q *QuoteLog) trimLocked() {
	if len(q.entries) <= maxQuotes {
		return
	}
	type aged struct {
		id string
		at int64
	}
	all := make([]aged, 0, len(q.entries))
	for id, e := range q.entries {
		all = append(all, aged{id, e.At})
	}
	sort.Slice(all, func(i, j int) bool { return all[i].at > all[j].at })
	for _, a := range all[maxQuotes:] {
		delete(q.entries, a.id)
	}
}

// Len is how many replies are remembered.
func (q *QuoteLog) Len() int {
	if q == nil {
		return 0
	}
	q.mu.RLock()
	defer q.mu.RUnlock()
	return len(q.entries)
}
