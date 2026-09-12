package store

import (
	"context"
	"encoding/json"
	"os/exec"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/wacli"
)

// The fake wacli returns whatever a test tells it to, which is what makes the
// decoding tests above fast - and what let the CLI reader ship with the wrong
// JSON shape entirely. `chats list` returns snake_case; `messages list`
// returns Go field names nested under data.messages. Nothing but the real
// binary would have said so.
//
// These decode the real output. They skip when wacli is absent or the store
// is locked, so they cost nothing in a clean checkout.

func realClient(t *testing.T) *wacli.Client {
	t.Helper()
	if _, err := exec.LookPath("wacli"); err != nil {
		t.Skip("wacli is not installed")
	}
	return wacli.New(config.Wacli{Bin: "wacli", Timeout: config.Duration(20 * time.Second)})
}

func TestRealChatsListDecodes(t *testing.T) {
	c := realClient(t)
	body, err := c.Raw(context.Background(), "chats", "list", "--limit", "3")
	if err != nil {
		t.Skipf("cannot read chats: %v", err)
	}
	var raw []jsonChat
	if err := json.Unmarshal(body, &raw); err != nil {
		t.Fatalf("the chat shape has changed: %v\n%s", err, body)
	}
	if len(raw) == 0 {
		t.Skip("no chats to check")
	}
	if raw[0].JID == "" {
		t.Errorf("decoded a chat with no JID from %s", body)
	}
}

func TestRealMessagesListDecodes(t *testing.T) {
	c := realClient(t)

	body, err := c.Raw(context.Background(), "chats", "list", "--limit", "5", "--no-archived")
	if err != nil {
		t.Skipf("cannot read chats: %v", err)
	}
	var chats []jsonChat
	if err := json.Unmarshal(body, &chats); err != nil || len(chats) == 0 {
		t.Skip("no chats to check")
	}

	for _, ch := range chats {
		body, err := c.Raw(context.Background(), "messages", "list", "--chat", ch.JID, "--limit", "3")
		if err != nil {
			continue
		}
		var env messageEnvelope
		if err := json.Unmarshal(body, &env); err != nil {
			t.Fatalf("the message shape has changed: %v\n%s", err, body)
		}
		if len(env.Messages) == 0 {
			continue
		}
		m := env.Messages[0]
		if m.MsgID == "" {
			t.Errorf("decoded a message with no id from %s", body)
		}
		if m.ChatJID == "" {
			t.Errorf("decoded a message with no chat from %s", body)
		}
		if m.Timestamp == "" {
			t.Errorf("decoded a message with no timestamp from %s", body)
		}
		// One chat with messages is enough to prove the shape.
		return
	}
	t.Skip("no messages to check")
}

func TestRealReaderRoundTrip(t *testing.T) {
	// End to end through the CLI reader itself, which is what the fallback
	// path actually uses.
	c := realClient(t)
	r := OpenCLI(c)

	chats, err := r.Chats(context.Background(), ChatFilter{Limit: 5})
	if err != nil {
		t.Skipf("cannot read chats: %v", err)
	}
	if len(chats) == 0 {
		t.Skip("no chats")
	}
	for _, ch := range chats {
		msgs, err := r.Messages(context.Background(), MessageFilter{Chat: ch.JID, Limit: 3})
		if err != nil || len(msgs) == 0 {
			continue
		}
		if msgs[0].ID == "" || msgs[0].TS.IsZero() {
			t.Errorf("the CLI reader produced an empty message: %+v", msgs[0])
		}
		return
	}
	t.Skip("no messages")
}
