package store

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/wacli"
)

// cliReader reads through the wacli command line instead of the database.
//
// It exists so that a wacli upgrade which moves a column degrades into
// something slower rather than something wrong. It costs 11-15 ms per query
// against roughly nothing for the direct reader, so it is never the default.
type cliReader struct {
	c *wacli.Client
}

// OpenCLI returns a reader backed by the wacli command line.
func OpenCLI(c *wacli.Client) Reader { return &cliReader{c: c} }

// Open picks a reader. The direct one is used when the schema is recognised;
// otherwise the CLI reader is returned along with a Degradation explaining
// why, which the interface reports once rather than hiding.
func Open(dbPath string, c *wacli.Client) (Reader, Degradation, error) {
	_, ok, reason, err := Probe(dbPath)
	if err != nil {
		if c == nil {
			return nil, Degradation{}, err
		}
		return OpenCLI(c), Degradation{
			Used:   true,
			Reason: fmt.Sprintf("cannot read %s directly (%v); falling back to the wacli CLI", dbPath, err),
		}, nil
	}
	if ok {
		r, err := OpenSQLite(dbPath)
		if err == nil {
			return r, Degradation{}, nil
		}
		if c == nil {
			return nil, Degradation{}, err
		}
		return OpenCLI(c), Degradation{
			Used:   true,
			Reason: fmt.Sprintf("cannot open %s (%v); falling back to the wacli CLI", dbPath, err),
		}, nil
	}
	if c == nil {
		return nil, Degradation{}, fmt.Errorf("%s: %s, and no wacli client to fall back to", dbPath, reason)
	}
	return OpenCLI(c), Degradation{
		Used:   true,
		Reason: reason + "; reading through the wacli CLI instead",
	}, nil
}

func (r *cliReader) Close() error { return nil }

// jsonChat is wacli's chat shape. Timestamps arrive as RFC3339 strings here,
// unlike the integers in the database.
type jsonChat struct {
	JID           string `json:"jid"`
	Kind          string `json:"kind"`
	Name          string `json:"name"`
	LastMessageTS string `json:"last_message_ts"`
	Archived      bool   `json:"archived"`
	Pinned        bool   `json:"pinned"`
	MutedUntil    int64  `json:"muted_until"`
	Unread        bool   `json:"unread"`
	UnreadCount   int    `json:"unread_count"`
	LastMessage   string `json:"last_message"`
}

func (j jsonChat) toDomain() domain.Chat {
	// wacli puts the JID in the name field when it has nothing better, the
	// same as it does in the database. Passing that through would show a
	// column of raw identifiers, so drop it and let the caller format the
	// number instead.
	name := j.Name
	if name == j.JID {
		name = ""
	}
	c := domain.Chat{
		Name:        name,
		Kind:        domain.ChatKind(j.Kind),
		Archived:    j.Archived,
		Pinned:      j.Pinned,
		Unread:      j.Unread || j.UnreadCount > 0,
		UnreadCount: j.UnreadCount,
		LastSnippet: j.LastMessage,
	}
	c.JID, _ = domain.ParseJID(j.JID)
	if t, err := time.Parse(time.RFC3339, j.LastMessageTS); err == nil {
		c.LastMessageTS = t
	}
	if j.MutedUntil > 0 {
		c.MutedUntil = time.Unix(j.MutedUntil, 0)
	}
	return c
}

func (r *cliReader) Chats(ctx context.Context, f ChatFilter) ([]domain.Chat, error) {
	args := []string{"chats", "list", "--limit", strconv.Itoa(limitOr(f.Limit, 200))}
	if f.Query != "" {
		args = append(args, "--query", f.Query)
	}
	switch {
	case f.Archived:
		args = append(args, "--archived")
	case !f.IncludeArchived:
		args = append(args, "--no-archived")
	}
	if f.Unread {
		args = append(args, "--unread")
	}
	if f.Pinned {
		args = append(args, "--pinned")
	}
	if f.Muted {
		args = append(args, "--muted")
	}

	body, err := r.c.Raw(ctx, args...)
	if err != nil {
		return nil, err
	}
	var raw []jsonChat
	if err := json.Unmarshal(body, &raw); err != nil {
		return nil, fmt.Errorf("chats: %w", err)
	}

	out := make([]domain.Chat, 0, len(raw))
	for _, j := range raw {
		c := j.toDomain()
		// wacli has no group/dm filter of its own, so narrow here.
		if f.Groups && c.Kind != domain.KindGroup {
			continue
		}
		if f.DMs && c.Kind != domain.KindDM {
			continue
		}
		out = append(out, c)
	}
	return out, nil
}

