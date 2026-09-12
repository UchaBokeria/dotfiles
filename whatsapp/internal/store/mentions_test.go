package store

import (
	"context"
	"testing"
)

func insertContact(t *testing.T, path, jid, full, push string) {
	t.Helper()
	db := writable(t, path)
	if _, err := db.Exec(`insert into contacts(jid, full_name, push_name, updated_at)
values(?, ?, ?, 0)`, jid, full, push); err != nil {
		t.Fatalf("seeding contact %s: %v", jid, err)
	}
}

func messageText(t *testing.T, path, chat string) string {
	t.Helper()
	r, err := OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	got, err := r.Messages(context.Background(), MessageFilter{Chat: jid(t, chat)})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 {
		t.Fatalf("got %d messages", len(got))
	}
	return got[0].Text
}

func TestAMentionByLIDBecomesAName(t *testing.T) {
	// WhatsApp stores a mention as the person's LID digits. The phone draws
	// their name; wa drew "@148777784619227".
	path := newDB(t, 0)
	newSession(t, path, map[string]string{"148777784619227": "995571990229"}, "", "")
	insertContact(t, path, "995571990229@s.whatsapp.net", "rezi", "Rezi Parulava")
	insertChats(t, path, chatRow{jid: "120363404077369111@g.us", kind: "group", name: "Billi", ts: 1})
	insertMessage(t, path, msgRow{
		chat: "120363404077369111@g.us", id: "M", ts: 1, text: "ask @148777784619227 about it",
	})

	if got := messageText(t, path, "120363404077369111@g.us"); got != "ask @rezi about it" {
		t.Errorf("Text = %q", got)
	}
}

func TestAMentionByNumberBecomesAName(t *testing.T) {
	path := newDB(t, 0)
	newSession(t, path, nil, "", "")
	insertContact(t, path, "995571990229@s.whatsapp.net", "rezi", "")
	insertChats(t, path, chatRow{jid: "995000000000@s.whatsapp.net", kind: "dm", ts: 1})
	insertMessage(t, path, msgRow{
		chat: "995000000000@s.whatsapp.net", id: "M", ts: 1, text: "@995571990229 hi",
	})

	if got := messageText(t, path, "995000000000@s.whatsapp.net"); got != "@rezi hi" {
		t.Errorf("Text = %q", got)
	}
}

func TestANameThatIsOnlyTheNumberIsSkipped(t *testing.T) {
	// Your own address-book entry is usually your number again. Replacing the
	// digits with the same digits, formatted, is not a name.
	path := newDB(t, 0)
	newSession(t, path, map[string]string{"48735396614220": "995568669331"}, "", "")
	insertContact(t, path, "995568669331@s.whatsapp.net", "+995 568 66 93 31", "Ucha Bokeria")
	insertChats(t, path, chatRow{jid: "995000000000@s.whatsapp.net", kind: "dm", ts: 1})
	insertMessage(t, path, msgRow{
		chat: "995000000000@s.whatsapp.net", id: "M", ts: 1, text: "@48735396614220 look",
	})

	if got := messageText(t, path, "995000000000@s.whatsapp.net"); got != "@Ucha Bokeria look" {
		t.Errorf("Text = %q", got)
	}
}

func TestAnUnknownMentionIsLeftAlone(t *testing.T) {
	path := newDB(t, 0)
	newSession(t, path, nil, "", "")
	insertChats(t, path, chatRow{jid: "995000000000@s.whatsapp.net", kind: "dm", ts: 1})
	insertMessage(t, path, msgRow{
		chat: "995000000000@s.whatsapp.net", id: "M", ts: 1,
		text: "@123456789012 and an email a@b.com and a price @5",
	})

	want := "@123456789012 and an email a@b.com and a price @5"
	if got := messageText(t, path, "995000000000@s.whatsapp.net"); got != want {
		t.Errorf("Text = %q", got)
	}
}

func TestLooksLikeNumber(t *testing.T) {
	for in, want := range map[string]bool{
		"+995 568 66 93 31": true,
		"(555) 123-4567":    true,
		"rezi":              false,
		"Ucha Bokeria":      false,
		"":                  false,
		"R2D2":              false,
	} {
		if got := looksLikeNumber(in); got != want {
			t.Errorf("looksLikeNumber(%q) = %v", in, got)
		}
	}
}
