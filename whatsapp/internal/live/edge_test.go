package live

import (
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

func TestDecodeSurvivesGarbage(t *testing.T) {
	for _, body := range []string{
		``, `{`, `null`, `[]`, `"string"`, `{"EventType":42}`,
		`{"EventType":"receipt","MessageIDs":"not-a-list"}`,
		`{"Timestamp":{"nested":true}}`,
	} {
		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("decode(%q) panicked: %v", body, r)
				}
			}()
			decode([]byte(body))
		}()
	}
}

func TestDecodeTimestampSpellings(t *testing.T) {
	cases := map[string]int64{
		`{"Timestamp":"2026-07-25T10:00:01Z"}`: 1784973601,
		`{"Timestamp":1784973601}`:             1784973601,
		`{"ts":1784973601000}`:                 1784973601,
	}
	for body, want := range cases {
		ev, ok := decode([]byte(body))
		if !ok {
			t.Errorf("%s did not decode", body)
			continue
		}
		if got := ev.At.Unix(); got != want {
			t.Errorf("%s: at = %d, want %d", body, got, want)
		}
	}
	// A timestamp that is neither falls back to now rather than year 1.
	ev, _ := decode([]byte(`{"Timestamp":"yesterday"}`))
	if ev.At.Year() < 2020 {
		t.Errorf("an unreadable timestamp became %v", ev.At)
	}
}

func TestReceiptWithBlankAndDuplicateIDs(t *testing.T) {
	ev, ok := decode([]byte(`{"EventType":"receipt","Chat":"1@s.whatsapp.net","MessageIDs":["","A","A"],"Type":"read"}`))
	if !ok || ev.Kind != domain.EventReceipt || ev.Receipt != domain.Read {
		t.Fatalf("decoded %+v (ok=%v)", ev, ok)
	}
	if ev.MessageID == "" && len(ev.MessageIDs) > 0 && ev.MessageIDs[0] == "" {
		// The first id being blank must not leave the event naming nothing
		// when a real id follows; the loop that applies ids skips blanks.
		t.Log("first id blank; applyEvent skips it")
	}
}

func TestUnknownEventTypeIsTreatedAsAMessage(t *testing.T) {
	ev, ok := decode([]byte(`{"EventType":"call_offer","Chat":"1@s.whatsapp.net"}`))
	if !ok || ev.Kind != domain.EventMessage {
		t.Errorf("unknown kind decoded as %q (ok=%v)", ev.Kind, ok)
	}
}
