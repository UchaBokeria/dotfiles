package live

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"sync"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
)

func sign(secret string, body []byte) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write(body)
	return hex.EncodeToString(m.Sum(nil))
}

func post(t *testing.T, w *Webhook, secret string, body string) int {
	t.Helper()
	req, err := http.NewRequest("POST",
		fmt.Sprintf("http://127.0.0.1:%d/e", w.Port()), bytes.NewReader([]byte(body)))
	if err != nil {
		t.Fatal(err)
	}
	if secret != "" {
		req.Header.Set("X-Wacli-Signature", sign(secret, []byte(body)))
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	return resp.StatusCode
}

func waitEvent(t *testing.T, s Source) (domain.Event, bool) {
	t.Helper()
	select {
	case ev := <-s.Events():
		return ev, true
	case <-time.After(2 * time.Second):
		return domain.Event{}, false
	}
}

func TestWebhookAcceptsASignedMessageEvent(t *testing.T) {
	w, err := NewWebhook("s3cret", 8)
	if err != nil {
		t.Fatal(err)
	}
	defer w.Close()

	body := `{"type":"message","chat_jid":"a@s.whatsapp.net","msg_id":"M1","ts":1757000000}`
	if code := post(t, w, "s3cret", body); code != http.StatusOK {
		t.Fatalf("status = %d", code)
	}
	ev, ok := waitEvent(t, w)
	if !ok {
		t.Fatal("no event arrived")
	}
	if ev.Kind != domain.EventMessage || ev.Chat.User != "a" || ev.MessageID != "M1" {
		t.Errorf("event = %+v", ev)
	}
}

func TestWebhookRejectsABadSignature(t *testing.T) {
	w, _ := NewWebhook("s3cret", 8)
	defer w.Close()

	body := `{"type":"message","chat_jid":"a@s.whatsapp.net","msg_id":"M1"}`
	if code := post(t, w, "wrong", body); code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", code)
	}
	select {
	case ev := <-w.Events():
		t.Fatalf("an unsigned event reached the interface: %+v", ev)
	case <-time.After(150 * time.Millisecond):
	}
}

func TestWebhookRejectsAMissingSignature(t *testing.T) {
	w, _ := NewWebhook("s3cret", 8)
	defer w.Close()
	if code := post(t, w, "", `{"type":"message"}`); code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401 for an unsigned post", code)
	}
}

func TestWebhookRejectsGet(t *testing.T) {
	w, _ := NewWebhook("s", 8)
	defer w.Close()
	resp, err := http.Get(fmt.Sprintf("http://127.0.0.1:%d/e", w.Port()))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Errorf("status = %d, want 405", resp.StatusCode)
	}
}

func TestWebhookDropsOldestUnderBurst(t *testing.T) {
	// The handler must never block: wacli posts synchronously, and a stalled
	// webhook would stall the sync process itself.
	w, _ := NewWebhook("s", 2)
	defer w.Close()

	done := make(chan struct{})
	go func() {
		defer close(done)
		for i := 0; i < 50; i++ {
			post(t, w, "s", fmt.Sprintf(`{"type":"message","chat_jid":"a@s.whatsapp.net","msg_id":"M%d"}`, i))
		}
	}()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("the webhook handler blocked under burst")
	}
	if w.Dropped() == 0 {
		t.Error("a burst past the buffer must be counted as dropped")
	}
}

func TestWebhookUnknownPayloadStillInvalidates(t *testing.T) {
	// An unrecognised shape is still evidence that something changed. Losing
	// it silently would leave a stale chat on screen.
	w, _ := NewWebhook("s", 4)
	defer w.Close()
	if code := post(t, w, "s", `{"something":"else"}`); code != http.StatusOK {
		t.Fatalf("status = %d", code)
	}
	if _, ok := waitEvent(t, w); !ok {
		t.Fatal("an unrecognised payload produced no invalidation")
	}
}

func TestWebhookMalformedJSONStillInvalidates(t *testing.T) {
	w, _ := NewWebhook("s", 4)
	defer w.Close()
	if code := post(t, w, "s", `{not json`); code != http.StatusOK {
		t.Fatalf("status = %d", code)
	}
	if _, ok := waitEvent(t, w); !ok {
		t.Fatal("malformed JSON produced no invalidation")
	}
}

