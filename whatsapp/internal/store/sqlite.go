package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	_ "modernc.org/sqlite" // pure Go, so the binary needs no cgo

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// ErrNotFound is returned when a row that was asked for by identity is absent.
var ErrNotFound = errors.New("not found")

type sqliteReader struct {
	db  *sql.DB
	fts bool
	// lids resolves WhatsApp's newer LID addresses back to phone numbers, so
	// one person is one chat however the server addressed them.
	lids *lidMap
	// quotes is wa's record of what its own sends replied to, which wacli
	// does not keep.
	quotes *QuoteLog
	// mentions puts names to the digits a mention is stored as.
	mentions *mentions
	// receipts is wa's record of how far its own sends got, which wacli's
	// store does not keep either.
	receipts *ReceiptLog
}

// SetQuoteLog attaches wa's record of its own replies. Nil disables it.
func SetQuoteLog(r Reader, q *QuoteLog) {
	if s, ok := r.(*sqliteReader); ok {
		s.quotes = q
	}
}

// SetReceiptLog attaches wa's record of delivery receipts. Nil disables it.
func SetReceiptLog(r Reader, l *ReceiptLog) {
	if s, ok := r.(*sqliteReader); ok {
		s.receipts = l
	}
}

// openRO opens the database read-only.
//
// mode=ro is what makes "never writes" a property of the connection rather
// than a convention: a stray UPDATE fails instead of corrupting wacli's store.
// busy_timeout covers the brief moments the sync process holds a write lock on
// a WAL checkpoint.
func openRO(path string) (*sql.DB, error) {
	// A file that is not there is the ordinary case on a machine where nobody
	// has linked an account yet, and it deserves to be said in those words.
	// SQLite reports a missing database in read-only mode as "unable to open
	// database file: out of memory (14)", which sends people looking for a
	// memory problem they do not have.
	if _, err := os.Stat(path); err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("there is no store at %s yet; run `wacli auth` to link an account", path)
		}
		return nil, fmt.Errorf("opening %s: %w", path, err)
	}

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
	lids := loadLIDMap(sessionPath(path))
	return &sqliteReader{
		db: db, fts: HasFTS(db), lids: lids,
		mentions: newMentions(db, lids),
	}, nil
}

func (s *sqliteReader) Close() error { return s.db.Close() }

// ---------------------------------------------------------------------------
// chats
// ---------------------------------------------------------------------------

// chatSnippet joins the newest message per chat for the list preview. The
// correlated subquery is bounded by the index on (chat_jid, ts).
// Resolving a chat's name is fiddly, and getting it wrong is the difference
// between a readable list and a column of raw identifiers.
//
// wacli stores the JID itself in chats.name whenever it has nothing better -
// for every group, and for any contact who is not in the address book. So
// chats.name cannot simply be preferred: it has to be discarded when it is
// just the JID again, which `nullif(name, jid)` does exactly.
//
// The remaining order matches what the phone app shows: a name you set
// yourself wins, then the group's subject, then the address book, then
// whatever the person calls themselves.
const chatSelect = `
select c.jid, c.kind,
       coalesce(
         nullif((select a.alias from contact_aliases a where a.jid = c.jid), ''),
         nullif(nullif(c.name, ''), c.jid),
         nullif(g.name, ''),
         nullif(ct.full_name, ''),
         nullif(ct.system_name, ''),
         nullif(ct.business_name, ''),
         nullif(ct.first_name, ''),
         nullif(ct.push_name, ''),
         '') as name,
       coalesce(c.last_message_ts, 0),
       c.archived, c.pinned, c.muted_until, c.unread, c.unread_count,
       coalesce((select coalesce(nullif(m.display_text, ''), nullif(m.text, ''),
                                nullif(m.media_caption, ''), nullif(m.filename, ''), '')
                 from messages m
                 where m.chat_jid = c.jid and m.deleted_for_me = 0
                 order by m.ts desc, m.rowid desc limit 1), '') as snippet,
       coalesce((select count(*) from group_participants gp
                 where gp.group_jid = c.jid), 0) as members
from chats c
left join groups g on g.jid = c.jid
left join contacts ct on ct.jid = c.jid`

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
		where = append(where, "(lower(coalesce(c.name, '')) like ? or lower(c.jid) like ?)")
		like := "%" + strings.ToLower(f.Query) + "%"
		args = append(args, like, like)
	}
	if f.Tag != "" {
		where = append(where, "exists (select 1 from contact_tags t where t.jid = c.jid and t.tag = ?)")
		args = append(args, f.Tag)
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
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return s.lids.foldChats(out), nil
}

