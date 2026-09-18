package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"sync"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// ReceiptLog remembers how far each message wa sent has travelled.
//
// wacli's store records that a message was sent and nothing more: there is no
// receipts table, and the delivered/read state only ever crosses the webhook
// as a live event. Without a record of its own, wa showed one tick against
// every message it had ever sent - including ones the other person answered
// days ago - and lost even the live ticks on restart.
//
// Like the quote log this is wa's own small side-file: advisory, capped, and
// worth nothing but a tick if it is lost.
type ReceiptLog struct {
	path string

	mu      sync.RWMutex
	entries map[string]Receipt
	dirty   bool
}

// Receipt is the furthest state seen for one message.
type Receipt struct {
	// State is domain.Sent, Delivered or Read.
	State int   `json:"state"`
	At    int64 `json:"at"`
}

// maxReceipts bounds the file the way the quote log is bounded.
const maxReceipts = 20000

// OpenReceiptLog reads the log, or starts an empty one. A missing or unreadable
// file is not an error: ticks are not worth refusing to start over.
func OpenReceiptLog(path string) *ReceiptLog {
	r := &ReceiptLog{path: path, entries: map[string]Receipt{}}
	b, err := os.ReadFile(path)
	if err != nil {
		return r
	}
	_ = json.Unmarshal(b, &r.entries)
	return r
}

// Record notes a receipt. State only ever moves forwards: WhatsApp batches
// receipts and a late "delivered" must not undo a "read".
func (r *ReceiptLog) Record(msgID string, state domain.DeliveryState, at int64) bool {
	if r == nil || msgID == "" || state <= domain.Sent {
		return false
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if cur, ok := r.entries[msgID]; ok && domain.DeliveryState(cur.State) >= state {
		return false
	}
	r.entries[msgID] = Receipt{State: int(state), At: at}
	r.dirty = true
	return true
}

// Lookup is the state recorded for a message.
func (r *ReceiptLog) Lookup(msgID string) (domain.DeliveryState, bool) {
	if r == nil {
		return 0, false
	}
	r.mu.RLock()
	defer r.mu.RUnlock()
	e, ok := r.entries[msgID]
	return domain.DeliveryState(e.State), ok
}

// Apply raises a message's delivery state to whatever was recorded for it.
func (r *ReceiptLog) Apply(m domain.Message) domain.Message {
	if r == nil || !m.FromMe || m.Delivery == domain.Failed {
		return m
	}
	if state, ok := r.Lookup(m.ID); ok && state > m.Delivery {
		m.Delivery = state
	}
	return m
}

// Len is how many receipts are remembered.
func (r *ReceiptLog) Len() int {
	if r == nil {
		return 0
	}
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.entries)
}

// Save writes the log if anything changed.
func (r *ReceiptLog) Save() error {
	if r == nil || r.path == "" {
		return nil
	}
	r.mu.Lock()
	if !r.dirty {
		r.mu.Unlock()
		return nil
	}
	r.trimLocked()
	b, err := json.Marshal(r.entries)
	r.dirty = false
	r.mu.Unlock()

	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(r.path), 0o700); err != nil {
		return err
	}
	tmp := r.path + ".tmp"
	if err := os.WriteFile(tmp, b, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, r.path)
}

// trimLocked drops the oldest entries past the cap.
func (r *ReceiptLog) trimLocked() {
	if len(r.entries) <= maxReceipts {
		return
	}
	type aged struct {
		id string
		at int64
	}
	all := make([]aged, 0, len(r.entries))
	for id, e := range r.entries {
		all = append(all, aged{id, e.At})
	}
	sort.Slice(all, func(i, j int) bool { return all[i].at > all[j].at })
	for _, a := range all[maxReceipts:] {
		delete(r.entries, a.id)
	}
}
