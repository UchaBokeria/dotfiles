package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	_ "modernc.org/sqlite" // pure Go, so the binary needs no cgo

	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
)

// ErrNotFound is returned when a row that was asked for by identity is absent.
var ErrNotFound = errors.New("not found")

type sqliteReader struct {
	db  *sql.DB
	fts bool
}

// openRO opens the database read-only.
//
// mode=ro is what makes "never writes" a property of the connection rather
// than a convention: a stray UPDATE fails instead of corrupting wacli's store.
// busy_timeout covers the brief moments the sync process holds a write lock on
// a WAL checkpoint.
func openRO(path string) (*sql.DB, error) {
	dsn := fmt.Sprintf("file:%s?mode=ro&_pragma=busy_timeout(5000)", path)
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, fmt.Errorf("opening %s: %w", path, err)
	}
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("opening %s: %w", path, err)
	}
	return db, nil
}

// OpenSQLite opens the store for direct reads.
func OpenSQLite(path string) (Reader, error) {
	db, err := openRO(path)
	if err != nil {
		return nil, err
	}
	return &sqliteReader{db: db, fts: HasFTS(db)}, nil
}

func (s *sqliteReader) Close() error { return s.db.Close() }

// ---------------------------------------------------------------------------
// chats
// ---------------------------------------------------------------------------

// chatSnippet joins the newest message per chat for the list preview. The
// correlated subquery is bounded by the index on (chat_jid, ts).
// The name is coalesced across three sources because wacli fills them
// differently: chats.name is empty for most groups, whose name lives in the
// groups table, and a direct message with someone not in the address book has
// only the push name attached to their messages. Without this a group list
// reads as a column of raw JIDs.
const chatSelect = `
select c.jid, c.kind,
       coalesce(nullif(c.name, ''), nullif(g.name, ''),
                nullif((select ct.full_name from contacts ct where ct.jid = c.jid), ''),
                nullif((select ct.push_name from contacts ct where ct.jid = c.jid), ''),
                nullif((select a.alias from contact_aliases a where a.jid = c.jid), ''),
                '') as name,
       coalesce(c.last_message_ts, 0),
       c.archived, c.pinned, c.muted_until, c.unread, c.unread_count,
       coalesce((select coalesce(nullif(m.display_text, ''), nullif(m.text, ''),
                                nullif(m.media_caption, ''), nullif(m.filename, ''), '')
                 from messages m
                 where m.chat_jid = c.jid and m.deleted_for_me = 0
                 order by m.ts desc, m.rowid desc limit 1), '') as snippet
from chats c
left join groups g on g.jid = c.jid`

func (s *sqliteReader) Chats(ctx context.Context, f ChatFilter) ([]domain.Chat, error) {
	var where []string
	var args []any

	if !f.IncludeArchived && !f.Archived {
		where = append(where, "c.archived = 0")
	}
	if f.Archived {
		where = append(where, "c.archived = 1")
	}
	if f.Pinned {
		where = append(where, "c.pinned = 1")
	}
	if f.Unread {
		where = append(where, "(c.unread = 1 or c.unread_count > 0)")
	}
	if f.Muted {
		where = append(where, "c.muted_until > ?")
		args = append(args, time.Now().Unix())
	}
	if f.Groups {
		where = append(where, "c.kind = 'group'")
	}
	if f.DMs {
		where = append(where, "c.kind = 'dm'")
	}
	if f.Query != "" {
		where = append(where, "lower(coalesce(c.name, '')) like ? or lower(c.jid) like ?")
		like := "%" + strings.ToLower(f.Query) + "%"
		args = append(args, like, like)
	}

	q := chatSelect
	if len(where) > 0 {
		q += " where " + strings.Join(where, " and ")
	}
	// Pinned first, then most recent: the order the phone app uses.
	q += " order by c.pinned desc, c.last_message_ts desc, c.jid limit ?"
	args = append(args, limitOr(f.Limit, 200))

	rows, err := s.db.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, fmt.Errorf("chats: %w", err)
	}
	defer rows.Close()

	var out []domain.Chat
	for rows.Next() {
		c, err := scanChat(rows)
		if err != nil {
			return nil, fmt.Errorf("chats: %w", err)
		}
		out = append(out, c)
	}
	return out, rows.Err()
}

