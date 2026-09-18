package live

import (
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

func TestDecodeTheReceiptWacliActuallyPosts(t *testing.T) {
	// wacli's webhook uses Go field names and an RFC 3339 timestamp. Reading
	// the snake_case spelling alone turned every receipt into an unrecognised
	// message event, which is why nothing ever showed two ticks.
	body := []byte(`{"EventType":"receipt","Chat":"120363000000000000@g.us",` +
		`"Sender":"15551234567@s.whatsapp.net","MessageIDs":["3EB0A","3EB0B"],` +
		`"Timestamp":"2026-07-25T10:00:01Z","Type":"read","IsFromMe":false}`)

	ev, ok := decode(body)
	if !ok {
		t.Fatal("the payload did not decode")
	}
	if ev.Kind != domain.EventReceipt {
		t.Errorf("kind = %q", ev.Kind)
	}
	if ev.Receipt != domain.Read {
		t.Errorf("state = %v, want read", ev.Receipt)
	}
	if len(ev.MessageIDs) != 2 || ev.MessageIDs[0] != "3EB0A" {
		t.Errorf("ids = %v", ev.MessageIDs)
	}
	if ev.Chat.String() != "120363000000000000@g.us" {
		t.Errorf("chat = %q", ev.Chat)
	}
	if ev.Sender.User != "15551234567" {
		t.Errorf("sender = %q", ev.Sender)
	}
	if !ev.At.Equal(time.Date(2026, 7, 25, 10, 0, 1, 0, time.UTC)) {
		t.Errorf("at = %v", ev.At)
	}
}

func TestAnEmptyReceiptTypeMeansDelivered(t *testing.T) {
	// WhatsApp sends "delivered" as an empty string on the wire; wacli spells
	// it out, but both reach here.
	for _, body := range []string{
		`{"EventType":"receipt","Chat":"1@s.whatsapp.net","MessageIDs":["A"],"Type":""}`,
		`{"EventType":"receipt","Chat":"1@s.whatsapp.net","MessageIDs":["A"],"Type":"delivered"}`,
	} {
		ev, ok := decode([]byte(body))
		if !ok || ev.Receipt != domain.Delivered {
			t.Errorf("%s decoded as %v (ok=%v)", body, ev.Receipt, ok)
		}
	}
	ev, _ := decode([]byte(`{"EventType":"receipt","Chat":"1@s.whatsapp.net","MessageIDs":["A"],"Type":"played"}`))
	if ev.Receipt != domain.Read {
		t.Errorf("a played voice note is a read receipt, got %v", ev.Receipt)
	}
}

func TestAMessagePayloadHasNoDiscriminator(t *testing.T) {
	ev, ok := decode([]byte(`{"Chat":"15551234567@s.whatsapp.net","ID":"3EB0",` +
		`"SenderJID":"15551234567@s.whatsapp.net","Timestamp":"2026-07-25T10:00:00Z",` +
		`"FromMe":false,"Text":"hi","ChatName":"Alice"}`))
	if !ok {
		t.Fatal("the payload did not decode")
	}
	if ev.Kind != domain.EventMessage {
		t.Errorf("kind = %q, want message", ev.Kind)
	}
	if ev.MessageID != "3EB0" {
		t.Errorf("id = %q", ev.MessageID)
	}
	if ev.Chat.User != "15551234567" {
		t.Errorf("chat = %q", ev.Chat)
	}
}

func TestTypingStateStillDecodes(t *testing.T) {
	ev, ok := decode([]byte(`{"EventType":"chat_presence","Chat":"1@s.whatsapp.net",` +
		`"Sender":"1@s.whatsapp.net","State":"composing","Media":""}`))
	if !ok || ev.Kind != domain.EventChatPresence || ev.State != "composing" {
		t.Errorf("presence decoded as %+v (ok=%v)", ev, ok)
	}
}
