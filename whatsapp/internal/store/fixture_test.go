package store

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// The fixtures build a real database from the real wacli DDL, captured in
// testdata/schema.sql. That keeps the FTS triggers and the column types exactly
// as production has them, and means these tests never touch the live store.

type chatRow struct {
	jid      string
	kind     string
	name     string
	ts       int64
	archived bool
	pinned   bool
	muted    int64
	unread   int
}

type msgRow struct {
	chat         string
	id           string
	sender       string
	senderName   string
	ts           int64
	fromMe       bool
	text         string
	quoted       string
	mediaType    string
	caption      string
	filename     string
	localPath    string
	downloadedAt int64
	revoked      bool
	edited       bool
}

// newDB creates an empty store at the given migration version.
func newDB(t *testing.T, version int) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "wacli.db")

	ddl, err := os.ReadFile("testdata/schema.sql")
	if err != nil {
		t.Fatalf("reading the schema fixture: %v", err)
	}

	db, err := sql.Open("sqlite", "file:"+path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	if _, err := db.Exec(string(ddl)); err != nil {
		t.Fatalf("applying the schema: %v", err)
	}
	for v := 1; v <= version; v++ {
		if _, err := db.Exec(
			`insert into schema_migrations(version, name, applied_at) values(?, ?, 0)`,
			v, fmt.Sprintf("migration %d", v)); err != nil {
			t.Fatal(err)
		}
	}
	return path
}

// fixturePath is a store at a given schema version with no rows.
func fixturePath(t *testing.T, version int) string {
	t.Helper()
	return newDB(t, version)
}

// fixture is a store at the known-good version, seeded with chats, opened
// read-only through the real code path.
func fixture(t *testing.T, chats ...chatRow) (Reader, string) {
	t.Helper()
	path := newDB(t, KnownMigration)
	insertChats(t, path, chats...)

	r, err := OpenSQLite(path)
	if err != nil {
		t.Fatalf("opening the fixture: %v", err)
	}
	t.Cleanup(func() { r.Close() })
	return r, path
}

// writable opens the fixture for writing. Tests seed through this; the code
// under test only ever sees the read-only handle.
func writable(t *testing.T, path string) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", "file:"+path)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func insertChats(t *testing.T, path string, chats ...chatRow) {
	t.Helper()
	db := writable(t, path)
	for _, c := range chats {
		kind := c.kind
		if kind == "" {
			kind = "dm"
		}
		if _, err := db.Exec(`
insert into chats(jid, kind, name, last_message_ts, archived, pinned, muted_until, unread, unread_count)
values(?, ?, ?, ?, ?, ?, ?, ?, ?)`,
			c.jid, kind, c.name, c.ts, b2i(c.archived), b2i(c.pinned), c.muted,
			b2i(c.unread > 0), c.unread); err != nil {
			t.Fatalf("seeding chat %s: %v", c.jid, err)
		}
	}
}

func insertMessage(t *testing.T, path string, m msgRow) {
	t.Helper()
	db := writable(t, path)
	if _, err := db.Exec(`
insert into messages(chat_jid, chat_name, msg_id, sender_jid, sender_name, ts, from_me,
                     text, quoted_msg_id, is_forwarded, media_type, media_caption,
                     filename, local_path, downloaded_at, revoked, deleted_for_me,
                     edited, edited_ts)
values(?, '', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, 0, ?, 0)`,
		m.chat, m.id, m.sender, m.senderName, m.ts, b2i(m.fromMe), m.text, m.quoted,
		m.mediaType, m.caption, m.filename, m.localPath, m.downloadedAt,
		b2i(m.revoked), b2i(m.edited)); err != nil {
		t.Fatalf("seeding message %s: %v", m.id, err)
	}
}

// seedMessages inserts n messages one second apart, oldest first.
func seedMessages(t *testing.T, path, chat string, n int) {
	t.Helper()
	for i := 1; i <= n; i++ {
		insertMessage(t, path, msgRow{
			chat: chat,
			id:   fmt.Sprintf("M%d", i),
			ts:   int64(1_700_000_000 + i),
			text: fmt.Sprintf("message %d", i),
		})
	}
}

func b2i(b bool) int {
	if b {
		return 1
	}
	return 0
}

func names(cs []domain.Chat) []string {
	out := make([]string, 0, len(cs))
	for _, c := range cs {
		out = append(out, c.Name)
	}
	return out
}

func ids(ms []domain.Message) []string {
	out := make([]string, 0, len(ms))
	for _, m := range ms {
		out = append(out, m.ID)
	}
	return out
}

func mustJID(t *testing.T, s string) domain.JID {
	t.Helper()
	j, err := domain.ParseJID(s)
	if err != nil {
		t.Fatal(err)
	}
	return j
}

func hoursAgo(n int) int64 { return time.Now().Add(-time.Duration(n) * time.Hour).Unix() }

// insertReaction seeds a reaction row. WhatsApp stores each one as a message
// of its own, pointing at the message it is on.
func insertReaction(t *testing.T, path, chat, id, target, emoji string, ts int64) {
	t.Helper()
	db := writable(t, path)
	if _, err := db.Exec(`
insert into messages(chat_jid, chat_name, msg_id, sender_jid, sender_name, ts, from_me,
                     text, is_forwarded, reaction_to_id, reaction_emoji,
                     revoked, deleted_for_me, edited, edited_ts)
values(?, '', ?, '', '', ?, 1, '', 0, ?, ?, 0, 0, 0, 0)`,
		chat, id, ts, target, emoji); err != nil {
		t.Fatalf("seeding reaction %s: %v", id, err)
	}
}
