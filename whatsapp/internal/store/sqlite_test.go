package store

import (
	"context"
	"errors"
	"testing"
)

func TestChatsOrderPinnedFirstThenRecent(t *testing.T) {
	r, _ := fixture(t,
		chatRow{jid: "a@s.whatsapp.net", name: "Ana", ts: 100},
		chatRow{jid: "b@s.whatsapp.net", name: "Beka", ts: 300},
		chatRow{jid: "c@s.whatsapp.net", name: "Cezar", ts: 50, pinned: true},
	)
	got, err := r.Chats(context.Background(), ChatFilter{})
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"Cezar", "Beka", "Ana"}
	for i := range want {
		if got[i].Name != want[i] {
			t.Fatalf("order = %v, want %v", names(got), want)
		}
	}
}

func TestChatsHideArchivedByDefault(t *testing.T) {
	r, _ := fixture(t,
		chatRow{jid: "a@s.whatsapp.net", name: "Ana"},
		chatRow{jid: "b@s.whatsapp.net", name: "Beka", archived: true},
	)
	ctx := context.Background()

	got, _ := r.Chats(ctx, ChatFilter{})
	if len(got) != 1 || got[0].Name != "Ana" {
		t.Errorf("default view = %v, want just Ana", names(got))
	}
	got, _ = r.Chats(ctx, ChatFilter{Archived: true})
	if len(got) != 1 || got[0].Name != "Beka" {
		t.Errorf("archived filter = %v, want just Beka", names(got))
	}
	got, _ = r.Chats(ctx, ChatFilter{IncludeArchived: true})
	if len(got) != 2 {
		t.Errorf("IncludeArchived = %v, want both", names(got))
	}
}

func TestChatsFilters(t *testing.T) {
	r, _ := fixture(t,
		chatRow{jid: "a@s.whatsapp.net", name: "Ana"},
		chatRow{jid: "b@s.whatsapp.net", name: "Beka", unread: 3},
		chatRow{jid: "c@s.whatsapp.net", name: "Cezar", pinned: true},
		chatRow{jid: "120363000000000001@g.us", kind: "group", name: "Team"},
		chatRow{jid: "d@s.whatsapp.net", name: "Dato", muted: hoursAgo(-2)},
	)
	ctx := context.Background()

	cases := []struct {
		name   string
		filter ChatFilter
		want   []string
	}{
		{"unread", ChatFilter{Unread: true}, []string{"Beka"}},
		{"pinned", ChatFilter{Pinned: true}, []string{"Cezar"}},
		{"groups", ChatFilter{Groups: true}, []string{"Team"}},
		{"muted", ChatFilter{Muted: true}, []string{"Dato"}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got, err := r.Chats(ctx, c.filter)
			if err != nil {
				t.Fatal(err)
			}
			if len(got) != len(c.want) {
				t.Fatalf("got %v, want %v", names(got), c.want)
			}
			for i := range c.want {
				if got[i].Name != c.want[i] {
					t.Fatalf("got %v, want %v", names(got), c.want)
				}
			}
		})
	}
}

func TestChatsUnreadCountSurvives(t *testing.T) {
	r, _ := fixture(t, chatRow{jid: "b@s.whatsapp.net", name: "Beka", unread: 7})
	got, _ := r.Chats(context.Background(), ChatFilter{})
	if got[0].UnreadCount != 7 || !got[0].Unread {
		t.Errorf("unread = %v/%d, want true/7", got[0].Unread, got[0].UnreadCount)
	}
}

func TestChatSnippetIsTheNewestMessage(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana", ts: 200})
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M1", ts: 100, text: "older"})
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M2", ts: 200, text: "newest"})

	got, err := r.Chats(context.Background(), ChatFilter{})
	if err != nil {
		t.Fatal(err)
	}
	if got[0].LastSnippet != "newest" {
		t.Errorf("snippet = %q, want %q", got[0].LastSnippet, "newest")
	}
}