func (s *sqliteReader) Chat(ctx context.Context, jid domain.JID) (domain.Chat, error) {
	// A conversation can be stored under either address, and which one exists
	// is not knowable from the JID being asked for.
	jids := s.lids.Aliases(jid)
	rows, err := s.db.QueryContext(ctx,
		chatSelect+" where "+inClause("c.jid", len(jids)), jidArgs(jids)...)
	if err != nil {
		return domain.Chat{}, fmt.Errorf("chat %s: %w", jid, err)
	}
	defer rows.Close()

	var found []domain.Chat
	for rows.Next() {
		c, err := scanChat(rows)
		if err != nil {
			return domain.Chat{}, err
		}
		found = append(found, c)
	}
	if err := rows.Err(); err != nil {
		return domain.Chat{}, err
	}
	if len(found) == 0 {
		return domain.Chat{}, fmt.Errorf("chat %s: %w", jid, ErrNotFound)
	}
	return s.lids.foldChats(found)[0], nil
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
		&mutedUntil, &unread, &c.UnreadCount, &c.LastSnippet, &c.Members); err != nil {
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
       -- The quoted message's own text, so the quote bar reads as a quote
       -- rather than as an ellipsis. wacli stores the reference, not the
       -- words; one indexed lookup per row is what the phone app shows.
       coalesce((select coalesce(nullif(q.display_text, ''), nullif(q.text, ''),
                                nullif(q.media_caption, ''), nullif(q.filename, ''), '')
                 from messages q
                 where q.chat_jid = m.chat_jid and q.msg_id = m.quoted_msg_id
                 limit 1), '') as quoted_text,
       m.is_forwarded, coalesce(m.reaction_to_id, ''), coalesce(m.reaction_emoji, ''),
       coalesce(m.media_type, ''), coalesce(m.media_caption, ''),
       coalesce(m.media_unavailable_at, 0),
       coalesce(m.filename, ''), coalesce(m.mime_type, ''),
       coalesce(m.file_length, 0), coalesce(m.local_path, ''),
       coalesce(m.downloaded_at, 0), m.revoked, m.deleted_for_me,
       m.edited, m.edited_ts
from messages m`

func (s *sqliteReader) Messages(ctx context.Context, f MessageFilter) ([]domain.Message, error) {
	if f.Chat.IsZero() {
		return nil, fmt.Errorf("messages: no chat")
	}
	// A conversation may be filed under both a phone number and a LID, so ask
	// for every address the same person answers to.
	jids := s.lids.Aliases(f.Chat)
	where := []string{inClause("m.chat_jid", len(jids)), "m.deleted_for_me = 0"}
	args := jidArgs(jids)

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
	// Reactions are rows too, and they are about to be folded away. Asking for
	// extra keeps a page from shrinking to nothing in a heavily reacted chat.
	limit := limitOr(f.Limit, 100)
	q := messageSelect + " where " + strings.Join(where, " and ") + " " + order + " limit ?"
	args = append(args, limit*2)

	got, err := s.queryMessages(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	got = dropRetryPlaceholders(foldReactions(got))
	if len(got) > limit {
		if f.Ascending {
			got = got[:limit]
		} else {
			got = got[:limit]
		}
	}
	return got, nil
}

func (s *sqliteReader) Message(ctx context.Context, chat domain.JID, id string) (domain.Message, error) {
	jids := s.lids.Aliases(chat)
	args := append(jidArgs(jids), id)
	got, err := s.queryMessages(ctx,
		messageSelect+" where "+inClause("m.chat_jid", len(jids))+" and m.msg_id = ? limit 1",
		args...)
	if err != nil {
		return domain.Message{}, err
	}
	if len(got) == 0 {
		return domain.Message{}, fmt.Errorf("message %s in %s: %w", id, chat, ErrNotFound)
	}
	return got[0], nil
}

func (s *sqliteReader) Search(ctx context.Context, q Query) ([]domain.Message, error) {
	text := strings.TrimSpace(q.Text)
	if text == "" && !q.Browse {
		return nil, nil
	}
	var (
		sql  string
		args []any
	)
	where := []string{"m.deleted_for_me = 0"}

	switch {
	case text == "":
		// Browsing: every filter still applies, there is just no text to
		// match. This is what the finder shows before anything is typed.
		sql = messageSelect
	case s.fts:
		sql = messageSelect + ` join messages_fts f on f.rowid = m.rowid`
		where = append(where, "messages_fts match ?")
		args = append(args, ftsQuery(text))
	default:
		sql = messageSelect
		where = append(where, "(lower(coalesce(m.text,'')) like ? or lower(coalesce(m.media_caption,'')) like ?)")
		like := "%" + strings.ToLower(text) + "%"
		args = append(args, like, like)
	}

	if !q.Chat.IsZero() {
		jids := s.lids.Aliases(q.Chat)
		where = append(where, inClause("m.chat_jid", len(jids)))
		args = append(args, jidArgs(jids)...)
	}
	if q.HasMedia {
		where = append(where, "coalesce(m.media_type, '') != ''")
	}
	if len(q.Kinds) > 0 {
		where = append(where, inClause("coalesce(m.media_type, '')", len(q.Kinds)))
		for _, k := range q.Kinds {
			args = append(args, k)
		}
	}
	if q.HasLink {
		// The cheap test that finds every URL anyone actually sends. A message
		// saying "http" and nothing else is a false positive nobody will meet.
		where = append(where, "(coalesce(m.text,'') like '%http%' or coalesce(m.media_caption,'') like '%http%')")
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
		// A message filed under a LID belongs to the same conversation as one
		// filed under the number. Everything above this line - the pane's
		// selection, a download, a forward - compares JIDs, so they have to
		// agree before any of that happens.
		m.StoredChatJID = m.ChatJID
		m.ChatJID = s.lids.Canonical(m.ChatJID)
		m.SenderJID = s.lids.Canonical(m.SenderJID)
		m = s.quotes.Apply(m)
		m = s.receipts.Apply(m)
		// display_text has already been folded into Text when it is the only
		// text a message has, so these two cover everything drawn.
		m.Text = s.mentions.Resolve(ctx, m.Text)
		m.QuotedText = s.mentions.Resolve(ctx, m.QuotedText)
		out = append(out, m)
	}
	return out, rows.Err()
}

// undecodedPlaceholder is what wacli stores as the display text of a message
// type it does not understand.
const undecodedPlaceholder = "(message)"

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
		unavailable  int64
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
		&ts, &fromMe, &m.Text, &displayText, &m.QuotedID, &quotedSender, &m.QuotedText,
		&forwarded, &m.ReactionTo, &m.ReactionEmoji,
		&mediaType, &caption, &unavailable, &filename, &mime, &length, &localPath, &downloadedAt,
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
	// Except when it is wacli's catch-all "(message)", which means only that
	// the type was not understood: that becomes a flag, and the bubble says so
	// in words of its own instead of quoting a placeholder as if it were text.
	if m.Text == "" && displayText != "" {
		if displayText == undecodedPlaceholder && mediaType == "" && filename == "" {
			m.Unsupported = true
		} else {
			m.Text = displayText
		}
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
		if unavailable > 0 {
			m.Media.UnavailableAt = time.Unix(unavailable, 0)
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

// ChatStats adds one conversation up.
//
// It is one pass over the chat's rows rather than a query per number: the
// counts are wanted together, and a chat of forty thousand messages should not
// be walked a dozen times to say so.
func (s *sqliteReader) ChatStats(ctx context.Context, jid domain.JID) (ChatStats, error) {
	st := ChatStats{Chat: jid, Kinds: map[string]int{}}
	jids := s.lids.Aliases(jid)

	rows, err := s.db.QueryContext(ctx, `
select coalesce(m.media_type,''), coalesce(m.filename,''), coalesce(m.mime_type,''),
       coalesce(m.file_length,0), m.from_me, m.ts,
       coalesce(m.text,''), coalesce(m.media_caption,''),
       coalesce(m.reaction_to_id,''), m.edited, m.revoked,
       exists(select 1 from starred s where s.chat_jid = m.chat_jid and s.msg_id = m.msg_id)
  from messages m
 where `+inClause("m.chat_jid", len(jids))+` and m.deleted_for_me = 0`,
		jidArgs(jids)...)
	if err != nil {
		return st, fmt.Errorf("chat stats: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var (
			kind, filename, mime, text, caption, reactionTo string
			length                                          int64
			fromMe, edited, revoked, starred                bool
			ts                                              int64
		)
		if err := rows.Scan(&kind, &filename, &mime, &length, &fromMe, &ts,
			&text, &caption, &reactionTo, &edited, &revoked, &starred); err != nil {
			return st, fmt.Errorf("chat stats: %w", err)
		}

		// A reaction is stored as a message of its own. Counting it as one
		// would say a chat of ten sentences and forty thumbs-up holds fifty
		// messages, which is not what anybody means.
		if reactionTo != "" {
			st.Reactions++
			continue
		}

		st.Messages++
		if fromMe {
			st.Sent++
		} else {
			st.Received++
		}
		if edited {
			st.Edited++
		}
		if revoked {
			st.Deleted++
		}
		if starred {
			st.Starred++
		}
		if strings.Contains(text, "http") || strings.Contains(caption, "http") {
			st.Links++
		}
		if kind != "" {
			st.Kinds[kind]++
			st.Bytes += length
			if kind == "document" {
				if isArchive(filename, mime) {
					st.Archives++
				} else {
					st.Documents++
				}
			}
		}

		at := time.Unix(ts, 0)
		if st.First.IsZero() || at.Before(st.First) {
			st.First = at
		}
		if at.After(st.Last) {
			st.Last = at
		}
	}
	return st, rows.Err()
}

// archiveExts are the documents that are really a pile of other documents.
var archiveExts = []string{".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".zst"}

// isArchive splits the document pile: "37 documents" says nothing about
// whether they are contracts or backups.
func isArchive(filename, mime string) bool {
	name := strings.ToLower(filename)
	for _, ext := range archiveExts {
		if strings.HasSuffix(name, ext) {
			return true
		}
	}
	switch {
	case strings.Contains(mime, "zip"), strings.Contains(mime, "x-tar"),
		strings.Contains(mime, "x-7z"), strings.Contains(mime, "rar"),
		strings.Contains(mime, "gzip"), strings.Contains(mime, "compressed"):
		return true
	}
	return false
}

// Contacts lists the address book, for the contacts tab.
//
// A contact is not a chat: most of the address book has never been written to,
// and the point of the tab is to start the conversation that does not exist
// yet.
func (s *sqliteReader) Contacts(ctx context.Context, f ContactFilter) ([]domain.Contact, error) {
	var where []string
	var args []any

	if f.Query != "" {
		like := "%" + strings.ToLower(f.Query) + "%"
		where = append(where, `(lower(coalesce(c.full_name,'')) like ?
			or lower(coalesce(c.push_name,'')) like ?
			or lower(coalesce(c.business_name,'')) like ?
			or lower(coalesce(a.alias,'')) like ?
			or lower(c.jid) like ?)`)
		args = append(args, like, like, like, like, like)
	}
	if f.Tag != "" {
		where = append(where, "exists (select 1 from contact_tags t where t.jid = c.jid and t.tag = ?)")
		args = append(args, f.Tag)
	}

	q := `
select c.jid, coalesce(c.push_name,''), coalesce(c.full_name,''),
       coalesce(c.business_name,''), coalesce(a.alias,'')
  from contacts c
  left join contact_aliases a on a.jid = c.jid`
	if len(where) > 0 {
		q += " where " + strings.Join(where, " and ")
	}
	// Named contacts first: a list that opens on four hundred bare numbers is
	// a list nobody scrolls.
	q += ` order by (coalesce(nullif(a.alias,''), nullif(c.full_name,''),
                             nullif(c.business_name,''), nullif(c.push_name,'')) is null),
                    lower(coalesce(nullif(a.alias,''), nullif(c.full_name,''),
                             nullif(c.business_name,''), nullif(c.push_name,''), c.jid))
             limit ?`
	args = append(args, limitOr(f.Limit, 500))

	rows, err := s.db.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, fmt.Errorf("contacts: %w", err)
	}
	defer rows.Close()

	var out []domain.Contact
	for rows.Next() {
		var jid, push, full, business, alias string
		if err := rows.Scan(&jid, &push, &full, &business, &alias); err != nil {
			return nil, fmt.Errorf("contacts: %w", err)
		}
		j, err := domain.ParseJID(jid)
		if err != nil {
			continue
		}
		c := domain.Contact{JID: j, PushName: push, Name: full, Alias: alias,
			Business: business != ""}
		if c.Name == "" && business != "" {
			c.Name = business
		}
		out = append(out, c)
	}
	return out, rows.Err()
}
