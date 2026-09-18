package wacli

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// SendTextRequest is one outgoing message.
type SendTextRequest struct {
	To            domain.JID
	Message       string
	ReplyTo       string
	ReplyToSender domain.JID
	Mentions      []string
	NoPreview     bool
	AllowSelf     bool
}

// SentMessage is what came back.
type SentMessage struct {
	ID   string
	To   string
	Sent bool
	TS   time.Time
}

// SendText sends a message.
//
// Sends are serialised: while a `sync --follow` process holds the store lock,
// wacli hands the message to it over a Unix socket, and two concurrent sends
// would race on that socket. Expect roughly 2.7 s per call - far too slow to
// block an interface on, which is why the composer draws an optimistic bubble
// and reconciles it with the id this returns.
func (c *Client) SendText(ctx context.Context, r SendTextRequest) (SentMessage, error) {
	if r.To.IsZero() {
		return SentMessage{}, fmt.Errorf("send: no recipient")
	}
	if r.Message == "" {
		return SentMessage{}, fmt.Errorf("send: empty message")
	}

	args := []string{"send", "text", "--to", r.To.String(), "--message", r.Message}
	if r.ReplyTo != "" {
		args = append(args, "--reply-to", r.ReplyTo)
		if !r.ReplyToSender.IsZero() {
			args = append(args, "--reply-to-sender", r.ReplyToSender.String())
		}
	}
	for _, m := range r.Mentions {
		args = append(args, "--mention", m)
	}
	if r.NoPreview {
		args = append(args, "--no-preview")
	}
	if r.AllowSelf {
		args = append(args, "--allow-self")
	}
	args = append(args, c.postSendWait()...)

	c.sendMu.Lock()
	defer c.sendMu.Unlock()

	body, err := c.run(ctx, args...)
	if err != nil {
		return SentMessage{}, err
	}
	return decodeSent(body)
}

// decodeSent reads what wacli says about a message it just sent.
func decodeSent(body []byte) (SentMessage, error) {
	var raw struct {
		ID   string `json:"id"`
		To   string `json:"to"`
		Sent bool   `json:"sent"`
	}
	if err := json.Unmarshal(body, &raw); err != nil {
		return SentMessage{}, fmt.Errorf("send: %w", err)
	}
	return SentMessage{ID: raw.ID, To: raw.To, Sent: raw.Sent, TS: time.Now()}, nil
}

// Every chats subcommand takes --chat, not a positional argument. Passing the
// JID positionally fails with "--chat is required", which is what made pin,
// mute, archive and mark-read all appear to do nothing.

// MarkRead marks a chat read.
func (c *Client) MarkRead(ctx context.Context, j domain.JID) error {
	_, err := c.run(ctx, "chats", "mark-read", "--chat", j.String())
	return err
}

// MarkUnread marks a chat unread.
func (c *Client) MarkUnread(ctx context.Context, j domain.JID) error {
	_, err := c.run(ctx, "chats", "mark-unread", "--chat", j.String())
	return err
}

// Archive archives or unarchives a chat.
func (c *Client) Archive(ctx context.Context, j domain.JID, on bool) error {
	return c.toggle(ctx, "archive", "unarchive", j, on)
}

// Pin pins or unpins a chat.
func (c *Client) Pin(ctx context.Context, j domain.JID, on bool) error {
	return c.toggle(ctx, "pin", "unpin", j, on)
}

// Mute mutes or unmutes a chat.
func (c *Client) Mute(ctx context.Context, j domain.JID, on bool) error {
	return c.toggle(ctx, "mute", "unmute", j, on)
}

func (c *Client) toggle(ctx context.Context, on, off string, j domain.JID, want bool) error {
	verb := off
	if want {
		verb = on
	}
	_, err := c.run(ctx, "chats", verb, "--chat", j.String())
	return err
}

// Typing sends or clears a typing indicator.
func (c *Client) Typing(ctx context.Context, j domain.JID, on bool) error {
	verb := "paused"
	if on {
		verb = "typing"
	}
	_, err := c.run(ctx, "presence", verb, "--to", j.String())
	return err
}