func TestChatNotFoundIsTyped(t *testing.T) {
	r, _ := fixture(t)
	_, err := r.Chat(context.Background(), mustJID(t, "nobody@s.whatsapp.net"))
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestMessagesNewestFirstByDefault(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	seedMessages(t, path, "a@s.whatsapp.net", 5)

	got, err := r.Messages(context.Background(), MessageFilter{Chat: mustJID(t, "a@s.whatsapp.net")})
	if err != nil {
		t.Fatal(err)
	}
	if got[0].ID != "M5" {
		t.Errorf("first = %s, want the newest M5 (order %v)", got[0].ID, ids(got))
	}

	asc, _ := r.Messages(context.Background(), MessageFilter{
		Chat: mustJID(t, "a@s.whatsapp.net"), Ascending: true,
	})
	if asc[0].ID != "M1" {
		t.Errorf("ascending first = %s, want M1", asc[0].ID)
	}
}

func TestMessagesKeysetPagesWithoutRepeatingOrSkipping(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	seedMessages(t, path, "a@s.whatsapp.net", 10)
	jid := mustJID(t, "a@s.whatsapp.net")
	ctx := context.Background()

	seen := map[string]bool{}
	var cursor MessageFilter
	cursor.Chat = jid
	cursor.Limit = 4

	for page := 0; page < 5; page++ {
		got, err := r.Messages(ctx, cursor)
		if err != nil {
			t.Fatal(err)
		}
		if len(got) == 0 {
			break
		}
		for _, m := range got {
			if seen[m.ID] {
				t.Fatalf("page %d repeated %s", page, m.ID)
			}
			seen[m.ID] = true
		}
		last := got[len(got)-1]
		cursor.BeforeTS = last.TS
		cursor.BeforeRowID = last.RowID
	}
	if len(seen) != 10 {
		t.Errorf("paged through %d messages, want 10", len(seen))
	}
}

func TestMessagesKeysetHandlesTiesInTimestamp(t *testing.T) {
	// Two messages in the same second: ts alone is not a cursor.
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	for i, id := range []string{"M1", "M2", "M3", "M4"} {
		insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: id, ts: 1000, text: id})
		_ = i
	}
	jid := mustJID(t, "a@s.whatsapp.net")
	ctx := context.Background()

	first, _ := r.Messages(ctx, MessageFilter{Chat: jid, Limit: 2})
	if len(first) != 2 {
		t.Fatalf("page 1 = %v", ids(first))
	}
	last := first[1]
	second, _ := r.Messages(ctx, MessageFilter{
		Chat: jid, Limit: 2, BeforeTS: last.TS, BeforeRowID: last.RowID,
	})
	for _, m := range second {
		for _, f := range first {
			if m.ID == f.ID {
				t.Fatalf("tie in ts repeated %s across pages", m.ID)
			}
		}
	}
	if len(second) != 2 {
		t.Errorf("page 2 = %v, want the remaining two", ids(second))
	}
}

func TestMessagesSkipDeletedForMe(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M1", ts: 1, text: "kept"})
	db := writable(t, path)
	if _, err := db.Exec(`
insert into messages(chat_jid, msg_id, ts, from_me, text, is_forwarded, revoked,
                     deleted_for_me, edited, edited_ts)
values('a@s.whatsapp.net', 'M2', 2, 0, 'gone', 0, 0, 1, 0, 0)`); err != nil {
		t.Fatal(err)
	}
	got, _ := r.Messages(context.Background(), MessageFilter{Chat: mustJID(t, "a@s.whatsapp.net")})
	if len(got) != 1 || got[0].ID != "M1" {
		t.Errorf("got %v, want only M1", ids(got))
	}
}

func TestMessageMapsQuotedMediaAndFlags(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	insertMessage(t, path, msgRow{
		chat: "a@s.whatsapp.net", id: "M2", ts: 20, text: "look",
		quoted: "M1", mediaType: "image", filename: "shot.png",
		localPath: "/tmp/shot.png", downloadedAt: 99, edited: true,
	})
	m, err := r.Message(context.Background(), mustJID(t, "a@s.whatsapp.net"), "M2")
	if err != nil {
		t.Fatal(err)
	}
	if m.QuotedID != "M1" {
		t.Errorf("QuotedID = %q", m.QuotedID)
	}
	if m.Media == nil || m.Media.Type != "image" || !m.Media.Downloaded() {
		t.Errorf("Media = %+v", m.Media)
	}
	if !m.Edited {
		t.Error("Edited was not carried")
	}
}

