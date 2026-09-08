package store

import (
	"database/sql"
	"fmt"
	"strings"
)

// KnownMigration is the highest wacli schema version this build was written
// against. A store at exactly this version, or below it, is read directly.
// Anything higher may have moved a column we read, so the CLI reader is used
// instead: slower, but it speaks a documented interface rather than a private
// table layout.
const KnownMigration = 26

// requiredColumns are the columns the SQL in sqlite.go names. They are checked
// explicitly, because a migration can add a version without touching anything
// we read, and refusing the fast path on the version alone would be needlessly
// pessimistic.
var requiredColumns = map[string][]string{
	"chats": {
		"jid", "kind", "name", "last_message_ts",
		"archived", "pinned", "muted_until", "unread", "unread_count",
	},
	"messages": {
		"rowid", "chat_jid", "chat_name", "msg_id", "sender_jid", "sender_name",
		"ts", "from_me", "text", "display_text", "quoted_msg_id",
		"quoted_sender_jid", "is_forwarded", "reaction_to_id", "reaction_emoji",
		"media_type", "media_caption", "filename", "mime_type", "file_length",
		"local_path", "downloaded_at", "revoked", "deleted_for_me", "edited",
		"edited_ts",
	},
	"contacts": {
		"jid", "phone", "push_name", "full_name", "business_name",
	},
}

// Probe reports the store's schema version and whether this build can read it
// directly. The returned reason is empty when ok is true.
func Probe(dbPath string) (version int, ok bool, reason string, err error) {
	db, err := openRO(dbPath)
	if err != nil {
		return 0, false, "", err
	}
	defer db.Close()

	if err := db.QueryRow(`select coalesce(max(version), 0) from schema_migrations`).
		Scan(&version); err != nil {
		return 0, false, fmt.Sprintf("no schema_migrations table: %v", err), nil
	}
	if version > KnownMigration {
		return version, false, fmt.Sprintf(
			"schema version %d is newer than the %d this build understands",
			version, KnownMigration), nil
	}

	for table, want := range requiredColumns {
		have, err := columns(db, table)
		if err != nil {
			return version, false, fmt.Sprintf("reading %s: %v", table, err), nil
		}
		var missing []string
		for _, c := range want {
			if !have[c] {
				missing = append(missing, c)
			}
		}
		if len(missing) > 0 {
			return version, false, fmt.Sprintf("%s is missing %s",
				table, strings.Join(missing, ", ")), nil
		}
	}
	return version, true, "", nil
}

func columns(db *sql.DB, table string) (map[string]bool, error) {
	// A table name cannot be a bound parameter in PRAGMA, and these names are
	// compile-time constants from requiredColumns, never user input.
	rows, err := db.Query(`select name from pragma_table_info(?)`, table)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := map[string]bool{"rowid": true} // implicit on every rowid table
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return nil, err
		}
		out[name] = true
	}
	return out, rows.Err()
}

// HasFTS reports whether the full-text index exists. Without it, Search falls
// back to LIKE, which is slower and matches differently.
func HasFTS(db *sql.DB) bool {
	var n int
	err := db.QueryRow(
		`select count(*) from sqlite_master where type='table' and name='messages_fts'`).
		Scan(&n)
	return err == nil && n > 0
}
