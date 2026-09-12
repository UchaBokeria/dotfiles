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

// payload is the shape wacli posts. Only the fields needed to identify what
// changed are read; the body itself is never trusted as the message content.
type payload struct {
	Type      string `json:"type"`
	Event     string `json:"event"`
	ChatJID   string `json:"chat_jid"`
	Chat      string `json:"chat"`
	MsgID     string `json:"msg_id"`
	ID        string `json:"id"`
	Timestamp int64  `json:"ts"`
}

func decode(body []byte) (domain.Event, bool) {
	var p payload
	if err := json.Unmarshal(body, &p); err != nil {
		return domain.Event{}, false
	}

	kind := domain.EventKind(firstNonEmpty(p.Type, p.Event))
	switch kind {
	case domain.EventMessage, domain.EventReceipt, domain.EventChatPresence:
	default:
		kind = domain.EventMessage
	}

	ev := domain.Event{
		Kind:      kind,
		MessageID: firstNonEmpty(p.MsgID, p.ID),
		At:        now(),
	}
	if jid := firstNonEmpty(p.ChatJID, p.Chat); jid != "" {
		ev.Chat, _ = domain.ParseJID(jid)
	}
	if p.Timestamp > 0 {
		// wacli posts seconds; milliseconds appear in its NDJSON event stream.
		if p.Timestamp > 1e12 {
			ev.At = time.UnixMilli(p.Timestamp)
		} else {
			ev.At = time.Unix(p.Timestamp, 0)
		}
	}
	return ev, true
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}