func TestWebhookDecodesReceiptAndPresence(t *testing.T) {
	w, _ := NewWebhook("s", 8)
	defer w.Close()

	for _, tc := range []struct {
		body string
		want domain.EventKind
	}{
		{`{"type":"receipt","chat_jid":"a@s.whatsapp.net","msg_id":"M1"}`, domain.EventReceipt},
		{`{"type":"chat_presence","chat_jid":"a@s.whatsapp.net"}`, domain.EventChatPresence},
	} {
		post(t, w, "s", tc.body)
		ev, ok := waitEvent(t, w)
		if !ok {
			t.Fatalf("no event for %s", tc.body)
		}
		if ev.Kind != tc.want {
			t.Errorf("kind = %q, want %q", ev.Kind, tc.want)
		}
	}
}

func TestWebhookMillisecondTimestamps(t *testing.T) {
	w, _ := NewWebhook("s", 4)
	defer w.Close()
	post(t, w, "s", `{"type":"message","chat_jid":"a@s.whatsapp.net","ts":1788872473652}`)
	ev, ok := waitEvent(t, w)
	if !ok {
		t.Fatal("no event")
	}
	if ev.At.Year() < 2020 || ev.At.Year() > 2100 {
		t.Errorf("At = %v; a millisecond timestamp was read as seconds", ev.At)
	}
}

func TestWebhookWithoutASecretAcceptsUnsigned(t *testing.T) {
	// Only reachable when wa attached to a sync it did not start, so there is
	// no shared secret to check against.
	w, _ := NewWebhook("", 4)
	defer w.Close()
	if code := post(t, w, "", `{"type":"message","chat_jid":"a@s.whatsapp.net"}`); code != http.StatusOK {
		t.Fatalf("status = %d", code)
	}
}

func TestCloseIsIdempotent(t *testing.T) {
	w, _ := NewWebhook("s", 4)
	if err := w.Close(); err != nil {
		t.Fatal(err)
	}
	if err := w.Close(); err != nil {
		t.Errorf("second Close = %v", err)
	}
}

// --- polling ---------------------------------------------------------------

type fakeStats struct {
	store.Reader
	mu sync.Mutex
	st store.Stats

	// read is closed on the first Stats call, so a test can change the store
	// only after the poller has taken its baseline. Without it the update can
	// land first and become the baseline, and nothing ever looks changed.
	readOnce sync.Once
	read     chan struct{}
}

func newFakeStats(st store.Stats) *fakeStats {
	return &fakeStats{st: st, read: make(chan struct{})}
}

func (f *fakeStats) Stats(context.Context) (store.Stats, error) {
	f.readOnce.Do(func() {
		if f.read != nil {
			close(f.read)
		}
	})
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.st, nil
}

func (f *fakeStats) waitBaseline(t *testing.T) {
	t.Helper()
	select {
	case <-f.read:
	case <-time.After(2 * time.Second):
		t.Fatal("the poller never took a baseline reading")
	}
}

func (f *fakeStats) set(st store.Stats) {
	f.mu.Lock()
	f.st = st
	f.mu.Unlock()
}

func TestPollEmitsWhenTheStoreGrows(t *testing.T) {
	r := newFakeStats(store.Stats{MaxRowID: 10})
	p := NewPoll(r, 10*time.Millisecond, 4)
	defer p.Close()

	r.waitBaseline(t)
	r.set(store.Stats{MaxRowID: 11, LastMessageTS: time.Now()})
	if _, ok := waitEvent(t, p); !ok {
		t.Fatal("polling did not notice the new row")
	}
}

func TestPollStaysQuietWhenNothingChanges(t *testing.T) {
	r := newFakeStats(store.Stats{MaxRowID: 10, LastMessageTS: time.Unix(1000, 0)})
	p := NewPoll(r, 10*time.Millisecond, 4)
	defer p.Close()

	select {
	case ev := <-p.Events():
		t.Fatalf("an idle store produced an event: %+v", ev)
	case <-time.After(200 * time.Millisecond):
	}
}

func TestPollCloseIsIdempotent(t *testing.T) {
	p := NewPoll(newFakeStats(store.Stats{}), 10*time.Millisecond, 4)
	if err := p.Close(); err != nil {
		t.Fatal(err)
	}
	if err := p.Close(); err != nil {
		t.Errorf("second Close = %v", err)
	}
}

func TestNoneSourceNeverEmits(t *testing.T) {
	s := None()
	select {
	case <-s.Events():
		t.Fatal("None emitted")
	case <-time.After(50 * time.Millisecond):
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestSourcesSatisfyTheInterface(t *testing.T) {
	var _ Source = (*Webhook)(nil)
	var _ Source = (*Poll)(nil)
	var _ Source = (*nilSource)(nil)
}