func (s *sqliteReader) Chat(ctx context.Context, jid domain.JID) (domain.Chat, error) {
	rows, err := s.db.QueryContext(ctx, chatSelect+" where c.jid = ?", jid.String())
	if err != nil {
		return domain.Chat{}, fmt.Errorf("chat %s: %w", jid, err)
	}
	defer rows.Close()
	if !rows.Next() {
		if err := rows.Err(); err != nil {
			return domain.Chat{}, err
		}
		return domain.Chat{}, fmt.Errorf("chat %s: %w", jid, ErrNotFound)
	}
	return scanChat(rows)
}

type scanner interface {
	Scan(dest ...any) error
}

func scanChat(r scanner) (domain.Chat, error) {
	var (
		c          domain.Chat
		jid, kind  string
		lastTS     int64
		archived   int
		pinned     int
		mutedUntil int64
		unread     int
	)
	if err := r.Scan(&jid, &kind, &c.Name, &lastTS, &archived, &pinned,
		&mutedUntil, &unread, &c.UnreadCount, &c.LastSnippet); err != nil {
		return domain.Chat{}, err
	}
	c.JID, _ = domain.ParseJID(jid)
	c.Kind = domain.ChatKind(kind)
	if lastTS > 0 {
		c.LastMessageTS = time.Unix(lastTS, 0)
	}
	if mutedUntil > 0 {
		c.MutedUntil = time.Unix(mutedUntil, 0)
	}
	c.Archived = archived != 0
	c.Pinned = pinned != 0
	c.Unread = unread != 0 || c.UnreadCount > 0
	return c, nil
}

// ---------------------------------------------------------------------------
// messages
// ---------------------------------------------------------------------------

const messageSelect = `
select m.rowid, m.chat_jid, coalesce(m.chat_name, ''), m.msg_id,
       coalesce(m.sender_jid, ''), coalesce(m.sender_name, ''), m.ts, m.from_me,
       coalesce(m.text, ''), coalesce(m.display_text, ''),
       coalesce(m.quoted_msg_id, ''), coalesce(m.quoted_sender_jid, ''),
       m.is_forwarded, coalesce(m.reaction_to_id, ''), coalesce(m.reaction_emoji, ''),
       coalesce(m.media_type, ''), coalesce(m.media_caption, ''),
       coalesce(m.filename, ''), coalesce(m.mime_type, ''),
       coalesce(m.file_length, 0), coalesce(m.local_path, ''),
       coalesce(m.downloaded_at, 0), m.revoked, m.deleted_for_me,
       m.edited, m.edited_ts
from messages m`

func (s *sqliteReader) Messages(ctx context.Context, f MessageFilter) ([]domain.Message, error) {
	if f.Chat.IsZero() {
		return nil, fmt.Errorf("messages: no chat")
	}
	where := []string{"m.chat_jid = ?", "m.deleted_for_me = 0"}
	args := []any{f.Chat.String()}

	// Keyset paging on the composite (ts, rowid): ts alone is not unique,
	// and two messages in the same second would repeat or vanish across pages.
	if !f.BeforeTS.IsZero() {
		where = append(where, "(m.ts < ? or (m.ts = ? and m.rowid < ?))")
		args = append(args, f.BeforeTS.Unix(), f.BeforeTS.Unix(), f.BeforeRowID)
	}
	if !f.AfterTS.IsZero() {
		where = append(where, "(m.ts > ? or (m.ts = ? and m.rowid > ?))")
		args = append(args, f.AfterTS.Unix(), f.AfterTS.Unix(), f.AfterRowID)
	}

	order := "order by m.ts desc, m.rowid desc"
	if f.Ascending {
		order = "order by m.ts asc, m.rowid asc"
	}
	q := messageSelect + " where " + strings.Join(where, " and ") + " " + order + " limit ?"
	args = append(args, limitOr(f.Limit, 100))

	return s.queryMessages(ctx, q, args...)
}

