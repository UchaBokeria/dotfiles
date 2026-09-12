package store

import (
	"context"
	"database/sql"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// LID addresses.
//
// WhatsApp is moving accounts from a phone number ("995…@s.whatsapp.net") to
// an opaque identifier ("487…@lid"), and both forms reach the same person.
// wacli's store records whichever the server used, so one conversation can end
// up split across two chat rows: the reply arrives under the number and the
// reaction under the LID, and neither shows the other.
//
// The mapping is not in wacli.db. It is in the whatsmeow session database
// beside it, which wacli keeps for its own connection - `whatsmeow_lid_map` is
// a plain lid/pn pair table, and the device row names the linked account's own
// pair. Reading it is what lets wa show one chat per person instead of two.
type lidMap struct {
	mu    sync.RWMutex
	toPN  map[string]string // lid user -> phone user
	toLID map[string]string // phone user -> lid user
}

// sessionPath is where wacli keeps its whatsmeow session, beside the store.
func sessionPath(storeDB string) string {
	return filepath.Join(filepath.Dir(storeDB), "session.db")
}

// loadLIDMap reads the pair table. A missing or unreadable session database is
// not an error: without it wa behaves as it did before LIDs existed, which is
// correct for every account WhatsApp has not migrated.
func loadLIDMap(path string) *lidMap {
	m := &lidMap{toPN: map[string]string{}, toLID: map[string]string{}}

	db, err := openRO(path)
	if err != nil {
		return m
	}
	defer db.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	rows, err := db.QueryContext(ctx, `select lid, pn from whatsmeow_lid_map`)
	if err != nil {
		return m
	}
	defer rows.Close()

	for rows.Next() {
		var lid, pn string
		if err := rows.Scan(&lid, &pn); err != nil {
			return m
		}
		m.add(lid, pn)
	}

	// The device row carries the linked account's own pair, which is the one
	// that matters most: a reaction sent from this client comes back addressed
	// to our own LID.
	var own, ownLID sql.NullString
	if err := db.QueryRowContext(ctx,
		`select jid, lid from whatsmeow_device limit 1`).Scan(&own, &ownLID); err == nil {
		m.add(ownLID.String, own.String)
	}
	return m
}

// add records one pair. Either side may arrive with a device suffix or a
// server ("487…:26@lid"), so both are reduced to the user part - the only part
// that identifies the person.
func (m *lidMap) add(lid, pn string) {
	l, p := jidUser(lid), jidUser(pn)
	if l == "" || p == "" {
		return
	}
	m.mu.Lock()
	m.toPN[l] = p
	m.toLID[p] = l
	m.mu.Unlock()
}

// jidUser is the user part of anything JID-shaped.
func jidUser(s string) string {
	if s == "" {
		return ""
	}
	j, err := domain.ParseJID(s)
	if err != nil {
		return ""
	}
	return j.User
}

// Canonical returns the phone-number form of a JID, or the JID unchanged when
// there is nothing to map. Everything the interface shows or asks for is in
// this form, so a chat has one identity however the server addressed it.
func (m *lidMap) Canonical(j domain.JID) domain.JID {
	if m == nil || j.Server != domain.ServerLID {
		return j
	}
	m.mu.RLock()
	pn, ok := m.toPN[j.User]
	m.mu.RUnlock()
	if !ok {
		return j
	}
	return domain.JID{User: pn, Server: domain.ServerDM, Device: j.Device}
}

// phoneFor returns the phone number a LID user stands for.
func (m *lidMap) phoneFor(lidUser string) (string, bool) {
	if m == nil {
		return "", false
	}
	m.mu.RLock()
	defer m.mu.RUnlock()
	pn, ok := m.toPN[lidUser]
	return pn, ok
}

// Aliases lists every JID a chat's messages may be filed under: the JID
// itself, and its counterpart when one is known.
func (m *lidMap) Aliases(j domain.JID) []string {
	out := []string{j.String()}
	if m == nil {
		return out
	}

	m.mu.RLock()
	defer m.mu.RUnlock()

	switch j.Server {
	case domain.ServerDM:
		if lid, ok := m.toLID[j.User]; ok {
			out = append(out, domain.JID{User: lid, Server: domain.ServerLID}.String())
		}
	case domain.ServerLID:
		if pn, ok := m.toPN[j.User]; ok {
			out = append(out, domain.JID{User: pn, Server: domain.ServerDM}.String())
		}
	}
	return out
}

// Len is how many pairs are known, for diagnostics.
func (m *lidMap) Len() int {
	if m == nil {
		return 0
	}
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.toPN)
}

// foldChats merges the LID row of a conversation into its phone-number row.
//
// Without this the list shows the same person twice: once under the number,
// once under the LID, each with half the history. The surviving row keeps the
// newer activity and whichever name is actually a name.
func (m *lidMap) foldChats(in []domain.Chat) []domain.Chat {
	if m == nil || m.Len() == 0 {
		return in
	}

	out := in[:0:0]
	at := map[string]int{}

	for _, c := range in {
		c.JID = m.Canonical(c.JID)
		key := c.JID.String()

		i, seen := at[key]
		if !seen {
			at[key] = len(out)
			out = append(out, c)
			continue
		}
		out[i] = mergeChats(out[i], c)
	}
	return out
}

// mergeChats combines two rows for one person. The newer row wins on anything
// about recent activity; a real name beats a placeholder whichever row it came
// from; and the unread counts add up, because the two rows counted different
// messages.
func mergeChats(a, b domain.Chat) domain.Chat {
	if b.LastMessageTS.After(a.LastMessageTS) {
		a.LastMessageTS = b.LastMessageTS
		a.LastSnippet = b.LastSnippet
	}
	if a.Name == "" {
		a.Name = b.Name
	}
	a.Unread = a.Unread || b.Unread
	a.UnreadCount += b.UnreadCount
	a.Pinned = a.Pinned || b.Pinned
	a.Archived = a.Archived && b.Archived
	if b.MutedUntil.After(a.MutedUntil) {
		a.MutedUntil = b.MutedUntil
	}
	return a
}

// inClause builds "col in (?, ?, …)", or a plain equality for one value.
func inClause(col string, n int) string {
	if n <= 1 {
		return col + " = ?"
	}
	return col + " in (?" + strings.Repeat(", ?", n-1) + ")"
}

// jidArgs turns a JID list into query arguments.
func jidArgs(jids []string) []any {
	out := make([]any, len(jids))
	for i, j := range jids {
		out[i] = j
	}
	return out
}

// LIDPairs is how many LID addresses can be resolved for a store, for
// diagnostics.
func LIDPairs(storeDB string) int {
	return loadLIDMap(sessionPath(storeDB)).Len()
}