func TestMessageWithoutMediaHasNilMediaRef(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M1", ts: 1, text: "plain"})
	m, _ := r.Message(context.Background(), mustJID(t, "a@s.whatsapp.net"), "M1")
	if m.Media != nil {
		t.Errorf("Media = %+v, want nil for a text message", m.Media)
	}
}

func TestMessageNotFoundIsTyped(t *testing.T) {
	r, _ := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	_, err := r.Message(context.Background(), mustJID(t, "a@s.whatsapp.net"), "nope")
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestSearchUsesFTS(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M1", ts: 1, text: "deploy the nuc branch"})
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M2", ts: 2, text: "lunch?"})

	got, err := r.Search(context.Background(), Query{Text: "nuc"})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].ID != "M1" {
		t.Fatalf("search returned %v, want just M1", ids(got))
	}
}

func TestSearchAcceptsPunctuationWithoutSyntaxError(t *testing.T) {
	// A user typing "don't" or "a-b" must not hit an FTS5 parse error
	// mid-keystroke.
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M1", ts: 1, text: "don't stop"})

	for _, q := range []string{"don't", "a-b", `"`, "NEAR", "AND", "*", "^x"} {
		if _, err := r.Search(context.Background(), Query{Text: q}); err != nil {
			t.Errorf("Search(%q) = %v, want no error", q, err)
		}
	}
}

func TestSearchNarrowsToAChat(t *testing.T) {
	r, path := fixture(t,
		chatRow{jid: "a@s.whatsapp.net", name: "Ana"},
		chatRow{jid: "b@s.whatsapp.net", name: "Beka"},
	)
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M1", ts: 1, text: "nuc here"})
	insertMessage(t, path, msgRow{chat: "b@s.whatsapp.net", id: "M2", ts: 2, text: "nuc there"})

	got, _ := r.Search(context.Background(), Query{Text: "nuc", Chat: mustJID(t, "b@s.whatsapp.net")})
	if len(got) != 1 || got[0].ID != "M2" {
		t.Errorf("got %v, want just M2", ids(got))
	}
}

func TestSearchWithMediaFilter(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M1", ts: 1, text: "report"})
	insertMessage(t, path, msgRow{chat: "a@s.whatsapp.net", id: "M2", ts: 2, text: "report",
		mediaType: "document", filename: "report.pdf"})

	got, _ := r.Search(context.Background(), Query{Text: "report", HasMedia: true})
	if len(got) != 1 || got[0].ID != "M2" {
		t.Errorf("got %v, want just M2", ids(got))
	}
}

func TestSearchOfEmptyTextReturnsNothing(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	seedMessages(t, path, "a@s.whatsapp.net", 3)
	got, err := r.Search(context.Background(), Query{Text: "   "})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 0 {
		t.Errorf("empty search returned %d rows; it must not dump the archive", len(got))
	}
}

func TestStats(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	seedMessages(t, path, "a@s.whatsapp.net", 4)

	st, err := r.Stats(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.Messages != 4 || st.Chats != 1 {
		t.Errorf("stats = %+v", st)
	}
	if st.MaxRowID == 0 || st.LastMessageTS.IsZero() {
		t.Errorf("the polling source needs MaxRowID and LastMessageTS: %+v", st)
	}
}

func TestStatsOnAnEmptyStore(t *testing.T) {
	r, _ := fixture(t)
	st, err := r.Stats(context.Background())
	if err != nil {
		t.Fatalf("an empty store must not be an error: %v", err)
	}
	if st.Messages != 0 || st.MaxRowID != 0 {
		t.Errorf("stats = %+v", st)
	}
}

func TestContact(t *testing.T) {
	r, path := fixture(t)
	db := writable(t, path)
	db.Exec(`insert into contacts(jid, phone, push_name, full_name, updated_at)
	         values('a@s.whatsapp.net', '995', 'anapush', 'Ana Full', 0)`)
	db.Exec(`insert into contact_aliases(jid, alias, updated_at) values('a@s.whatsapp.net', 'anka', 0)`)
	db.Exec(`insert into contact_tags(jid, tag, updated_at) values('a@s.whatsapp.net', 'work', 0)`)

	c, err := r.Contact(context.Background(), mustJID(t, "a@s.whatsapp.net"))
	if err != nil {
		t.Fatal(err)
	}
	if c.DisplayName() != "anka" {
		t.Errorf("DisplayName = %q, want the local alias to win", c.DisplayName())
	}
	if len(c.Tags) != 1 || c.Tags[0] != "work" {
		t.Errorf("Tags = %v", c.Tags)
	}
}

func TestConnectionIsReadOnly(t *testing.T) {
	r, _ := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Ana"})
	s := r.(*sqliteReader)
	if _, err := s.db.Exec("delete from chats"); err == nil {
		t.Fatal("the store connection accepted a write; mode=ro is what keeps wa from corrupting wacli's data")
	}
}

func TestProbeAcceptsTheKnownVersion(t *testing.T) {
	v, ok, reason, err := Probe(fixturePath(t, KnownMigration))
	if err != nil {
		t.Fatal(err)
	}
	if !ok || v != KnownMigration {
		t.Fatalf("Probe = (%d, %v, %q)", v, ok, reason)
	}
}

func TestProbeAcceptsAnOlderVersion(t *testing.T) {
	// An older store cannot have moved a column we read.
	_, ok, reason, err := Probe(fixturePath(t, KnownMigration-3))
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatalf("an older schema was rejected: %s", reason)
	}
}