func (s *sqliteReader) Message(ctx context.Context, chat domain.JID, id string) (domain.Message, error) {
	got, err := s.queryMessages(ctx,
		messageSelect+" where m.chat_jid = ? and m.msg_id = ? limit 1",
		chat.String(), id)
	if err != nil {
		return domain.Message{}, err
	}
	if len(got) == 0 {
		return domain.Message{}, fmt.Errorf("message %s in %s: %w", id, chat, ErrNotFound)
	}
	return got[0], nil
}

func (s *sqliteReader) Search(ctx context.Context, q Query) ([]domain.Message, error) {
	if strings.TrimSpace(q.Text) == "" {
		return nil, nil
	}
	var (
		sql  string
		args []any
	)
	where := []string{"m.deleted_for_me = 0"}

	if s.fts {
		sql = messageSelect + ` join messages_fts f on f.rowid = m.rowid`
		where = append(where, "messages_fts match ?")
		args = append(args, ftsQuery(q.Text))
	} else {
		sql = messageSelect
		where = append(where, "(lower(coalesce(m.text,'')) like ? or lower(coalesce(m.media_caption,'')) like ?)")
		like := "%" + strings.ToLower(q.Text) + "%"
		args = append(args, like, like)
	}

	if !q.Chat.IsZero() {
		where = append(where, "m.chat_jid = ?")
		args = append(args, q.Chat.String())
	}
	if q.HasMedia {
		where = append(where, "coalesce(m.media_type, '') != ''")
	}
	if q.FromMe {
		where = append(where, "m.from_me = 1")
	}
	if q.Starred {
		where = append(where, "exists (select 1 from starred s where s.chat_jid = m.chat_jid and s.msg_id = m.msg_id)")
	}
	if !q.Since.IsZero() {
		where = append(where, "m.ts >= ?")
		args = append(args, q.Since.Unix())
	}

	sql += " where " + strings.Join(where, " and ") + " order by m.ts desc, m.rowid desc limit ?"
	args = append(args, limitOr(q.Limit, 200))

	return s.queryMessages(ctx, sql, args...)
}

// ftsQuery turns user input into an FTS5 expression. Bare words are quoted so
// that a stray quote, hyphen, or "NEAR" is searched for rather than parsed as
// syntax and rejected mid-keystroke.
func ftsQuery(text string) string {
	fields := strings.Fields(text)
	quoted := make([]string, 0, len(fields))
	for _, f := range fields {
		quoted = append(quoted, `"`+strings.ReplaceAll(f, `"`, `""`)+`"`)
	}
	return strings.Join(quoted, " ")
}

