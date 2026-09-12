package store

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

func TestQuoteLogRoundTrips(t *testing.T) {
	path := filepath.Join(t.TempDir(), "sent-quotes.json")

	q := OpenQuoteLog(path)
	q.Record("SENT", Quote{QuotedID: "TARGET", QuotedSender: "995000000000@s.whatsapp.net", QuotedText: "hello"})
	if err := q.Save(); err != nil {
		t.Fatal(err)
	}

	again := OpenQuoteLog(path)
	got, ok := again.Lookup("SENT")
	if !ok {
		t.Fatal("the record did not survive")
	}
	if got.QuotedID != "TARGET" || got.QuotedText != "hello" {
		t.Errorf("got %+v", got)
	}
	if got.At == 0 {
		t.Error("no timestamp recorded")
	}
}

func TestQuoteLogIgnoresNonsense(t *testing.T) {
	q := OpenQuoteLog(filepath.Join(t.TempDir(), "q.json"))
	q.Record("", Quote{QuotedID: "T"})
	q.Record("SENT", Quote{})
	if q.Len() != 0 {
		t.Errorf("recorded %d entries", q.Len())
	}
}

func TestQuoteLogSurvivesAMissingFile(t *testing.T) {
	q := OpenQuoteLog(filepath.Join(t.TempDir(), "nope", "q.json"))
	if q.Len() != 0 {
		t.Errorf("loaded %d entries from nothing", q.Len())
	}
	q.Record("SENT", Quote{QuotedID: "T"})
	if err := q.Save(); err != nil {
		t.Errorf("saving into a missing directory: %v", err)
	}
}