func (r *cliReader) Chat(ctx context.Context, jid domain.JID) (domain.Chat, error) {
	body, err := r.c.Raw(ctx, "chats", "show", "--jid", jid.String())
	if err != nil {
		return domain.Chat{}, err
	}
	var j jsonChat
	if err := json.Unmarshal(body, &j); err != nil {
		return domain.Chat{}, fmt.Errorf("chat %s: %w", jid, err)
	}
	if j.JID == "" {
		return domain.Chat{}, fmt.Errorf("chat %s: %w", jid, ErrNotFound)
	}
	return j.toDomain(), nil
}

// jsonMessage is wacli's message shape.
//
// Note the capitalisation: `chats list` returns snake_case, but
// `messages list` and `messages search` return Go field names, nested under
// data.messages alongside an "fts" flag. Guessing consistency here produced a
// reader that silently decoded nothing.
type jsonMessage struct {
	ChatJID       string `json:"ChatJID"`
	ChatName      string `json:"ChatName"`
	MsgID         string `json:"MsgID"`
	SenderJID     string `json:"SenderJID"`
	SenderName    string `json:"SenderName"`
	Timestamp     string `json:"Timestamp"`
	FromMe        bool   `json:"FromMe"`
	Text          string `json:"Text"`
	DisplayText   string `json:"DisplayText"`
	IsForwarded   bool   `json:"IsForwarded"`
	ReactionToID  string `json:"ReactionToID"`
	ReactionEmoji string `json:"ReactionEmoji"`
	MediaType     string `json:"MediaType"`
	MediaCaption  string `json:"MediaCaption"`
	Filename      string `json:"Filename"`
	MimeType      string `json:"MimeType"`
	LocalPath     string `json:"LocalPath"`
	DownloadedAt  string `json:"DownloadedAt"`
	Revoked       bool   `json:"Revoked"`
	DeletedForMe  bool   `json:"DeletedForMe"`
	Edited        bool   `json:"Edited"`
	Starred       bool   `json:"Starred"`
}

// messageEnvelope is the object `messages list` and `messages search` wrap
// their results in.
type messageEnvelope struct {
	FTS      bool          `json:"fts"`
	Messages []jsonMessage `json:"messages"`
}

func (j jsonMessage) toDomain() domain.Message {
	m := domain.Message{
		ID:            j.MsgID,
		SenderName:    j.SenderName,
		FromMe:        j.FromMe,
		Text:          firstNonEmpty(j.Text, j.DisplayText),
		Forwarded:     j.IsForwarded,
		ReactionTo:    j.ReactionToID,
		ReactionEmoji: j.ReactionEmoji,
		Revoked:       j.Revoked,
		DeletedForMe:  j.DeletedForMe,
		Edited:        j.Edited,
	}
	m.ChatJID, _ = domain.ParseJID(j.ChatJID)
	if j.SenderJID != "" {
		m.SenderJID, _ = domain.ParseJID(j.SenderJID)
	}
	if t, err := time.Parse(time.RFC3339, j.Timestamp); err == nil {
		m.TS = t
	}
	if j.MediaType != "" || j.Filename != "" {
		m.Media = &domain.MediaRef{
			Type:      j.MediaType,
			Caption:   j.MediaCaption,
			Filename:  j.Filename,
			MimeType:  j.MimeType,
			LocalPath: j.LocalPath,
		}
		if t, err := time.Parse(time.RFC3339, j.DownloadedAt); err == nil && t.Year() > 1 {
			m.Media.DownloadedAt = t
		}
	}
	if m.FromMe {
		m.Delivery = domain.Sent
	} else {
		m.Delivery = domain.Read
	}
	return m
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}

func (r *cliReader) Messages(ctx context.Context, f MessageFilter) ([]domain.Message, error) {
	if f.Chat.IsZero() {
		return nil, fmt.Errorf("messages: no chat")
	}
	args := []string{
		"messages", "list",
		"--chat", f.Chat.String(),
		"--limit", strconv.Itoa(limitOr(f.Limit, 100)),
	}
	if f.Ascending {
		args = append(args, "--asc")
	}
	// wacli pages by time only. Without a rowid tiebreaker, a page boundary
	// that lands inside a group of same-second messages can repeat one; the
	// message pane deduplicates by id for exactly this reason.
	if !f.BeforeTS.IsZero() {
		args = append(args, "--before", f.BeforeTS.Format(time.RFC3339))
	}
	if !f.AfterTS.IsZero() {
		args = append(args, "--after", f.AfterTS.Format(time.RFC3339))
	}
	return r.messages(ctx, args...)
}

