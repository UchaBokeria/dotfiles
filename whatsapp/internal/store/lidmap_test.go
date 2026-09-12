package store

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// newSession writes a whatsmeow session database beside a store, holding the
// two tables wa reads from it.
func newSession(t *testing.T, storePath string, pairs map[string]string, ownLID, ownPN string) {
	t.Helper()
	path := sessionPath(storePath)

	db, err := sql.Open("sqlite", "file:"+path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	if _, err := db.Exec(`
		create table whatsmeow_lid_map (lid text primary key, pn text unique not null);
		create table whatsmeow_device (jid text primary key, lid text);
	`); err != nil {
		t.Fatal(err)
	}
	for lid, pn := range pairs {
		if _, err := db.Exec(`insert into whatsmeow_lid_map (lid, pn) values (?, ?)`, lid, pn); err != nil {
			t.Fatal(err)
		}
	}
	if ownPN != "" {
		if _, err := db.Exec(`insert into whatsmeow_device (jid, lid) values (?, ?)`, ownPN, ownLID); err != nil {
			t.Fatal(err)
		}
	}
}

func jid(t *testing.T, s string) domain.JID {
	t.Helper()
	j, err := domain.ParseJID(s)
	if err != nil {
		t.Fatal(err)
	}
	return j
}

func TestLIDMapReadsThePairTable(t *testing.T) {
	path := newDB(t, 0)
	newSession(t, path, map[string]string{"48735396614220": "995568669331"}, "", "")

	m := loadLIDMap(sessionPath(path))
	if m.Len() != 1 {
		t.Fatalf("loaded %d pairs", m.Len())
	}
	got := m.Canonical(jid(t, "48735396614220@lid"))
	if got.String() != "995568669331@s.whatsapp.net" {
		t.Errorf("Canonical = %q", got)
	}
}

func TestLIDMapTakesTheDeviceRow(t *testing.T) {
	// The linked account's own pair matters most: a reaction sent from this
	// client comes back addressed to our own LID. whatsmeow writes both sides
	// of that row with a device suffix.
	path := newDB(t, 0)
	newSession(t, path, nil, "48735396614220:26@lid", "995568669331:26@s.whatsapp.net")

	m := loadLIDMap(sessionPath(path))
	got := m.Canonical(jid(t, "48735396614220@lid"))
	if got.String() != "995568669331@s.whatsapp.net" {
		t.Errorf("Canonical = %q", got)
	}
}

func TestLIDMapWithNoSessionDatabase(t *testing.T) {
	// An account WhatsApp has not migrated, or a store written by an older
	// wacli, must behave exactly as it did before LIDs existed.
	path := newDB(t, 0)
	m := loadLIDMap(sessionPath(path))

	if m.Len() != 0 {
		t.Errorf("loaded %d pairs from nothing", m.Len())
	}
	j := jid(t, "48735396614220@lid")
	if got := m.Canonical(j); got != j {
		t.Errorf("Canonical rewrote an unmapped LID to %q", got)
	}
	if got := m.Aliases(j); len(got) != 1 || got[0] != j.String() {
		t.Errorf("Aliases = %v", got)
	}
}

func TestLIDMapAliasesBothWays(t *testing.T) {
	path := newDB(t, 0)
	newSession(t, path, map[string]string{"48735396614220": "995568669331"}, "", "")
	m := loadLIDMap(sessionPath(path))

	fromPN := m.Aliases(jid(t, "995568669331@s.whatsapp.net"))
	fromLID := m.Aliases(jid(t, "48735396614220@lid"))
	for _, got := range [][]string{fromPN, fromLID} {
		if len(got) != 2 {
			t.Fatalf("Aliases = %v, want both addresses", got)
		}
	}
}

func TestLIDMapLeavesGroupsAlone(t *testing.T) {
	path := newDB(t, 0)
	newSession(t, path, map[string]string{"48735396614220": "995568669331"}, "", "")
	m := loadLIDMap(sessionPath(path))

	g := jid(t, "120363404077369111@g.us")
	if got := m.Canonical(g); got != g {
		t.Errorf("a group was rewritten to %q", got)
	}
	if got := m.Aliases(g); len(got) != 1 {
		t.Errorf("Aliases of a group = %v", got)
	}
}

func TestChatsFoldALIDRowIntoItsNumber(t *testing.T) {
	// This is the bug as it appears: the phone app shows one chat, and wa
	// showed two - the same person under a number and under a LID, each with
	// half the conversation.
	path := newDB(t, 0)
	newSession(t, path, map[string]string{"48735396614220": "995568669331"}, "", "")
	insertChats(t, path,
		chatRow{jid: "995568669331@s.whatsapp.net", kind: "dm", name: "Ucha", ts: 1000, unread: 1},
		chatRow{jid: "48735396614220@lid", kind: "unknown", name: "Ucha Bokeria", ts: 2000, unread: 2},
	)

	r, err := OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	chats, err := r.Chats(context.Background(), ChatFilter{})
	if err != nil {
		t.Fatal(err)
	}
	if len(chats) != 1 {
		for _, c := range chats {
			t.Logf("  %s  %q", c.JID, c.Name)
		}
		t.Fatalf("got %d chats, want 1", len(chats))
	}
	c := chats[0]
	if c.JID.String() != "995568669331@s.whatsapp.net" {
		t.Errorf("the surviving chat is %q", c.JID)
	}
	if c.LastMessageTS.Unix() != 2000 {
		t.Errorf("last activity = %d, want the newer row's 2000", c.LastMessageTS.Unix())
	}
	if c.UnreadCount != 3 {
		t.Errorf("unread = %d, want both rows counted", c.UnreadCount)
	}
}

func TestChatsKeepALIDRowWithNoNumber(t *testing.T) {
	// An unmapped LID is somebody wa knows nothing else about. Hiding it would
	// hide a real conversation.
	path := newDB(t, 0)
	newSession(t, path, nil, "", "")
	insertChats(t, path, chatRow{jid: "116075853262884@lid", kind: "unknown", ts: 1000})

	r, err := OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	chats, err := r.Chats(context.Background(), ChatFilter{})
	if err != nil {
		t.Fatal(err)
	}
	if len(chats) != 1 || chats[0].JID.String() != "116075853262884@lid" {
		t.Errorf("got %v", chats)
	}
}

func TestMessagesGatherBothAddresses(t *testing.T) {
	// The half of the conversation filed under the LID has to appear in the
	// chat opened by its number, or a reaction sent from this client vanishes.
	path := newDB(t, 0)
	newSession(t, path, map[string]string{"48735396614220": "995568669331"}, "", "")
	insertChats(t, path, chatRow{jid: "995568669331@s.whatsapp.net", kind: "dm", name: "Ucha", ts: 2000})
	insertMessage(t, path, msgRow{
		chat: "995568669331@s.whatsapp.net", id: "A", ts: 1000, fromMe: true, text: "under the number",
	})
	insertMessage(t, path, msgRow{
		chat: "48735396614220@lid", id: "B", ts: 2000, fromMe: true, text: "under the lid",
	})

	r, err := OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	got, err := r.Messages(context.Background(), MessageFilter{
		Chat: jid(t, "995568669331@s.whatsapp.net"),
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		for _, m := range got {
			t.Logf("  %s  %q", m.ChatJID, m.Text)
		}
		t.Fatalf("got %d messages, want both", len(got))
	}
	for _, m := range got {
		if m.ChatJID.String() != "995568669331@s.whatsapp.net" {
			t.Errorf("message %q reports chat %q", m.ID, m.ChatJID)
		}
	}
}

func TestAReactionFiledUnderTheLIDReachesItsMessage(t *testing.T) {
	// The whole point. A reaction sent from this client comes back addressed
	// to our own LID; the message it is on is under the number. Folding has to
	// see both, or the reaction never appears.
	path := newDB(t, 0)
	newSession(t, path, nil, "48735396614220:26@lid", "995568669331:26@s.whatsapp.net")
	insertChats(t, path, chatRow{jid: "995568669331@s.whatsapp.net", kind: "dm", name: "Ucha", ts: 2000})
	insertMessage(t, path, msgRow{
		chat: "995568669331@s.whatsapp.net", id: "TARGET", ts: 1000, fromMe: true, text: "probe",
	})
	insertReaction(t, path, "48735396614220@lid", "REACT", "TARGET", "👍", 2000)

	r, err := OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	got, err := r.Messages(context.Background(), MessageFilter{
		Chat: jid(t, "995568669331@s.whatsapp.net"),
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 {
		t.Fatalf("got %d messages, want the target with its reaction folded in", len(got))
	}
	if len(got[0].Reactions) != 1 || got[0].Reactions[0].Emoji != "👍" {
		t.Errorf("reactions = %+v", got[0].Reactions)
	}
}

func TestInClause(t *testing.T) {
	if got := inClause("c.jid", 1); got != "c.jid = ?" {
		t.Errorf("got %q", got)
	}
	if got := inClause("c.jid", 3); got != "c.jid in (?, ?, ?)" {
		t.Errorf("got %q", got)
	}
}

func TestSessionPathSitsBesideTheStore(t *testing.T) {
	got := sessionPath(filepath.Join("/x", "y", "wacli.db"))
	if got != filepath.Join("/x", "y", "session.db") {
		t.Errorf("got %q", got)
	}
}