// MaxDownloadSize is the largest attachment wacli will fetch.
//
// It refuses anything bigger with "media too large; maximum download size is
// 104857600 bytes", after the download has been attempted. Knowing the number
// here means wa can say so before spending a minute finding out.
const MaxDownloadSize = 100 * 1024 * 1024

// SendFileRequest is one outgoing attachment.
type SendFileRequest struct {
	To            domain.JID
	Path          string
	Caption       string
	Filename      string
	ReplyTo       string
	ReplyToSender domain.JID
	// Voice sends an ogg/opus file as a voice note rather than as audio.
	Voice bool
}

// Note that there is no AllowSelf here. `send text` refuses the linked account
// unless told otherwise; `send file` has no such flag and no such objection,
// and passing one it does not know is an error rather than a no-op.

// SendFile sends an attachment.
//
// wacli works out the WhatsApp media type from the file, so a photograph
// arrives as a photograph rather than as a document. That is worth leaving to
// it: getting it wrong is the difference between a picture in the conversation
// and a download link.
func (c *Client) SendFile(ctx context.Context, r SendFileRequest) (SentMessage, error) {
	if r.To.IsZero() {
		return SentMessage{}, fmt.Errorf("send: no recipient")
	}
	if r.Path == "" {
		return SentMessage{}, fmt.Errorf("send: no file")
	}
	if _, err := os.Stat(r.Path); err != nil {
		return SentMessage{}, fmt.Errorf("send: %w", err)
	}

	args := []string{"send", "file", "--to", r.To.String(), "--file", r.Path}
	if r.Caption != "" {
		args = append(args, "--caption", r.Caption)
	}
	if r.Filename != "" {
		args = append(args, "--filename", r.Filename)
	}
	if r.ReplyTo != "" {
		args = append(args, "--reply-to", r.ReplyTo)
		if !r.ReplyToSender.IsZero() {
			args = append(args, "--reply-to-sender", r.ReplyToSender.String())
		}
	}
	if r.Voice {
		args = append(args, "--ptt")
	}
	args = append(args, c.postSendWait()...)

	c.sendMu.Lock()
	defer c.sendMu.Unlock()

	body, err := c.run(ctx, args...)
	if err != nil {
		return SentMessage{}, err
	}
	return decodeSent(body)
}

// Tag adds or removes a local tag on a contact.
//
// WhatsApp has no "favourite" flag that reaches a linked device, so favourites
// are kept as one of wacli's own tags. They live in the local store and
// survive a sync, which is as close as this can be got.
func (c *Client) Tag(ctx context.Context, j domain.JID, tag string, on bool) error {
	verb := "rm"
	if on {
		verb = "add"
	}
	_, err := c.run(ctx, "contacts", "tags", verb, "--jid", j.String(), "--tag", tag)
	return err
}

// Alias sets the local name for a contact, or clears it when name is empty.
func (c *Client) Alias(ctx context.Context, j domain.JID, name string) error {
	if strings.TrimSpace(name) == "" {
		_, err := c.run(ctx, "contacts", "alias", "rm", "--jid", j.String())
		return err
	}
	_, err := c.run(ctx, "contacts", "alias", "set", "--jid", j.String(), "--alias", name)
	return err
}

// Export writes a chat's messages to a file as JSON.
func (c *Client) Export(ctx context.Context, j domain.JID, path string, limit int) error {
	if limit <= 0 {
		limit = 100000
	}
	_, err := c.run(ctx, "messages", "export",
		"--chat", j.String(), "--output", path, "--limit", strconv.Itoa(limit))
	return err
}

// ClearChat removes a conversation from the local store. WhatsApp is not told:
// wacli has no command that clears a chat on the account.
func (c *Client) ClearChat(ctx context.Context, j domain.JID) error {
	_, err := c.run(ctx, "chats", "cleanup", "--jid", j.String(), "--confirm")
	return err
}

// Registered asks WhatsApp whether numbers have accounts, which is the only
// way to be sure before starting a conversation with someone who is not in the
// store yet. The numbers are positional: `wacli contacts check <phone>...`.
func (c *Client) Registered(ctx context.Context, numbers ...string) ([]byte, error) {
	args := append([]string{"contacts", "check"}, numbers...)
	return c.Raw(ctx, args...)
}