func TestProbeRejectsANewerVersion(t *testing.T) {
	v, ok, reason, err := Probe(fixturePath(t, KnownMigration+5))
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("a newer schema must not take the direct-read path")
	}
	if v != KnownMigration+5 || reason == "" {
		t.Errorf("Probe = (%d, %v, %q), want a stated reason", v, ok, reason)
	}
}

func TestProbeRejectsAMissingColumn(t *testing.T) {
	path := fixturePath(t, KnownMigration)
	db := writable(t, path)
	if _, err := db.Exec(`alter table chats drop column unread_count`); err != nil {
		t.Skipf("this SQLite cannot drop a column: %v", err)
	}
	_, ok, reason, err := Probe(path)
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("a store missing a column we read must not take the direct path")
	}
	if reason == "" {
		t.Error("the reason must name what is missing")
	}
}

func TestGroupNameComesFromTheGroupsTable(t *testing.T) {
	// wacli leaves chats.name empty for most groups and keeps the name in
	// `groups`. Reading only chats.name gives a list of raw JIDs.
	r, path := fixture(t, chatRow{jid: "120363000000000001@g.us", kind: "group", name: ""})
	db := writable(t, path)
	if _, err := db.Exec(
		`insert into groups(jid, name, updated_at) values('120363000000000001@g.us', 'Team Blackwall', 0)`); err != nil {
		t.Fatal(err)
	}

	got, err := r.Chats(context.Background(), ChatFilter{})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Name != "Team Blackwall" {
		t.Fatalf("chat name = %q, want the group's name", got[0].Name)
	}
}

func TestChatNameFallsBackToTheContact(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: ""})
	db := writable(t, path)
	db.Exec(`insert into contacts(jid, push_name, updated_at) values('a@s.whatsapp.net', 'Anapush', 0)`)

	got, _ := r.Chats(context.Background(), ChatFilter{})
	if got[0].Name != "Anapush" {
		t.Errorf("chat name = %q, want the contact's push name", got[0].Name)
	}
}

func TestFullNameBeatsPushName(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: ""})
	db := writable(t, path)
	db.Exec(`insert into contacts(jid, push_name, full_name, updated_at)
	         values('a@s.whatsapp.net', 'Anapush', 'Ana Full', 0)`)

	got, _ := r.Chats(context.Background(), ChatFilter{})
	if got[0].Name != "Ana Full" {
		t.Errorf("chat name = %q, want the address-book name to win", got[0].Name)
	}
}

func TestChatOwnNameWins(t *testing.T) {
	r, path := fixture(t, chatRow{jid: "a@s.whatsapp.net", name: "Renamed"})
	db := writable(t, path)
	db.Exec(`insert into contacts(jid, full_name, updated_at) values('a@s.whatsapp.net', 'Ana Full', 0)`)

	got, _ := r.Chats(context.Background(), ChatFilter{})
	if got[0].Name != "Renamed" {
		t.Errorf("chat name = %q, want the chat's own name", got[0].Name)
	}
}