func (s *sqliteReader) queryMessages(ctx context.Context, q string, args ...any) ([]domain.Message, error) {
	rows, err := s.db.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, fmt.Errorf("messages: %w", err)
	}
	defer rows.Close()

	var out []domain.Message
	for rows.Next() {
		m, err := scanMessage(rows)
		if err != nil {
			return nil, fmt.Errorf("messages: %w", err)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func scanMessage(r scanner) (domain.Message, error) {
	var (
		m            domain.Message
		chatJID      string
		chatName     string
		senderJID    string
		quotedSender string
		ts           int64
		fromMe       int
		displayText  string
		forwarded    int
		mediaType    string
		caption      string
		filename     string
		mime         string
		length       int64
		localPath    string
		downloadedAt int64
		revoked      int
		deletedForMe int
		edited       int
		editedTS     int64
	)
	if err := r.Scan(&m.RowID, &chatJID, &chatName, &m.ID, &senderJID, &m.SenderName,
		&ts, &fromMe, &m.Text, &displayText, &m.QuotedID, &quotedSender,
		&forwarded, &m.ReactionTo, &m.ReactionEmoji,
		&mediaType, &caption, &filename, &mime, &length, &localPath, &downloadedAt,
		&revoked, &deletedForMe, &edited, &editedTS); err != nil {
		return domain.Message{}, err
	}

	m.ChatJID, _ = domain.ParseJID(chatJID)
	_ = chatName // the chat's name is carried by domain.Chat, not per message
	if senderJID != "" {
		m.SenderJID, _ = domain.ParseJID(senderJID)
	}
	if quotedSender != "" {
		m.QuotedSender, _ = domain.ParseJID(quotedSender)
	}
	m.TS = time.Unix(ts, 0)
	m.FromMe = fromMe != 0
	m.Forwarded = forwarded != 0
	m.Revoked = revoked != 0
	m.DeletedForMe = deletedForMe != 0
	m.Edited = edited != 0
	if editedTS > 0 {
		m.EditedTS = time.Unix(editedTS, 0)
	}

	// display_text is wacli's rendering of a non-text message - a poll, a
	// system notice - and is the better body when there is no text at all.
	if m.Text == "" && displayText != "" {
		m.Text = displayText
	}

	if mediaType != "" || filename != "" {
		m.Media = &domain.MediaRef{
			Type:      mediaType,
			Caption:   caption,
			Filename:  filename,
			MimeType:  mime,
			LocalPath: localPath,
			Length:    length,
		}
		if downloadedAt > 0 {
			m.Media.DownloadedAt = time.Unix(downloadedAt, 0)
		}
	}

	if m.FromMe {
		// The store records nothing finer than "we sent it"; receipts arrive
		// as live events and are applied on top by the interface.
		m.Delivery = domain.Sent
	} else {
		m.Delivery = domain.Read
	}
	return m, nil
}

// ---------------------------------------------------------------------------
// contacts and statistics
// ---------------------------------------------------------------------------

func (s *sqliteReader) Contact(ctx context.Context, jid domain.JID) (domain.Contact, error) {
	var c domain.Contact
	var phone, push, full, business, alias string
	err := s.db.QueryRowContext(ctx, `
select coalesce(c.phone, ''), coalesce(c.push_name, ''), coalesce(c.full_name, ''),
       coalesce(c.business_name, ''), coalesce(a.alias, '')
from contacts c
left join contact_aliases a on a.jid = c.jid
where c.jid = ?`, jid.String()).Scan(&phone, &push, &full, &business, &alias)
	if errors.Is(err, sql.ErrNoRows) {
		return domain.Contact{JID: jid}, fmt.Errorf("contact %s: %w", jid, ErrNotFound)
	}
	if err != nil {
		return c, fmt.Errorf("contact %s: %w", jid, err)
	}

	c.JID = jid
	c.PushName = push
	c.Name = full
	c.Alias = alias
	c.Business = business != ""
	if c.Name == "" && business != "" {
		c.Name = business
	}

	rows, err := s.db.QueryContext(ctx, `select tag from contact_tags where jid = ? order by tag`, jid.String())
	if err != nil {
		return c, nil // tags are decoration; their absence is not a failure
	}
	defer rows.Close()
	for rows.Next() {
		var tag string
		if err := rows.Scan(&tag); err == nil {
			c.Tags = append(c.Tags, tag)
		}
	}
	return c, nil
}

func (s *sqliteReader) Stats(ctx context.Context) (Stats, error) {
	var st Stats
	var maxRow, lastTS sql.NullInt64
	err := s.db.QueryRowContext(ctx, `
select (select count(*) from messages),
       (select count(*) from chats),
       (select count(*) from contacts),
       (select count(*) from groups),
       (select max(rowid) from messages),
       (select max(ts) from messages)`).
		Scan(&st.Messages, &st.Chats, &st.Contacts, &st.Groups, &maxRow, &lastTS)
	if err != nil {
		return st, fmt.Errorf("stats: %w", err)
	}
	st.MaxRowID = maxRow.Int64
	if lastTS.Valid && lastTS.Int64 > 0 {
		st.LastMessageTS = time.Unix(lastTS.Int64, 0)
	}
	return st, nil
}