func TestQuoteLogSurvivesGarbage(t *testing.T) {
	// A truncated write must cost the quote bars, not the program.
	path := filepath.Join(t.TempDir(), "q.json")
	if err := os.WriteFile(path, []byte("{not json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if q := OpenQuoteLog(path); q.Len() != 0 {
		t.Errorf("loaded %d entries from garbage", q.Len())
	}
}

func TestQuoteLogAppliesToAMessage(t *testing.T) {
	q := OpenQuoteLog(filepath.Join(t.TempDir(), "q.json"))
	q.Record("SENT", Quote{QuotedID: "TARGET", QuotedSender: "995000000000@s.whatsapp.net", QuotedText: "hello"})

	got := q.Apply(domain.Message{ID: "SENT", FromMe: true})
	if got.QuotedID != "TARGET" {
		t.Errorf("QuotedID = %q", got.QuotedID)
	}
	if got.QuotedText != "hello" {
		t.Errorf("QuotedText = %q", got.QuotedText)
	}
	if got.QuotedSender.User != "995000000000" {
		t.Errorf("QuotedSender = %q", got.QuotedSender)
	}
}

func TestQuoteLogNeverOverridesTheStore(t *testing.T) {
	// What WhatsApp says a message quoted is the truth. wa's own note is only
	// there for the gap wacli leaves.
	q := OpenQuoteLog(filepath.Join(t.TempDir(), "q.json"))
	q.Record("SENT", Quote{QuotedID: "WRONG"})

	got := q.Apply(domain.Message{ID: "SENT", FromMe: true, QuotedID: "REAL"})
	if got.QuotedID != "REAL" {
		t.Errorf("QuotedID = %q", got.QuotedID)
	}
}

func TestQuoteLogLeavesIncomingMessagesAlone(t *testing.T) {
	// wa only ever sends its own messages, so a match on somebody else's id
	// would be a collision, not a record.
	q := OpenQuoteLog(filepath.Join(t.TempDir(), "q.json"))
	q.Record("SENT", Quote{QuotedID: "TARGET"})

	got := q.Apply(domain.Message{ID: "SENT"})
	if got.QuotedID != "" {
		t.Errorf("QuotedID = %q on an incoming message", got.QuotedID)
	}
}

func TestNilQuoteLogIsSafe(t *testing.T) {
	var q *QuoteLog
	q.Record("SENT", Quote{QuotedID: "T"})
	if _, ok := q.Lookup("SENT"); ok {
		t.Error("a nil log found something")
	}
	if got := q.Apply(domain.Message{ID: "SENT", FromMe: true}); got.QuotedID != "" {
		t.Error("a nil log changed a message")
	}
	if err := q.Save(); err != nil {
		t.Error(err)
	}
	if q.Len() != 0 {
		t.Error("a nil log has entries")
	}
}

func TestQuoteLogIsBounded(t *testing.T) {
	path := filepath.Join(t.TempDir(), "q.json")
	q := OpenQuoteLog(path)
	for i := 0; i < maxQuotes+50; i++ {
		q.Record(string(rune('a'+i%26))+itoaTest(i), Quote{QuotedID: "T", At: int64(i)})
	}
	if err := q.Save(); err != nil {
		t.Fatal(err)
	}
	if n := OpenQuoteLog(path).Len(); n > maxQuotes {
		t.Errorf("saved %d entries, cap is %d", n, maxQuotes)
	}
}

func itoaTest(n int) string {
	if n == 0 {
		return "0"
	}
	var b []byte
	for n > 0 {
		b = append([]byte{byte('0' + n%10)}, b...)
		n /= 10
	}
	return string(b)
}

func TestAReplySentFromWaKeepsItsQuote(t *testing.T) {
	// wacli sends the quote but writes no quoted_msg_id, and the phone never
	// fills it in, so a reply sent from wa showed as a plain message in the
	// one place the person who sent it was looking.
	path := newDB(t, 0)
	insertChats(t, path, chatRow{jid: "995000000000@s.whatsapp.net", kind: "dm", name: "Someone", ts: 2000})
	insertMessage(t, path, msgRow{chat: "995000000000@s.whatsapp.net", id: "TARGET", ts: 1000, text: "question"})
	insertMessage(t, path, msgRow{chat: "995000000000@s.whatsapp.net", id: "REPLY", ts: 2000, fromMe: true, text: "answer"})

	r, err := OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	q := OpenQuoteLog(filepath.Join(t.TempDir(), "q.json"))
	q.Record("REPLY", Quote{QuotedID: "TARGET", QuotedText: "question"})
	SetQuoteLog(r, q)

	got, err := r.Messages(context.Background(), MessageFilter{Chat: jid(t, "995000000000@s.whatsapp.net")})
	if err != nil {
		t.Fatal(err)
	}
	for _, m := range got {
		if m.ID != "REPLY" {
			continue
		}
		if m.QuotedID != "TARGET" || m.QuotedText != "question" {
			t.Errorf("the reply lost its quote: %+v", m)
		}
		return
	}
	t.Fatal("the reply was not returned")
}

func TestAQuoteShowsTheWordsItQuoted(t *testing.T) {
	// wacli stores the reference, not the text. Without looking the target up,
	// every quote bar in the conversation reads as an ellipsis.
	path := newDB(t, 0)
	insertChats(t, path, chatRow{jid: "995000000000@s.whatsapp.net", kind: "dm", name: "Someone", ts: 2000})
	insertMessage(t, path, msgRow{chat: "995000000000@s.whatsapp.net", id: "TARGET", ts: 1000, text: "what time?"})
	insertMessage(t, path, msgRow{
		chat: "995000000000@s.whatsapp.net", id: "REPLY", ts: 2000, text: "six", quoted: "TARGET",
	})

	r, err := OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	got, err := r.Messages(context.Background(), MessageFilter{Chat: jid(t, "995000000000@s.whatsapp.net")})
	if err != nil {
		t.Fatal(err)
	}
	for _, m := range got {
		if m.ID != "REPLY" {
			continue
		}
		if m.QuotedText != "what time?" {
			t.Errorf("QuotedText = %q", m.QuotedText)
		}
		return
	}
	t.Fatal("the reply was not returned")
}

func TestAQuoteOfAMessageNotInTheStore(t *testing.T) {
	// Replying to something older than the sync window is normal; the bar
	// should still be drawn, just without words.
	path := newDB(t, 0)
	insertChats(t, path, chatRow{jid: "995000000000@s.whatsapp.net", kind: "dm", name: "Someone", ts: 2000})
	insertMessage(t, path, msgRow{
		chat: "995000000000@s.whatsapp.net", id: "REPLY", ts: 2000, text: "six", quoted: "GONE",
	})

	r, err := OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	got, err := r.Messages(context.Background(), MessageFilter{Chat: jid(t, "995000000000@s.whatsapp.net")})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 {
		t.Fatalf("got %d messages", len(got))
	}
	if got[0].QuotedID != "GONE" {
		t.Errorf("QuotedID = %q", got[0].QuotedID)
	}
	if got[0].QuotedText != "" {
		t.Errorf("QuotedText = %q, want empty", got[0].QuotedText)
	}
}