func (r *cliReader) Message(ctx context.Context, chat domain.JID, id string) (domain.Message, error) {
	body, err := r.c.Raw(ctx, "messages", "show", "--chat", chat.String(), "--id", id)
	if err != nil {
		return domain.Message{}, err
	}
	var j jsonMessage
	if err := json.Unmarshal(body, &j); err != nil {
		return domain.Message{}, fmt.Errorf("message %s: %w", id, err)
	}
	if j.MsgID == "" {
		return domain.Message{}, fmt.Errorf("message %s in %s: %w", id, chat, ErrNotFound)
	}
	return j.toDomain(), nil
}

func (r *cliReader) Search(ctx context.Context, q Query) ([]domain.Message, error) {
	if strings.TrimSpace(q.Text) == "" {
		return nil, nil
	}
	args := []string{"messages", "search", q.Text, "--limit", strconv.Itoa(limitOr(q.Limit, 200))}
	if !q.Chat.IsZero() {
		args = append(args, "--chat", q.Chat.String())
	}
	if q.HasMedia {
		args = append(args, "--has-media")
	}
	if q.Starred {
		args = append(args, "--starred")
	}
	if !q.Since.IsZero() {
		args = append(args, "--after", q.Since.Format(time.RFC3339))
	}
	return r.messages(ctx, args...)
}

func (r *cliReader) messages(ctx context.Context, args ...string) ([]domain.Message, error) {
	body, err := r.c.Raw(ctx, args...)
	if err != nil {
		return nil, err
	}
	var env messageEnvelope
	if err := json.Unmarshal(body, &env); err != nil {
		return nil, fmt.Errorf("messages: %w", err)
	}
	// Reactions are folded onto their targets, exactly as the direct reader
	// does, so the two paths cannot disagree about what a conversation holds.
	return foldReactions(decodeMessages(env.Messages)), nil
}

func decodeMessages(raw []jsonMessage) []domain.Message {
	out := make([]domain.Message, 0, len(raw))
	for _, j := range raw {
		out = append(out, j.toDomain())
	}
	return out
}

func (r *cliReader) Contact(ctx context.Context, jid domain.JID) (domain.Contact, error) {
	body, err := r.c.Raw(ctx, "contacts", "show", "--jid", jid.String())
	if err != nil {
		return domain.Contact{JID: jid}, err
	}
	var j struct {
		JID          string   `json:"jid"`
		PushName     string   `json:"push_name"`
		FullName     string   `json:"full_name"`
		BusinessName string   `json:"business_name"`
		Alias        string   `json:"alias"`
		Tags         []string `json:"tags"`
	}
	if err := json.Unmarshal(body, &j); err != nil {
		return domain.Contact{JID: jid}, fmt.Errorf("contact %s: %w", jid, err)
	}
	if j.JID == "" {
		return domain.Contact{JID: jid}, fmt.Errorf("contact %s: %w", jid, ErrNotFound)
	}
	return domain.Contact{
		JID:      jid,
		Name:     firstNonEmpty(j.FullName, j.BusinessName),
		PushName: j.PushName,
		Alias:    j.Alias,
		Tags:     j.Tags,
		Business: j.BusinessName != "",
	}, nil
}

func (r *cliReader) Stats(ctx context.Context) (Stats, error) {
	body, err := r.c.Raw(ctx, "store", "stats")
	if err != nil {
		return Stats{}, err
	}
	var j struct {
		Messages int `json:"messages"`
		Chats    int `json:"chats"`
		Contacts int `json:"contacts"`
		Groups   int `json:"groups"`
	}
	if err := json.Unmarshal(body, &j); err != nil {
		return Stats{}, fmt.Errorf("stats: %w", err)
	}
	// MaxRowID is not exposed by the CLI. The polling live source compares
	// message counts instead when running on this reader, which is coarser but
	// still detects an arrival.
	return Stats{
		Messages: j.Messages,
		Chats:    j.Chats,
		Contacts: j.Contacts,
		Groups:   j.Groups,
		MaxRowID: int64(j.Messages),
	}, nil
}
