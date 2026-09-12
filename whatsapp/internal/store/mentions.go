package store

import (
	"context"
	"database/sql"
	"regexp"
	"strings"
	"sync"
)

// Mentions.
//
// WhatsApp stores a mention as "@" followed by the person's number - or, since
// the move to LID addresses, by their opaque LID. The phone app swaps that for
// the person's name when it draws the message; the store keeps the digits. So
// "@148777784619227" is what a group mention looked like in wa, where the
// phone shows "@rezi".
//
// The name is looked up the way the chat list resolves one: your own alias for
// the person first, then your address book, then what they call themselves.
// A "name" that is only the number again is skipped, because the number is
// what is being replaced.

var mentionPattern = regexp.MustCompile(`@(\d{6,20})\b`)

// mentions resolves and remembers the names behind mention digits.
type mentions struct {
	db   *sql.DB
	lids *lidMap

	mu    sync.Mutex
	names map[string]string // digits -> name, "" once known to have none
}

func newMentions(db *sql.DB, lids *lidMap) *mentions {
	return &mentions{db: db, lids: lids, names: map[string]string{}}
}

// Resolve replaces every mention it can put a name to.
func (m *mentions) Resolve(ctx context.Context, text string) string {
	if m == nil || !strings.Contains(text, "@") {
		return text
	}
	return mentionPattern.ReplaceAllStringFunc(text, func(tok string) string {
		if name := m.name(ctx, tok[1:]); name != "" {
			return "@" + name
		}
		return tok
	})
}

func (m *mentions) name(ctx context.Context, digits string) string {
	m.mu.Lock()
	if name, ok := m.names[digits]; ok {
		m.mu.Unlock()
		return name
	}
	m.mu.Unlock()

	// A LID first becomes the number it stands for; the contact record is
	// filed under the number.
	user := digits
	if pn, ok := m.lids.phoneFor(digits); ok {
		user = pn
	}
	name := m.lookup(ctx, user+"@s.whatsapp.net")

	m.mu.Lock()
	m.names[digits] = name
	m.mu.Unlock()
	return name
}

func (m *mentions) lookup(ctx context.Context, jid string) string {
	row := m.db.QueryRowContext(ctx, `
select coalesce((select a.alias from contact_aliases a where a.jid = c.jid), ''),
       coalesce(c.full_name, ''), coalesce(c.push_name, ''),
       coalesce(c.first_name, ''), coalesce(c.business_name, '')
from contacts c where c.jid = ?`, jid)

	var alias, full, push, first, business string
	if err := row.Scan(&alias, &full, &push, &first, &business); err != nil {
		return ""
	}
	for _, name := range []string{alias, full, first, business, push} {
		if name = strings.TrimSpace(name); name != "" && !looksLikeNumber(name) {
			return name
		}
	}
	return ""
}

// looksLikeNumber reports whether a "name" is only a phone number with its
// usual punctuation - which is what the address book holds for anyone saved
// without a name, your own number included.
func looksLikeNumber(s string) bool {
	digits := 0
	for _, r := range s {
		switch {
		case r >= '0' && r <= '9':
			digits++
		case r == '+' || r == ' ' || r == '-' || r == '(' || r == ')':
		default:
			return false
		}
	}
	return digits > 0
}
