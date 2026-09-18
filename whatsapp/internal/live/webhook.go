package live

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// int64Counter is a tiny wrapper so the drop counter reads clearly at both
// call sites.
type int64Counter struct{ n atomic.Int64 }

func (c *int64Counter) add(n int64) { c.n.Add(n) }
func (c *int64Counter) get() int64  { return c.n.Load() }

// maxBody caps a webhook payload. wacli posts one message; anything far larger
// is a mistake, and reading it unbounded would be a way to exhaust memory.
const maxBody = 1 << 20

// Webhook receives events posted by `wacli sync --follow --webhook`.
type Webhook struct {
	srv      *http.Server
	ln       net.Listener
	ch       chan domain.Event
	dropped  int64Counter
	secret   string
	closeOne sync.Once
}

// NewWebhook listens on a kernel-assigned loopback port. The port is read back
// from the listener, so there is no race between choosing one and wacli being
// told about it.
func NewWebhook(secret string, buffer int) (*Webhook, error) {
	if buffer <= 0 {
		buffer = 64
	}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, fmt.Errorf("listening for webhooks: %w", err)
	}

	w := &Webhook{
		ln:     ln,
		ch:     make(chan domain.Event, buffer),
		secret: secret,
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/e", w.handle)
	w.srv = &http.Server{
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	go w.srv.Serve(ln)
	return w, nil
}

// Port is the port wacli should be told to post to.
func (w *Webhook) Port() int { return w.ln.Addr().(*net.TCPAddr).Port }

func (w *Webhook) Events() <-chan domain.Event { return w.ch }
func (w *Webhook) Dropped() int64              { return w.dropped.get() }
func (w *Webhook) Describe() string            { return "live" }

// Close stops the server. The event channel is left open: a consumer selecting
// on it should not see a spurious zero event at shutdown.
func (w *Webhook) Close() error {
	var err error
	w.closeOne.Do(func() { err = w.srv.Close() })
	return err
}

func (w *Webhook) handle(rw http.ResponseWriter, req *http.Request) {
	if req.Method != http.MethodPost {
		rw.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	// The listener is bound to loopback, but check the peer as well: a bind
	// is a weaker promise than an explicit check, and this endpoint injects
	// into the interface.
	if !isLoopback(req.RemoteAddr) {
		rw.WriteHeader(http.StatusForbidden)
		return
	}

	body, err := io.ReadAll(io.LimitReader(req.Body, maxBody))
	if err != nil {
		rw.WriteHeader(http.StatusBadRequest)
		return
	}
	if !w.verify(req.Header.Get("X-Wacli-Signature"), body) {
		rw.WriteHeader(http.StatusUnauthorized)
		return
	}

	ev, ok := decode(body)
	if !ok {
		// A payload shape we do not recognise is still a sign that something
		// changed, so fall back to a bare invalidation rather than dropping it.
		ev = domain.Event{Kind: domain.EventMessage, At: now()}
	}
	emit(w.ch, ev, &w.dropped)
	rw.WriteHeader(http.StatusOK)
}

// verify checks the HMAC. An empty configured secret means signing is off,
// which only happens when wa did not start the sync process itself.
func (w *Webhook) verify(header string, body []byte) bool {
	if w.secret == "" {
		return true
	}
	mac := hmac.New(sha256.New, []byte(w.secret))
	mac.Write(body)
	want := mac.Sum(nil)

	got, err := hex.DecodeString(strings.TrimPrefix(header, "sha256="))
	if err != nil {
		return false
	}
	return hmac.Equal(got, want)
}

func isLoopback(remoteAddr string) bool {
	host, _, err := net.SplitHostPort(remoteAddr)
	if err != nil {
		host = remoteAddr
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

// payload is the shape wacli posts.
//
// wacli's webhook uses Go field names - Chat, ID, EventType, MessageIDs - and
// an RFC 3339 Timestamp; the snake_case fields are what its NDJSON event
// stream uses. Both spellings are read here because both reach this handler
// depending on how the sync process was started, and reading only one of them
// is how receipts arrived for months as unrecognised message events.
//
// The body is never trusted as the message content: what an event carries is
// the identity of what changed, and the rows are re-read from the store.
type payload struct {
	EventType string `json:"EventType"`
	Type      string `json:"type"`
	Event     string `json:"event"`

	Chat    string `json:"Chat"`
	ChatJID string `json:"chat_jid"`
	ChatAlt string `json:"chat"`

	ID         string   `json:"ID"`
	MsgID      string   `json:"msg_id"`
	IDAlt      string   `json:"id"`
	MessageIDs []string `json:"MessageIDs"`

	// ReceiptType is "delivered", "read" or "played" on a receipt. On a
	// message payload there is no Type at all.
	ReceiptType string `json:"Type"`

	Sender    string `json:"Sender"`
	SenderJID string `json:"SenderJID"`

	// State and Media belong to chat_presence: "composing" while typing.
	State string `json:"State"`
	Media string `json:"Media"`

	// Timestamp is RFC 3339 over the webhook and epoch over NDJSON, so it is
	// read as either.
	Timestamp json.RawMessage `json:"Timestamp"`
	TS        int64           `json:"ts"`
}

func decode(body []byte) (domain.Event, bool) {
	var p payload
	if err := json.Unmarshal(body, &p); err != nil {
		return domain.Event{}, false
	}

	// A message payload deliberately carries no discriminator, so anything
	// unrecognised is a message: that is wacli's own rule for its webhook.
	kind := domain.EventKind(firstNonEmpty(p.EventType, p.Type, p.Event))
	switch kind {
	case domain.EventMessage, domain.EventReceipt, domain.EventChatPresence:
	default:
		kind = domain.EventMessage
	}

	ev := domain.Event{
		Kind:       kind,
		MessageID:  firstNonEmpty(p.MsgID, p.ID, p.IDAlt),
		MessageIDs: p.MessageIDs,
		State:      p.State,
		At:         now(),
	}
	if jid := firstNonEmpty(p.ChatJID, p.Chat, p.ChatAlt); jid != "" {
		ev.Chat, _ = domain.ParseJID(jid)
	}
	if jid := firstNonEmpty(p.Sender, p.SenderJID); jid != "" {
		ev.Sender, _ = domain.ParseJID(jid)
	}
	if ev.MessageID == "" && len(ev.MessageIDs) > 0 {
		ev.MessageID = ev.MessageIDs[0]
	}
	if len(ev.MessageIDs) == 0 && ev.MessageID != "" {
		ev.MessageIDs = []string{ev.MessageID}
	}
	if kind == domain.EventReceipt {
		ev.Receipt = receiptState(p.ReceiptType)
	}
	if at, ok := decodeTime(p.Timestamp, p.TS); ok {
		ev.At = at
	}
	return ev, true
}

// receiptState maps wacli's receipt types onto how far a message got.
//
// Only delivered, read and played cross the webhook; played is a voice note
// that was listened to, which is a read receipt as far as a tick is concerned.
func receiptState(t string) domain.DeliveryState {
	switch strings.ToLower(t) {
	case "read", "played", "read-self", "played-self":
		return domain.Read
	case "", "delivered":
		return domain.Delivered
	}
	return domain.Delivered
}

// decodeTime reads either spelling of the timestamp.
func decodeTime(raw json.RawMessage, epoch int64) (time.Time, bool) {
	if len(raw) > 0 {
		var s string
		if err := json.Unmarshal(raw, &s); err == nil && s != "" {
			if t, err := time.Parse(time.RFC3339, s); err == nil {
				return t, true
			}
		}
		var n int64
		if err := json.Unmarshal(raw, &n); err == nil && n > 0 {
			epoch = n
		}
	}
	if epoch <= 0 {
		return time.Time{}, false
	}
	// wacli posts seconds; milliseconds appear in its NDJSON event stream.
	if epoch > 1e12 {
		return time.UnixMilli(epoch), true
	}
	return time.Unix(epoch, 0), true
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}
