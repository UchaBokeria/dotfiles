-- Captured from a real wacli 0.18.1 store with `sqlite3 wacli.db .schema`.
-- Data-free: the only INSERTs below are inside the FTS triggers.
-- sqlite_sequence is stripped; SQLite creates it itself and rejects the DDL.
CREATE TABLE schema_migrations (
			version INTEGER PRIMARY KEY,
			name TEXT NOT NULL,
			applied_at INTEGER NOT NULL
		);
CREATE TABLE chats (
    jid TEXT PRIMARY KEY,
    kind TEXT NOT NULL, -- dm|group|broadcast|newsletter|unknown
    name TEXT,
    last_message_ts INTEGER,
    archived INTEGER NOT NULL DEFAULT 0,
    pinned INTEGER NOT NULL DEFAULT 0,
    muted_until INTEGER NOT NULL DEFAULT 0,
    unread INTEGER NOT NULL DEFAULT 0,
    unread_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE contacts (
    jid TEXT PRIMARY KEY,
    phone TEXT,
    push_name TEXT,
    full_name TEXT,
    first_name TEXT,
    business_name TEXT,
    system_name TEXT,
    updated_at INTEGER NOT NULL
);
CREATE TABLE groups (
    jid TEXT PRIMARY KEY,
    name TEXT,
    owner_jid TEXT,
    created_ts INTEGER,
    is_parent INTEGER NOT NULL DEFAULT 0,
    linked_parent_jid TEXT,
    left_at INTEGER,
    updated_at INTEGER NOT NULL
);
CREATE TABLE group_participants (
    group_jid TEXT NOT NULL,
    user_jid TEXT NOT NULL,
    role TEXT,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (group_jid, user_jid),
    FOREIGN KEY (group_jid) REFERENCES groups(jid) ON DELETE CASCADE
);
CREATE TABLE contact_aliases (
    jid TEXT PRIMARY KEY,
    alias TEXT NOT NULL,
    notes TEXT,
    updated_at INTEGER NOT NULL
);
CREATE TABLE contact_tags (
    jid TEXT NOT NULL,
    tag TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (jid, tag)
);
CREATE TABLE messages (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_jid TEXT NOT NULL,
    chat_name TEXT,
    msg_id TEXT NOT NULL,
    sender_jid TEXT,
    sender_name TEXT,
    ts INTEGER NOT NULL,
    from_me INTEGER NOT NULL,
    text TEXT,
    display_text TEXT,
    quoted_msg_id TEXT,
    quoted_sender_jid TEXT,
    is_forwarded INTEGER NOT NULL DEFAULT 0,
    forwarding_score INTEGER NOT NULL DEFAULT 0,
    reaction_to_id TEXT,
    reaction_emoji TEXT,
    media_type TEXT,
    media_caption TEXT,
    filename TEXT,
    mime_type TEXT,
    direct_path TEXT,
    media_key BLOB,
    file_sha256 BLOB,
    file_enc_sha256 BLOB,
    file_length INTEGER,
    local_path TEXT,
    downloaded_at INTEGER,
    media_unavailable_at INTEGER,
    revoked INTEGER NOT NULL DEFAULT 0,
    deleted_for_me INTEGER NOT NULL DEFAULT 0,
    deleted_at INTEGER,
    deletion_reason TEXT,
    payload_purged_at INTEGER,
    edited INTEGER NOT NULL DEFAULT 0,
    edited_ts INTEGER NOT NULL DEFAULT 0,
    buttons TEXT,
    UNIQUE(chat_jid, msg_id),
    FOREIGN KEY (chat_jid) REFERENCES chats(jid) ON DELETE CASCADE
);
CREATE INDEX idx_messages_chat_ts ON messages(chat_jid, ts);
CREATE INDEX idx_messages_ts ON messages(ts);
CREATE TABLE message_payload_purges (
    chat_jid TEXT NOT NULL,
    msg_id TEXT NOT NULL,
    purged_at INTEGER NOT NULL,
    deleted_at INTEGER NOT NULL,
    deletion_reason TEXT NOT NULL,
    PRIMARY KEY (chat_jid, msg_id)
);
CREATE TABLE message_local_media_aliases (
    chat_jid TEXT NOT NULL,
    msg_id TEXT NOT NULL,
    local_path TEXT NOT NULL,
    downloaded_at INTEGER,
    PRIMARY KEY (chat_jid, msg_id, local_path),
    FOREIGN KEY (chat_jid, msg_id) REFERENCES messages(chat_jid, msg_id) ON DELETE CASCADE
);
CREATE TABLE status_messages (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id TEXT NOT NULL UNIQUE,
    ts INTEGER NOT NULL,
    from_me INTEGER NOT NULL,
    sender_jid TEXT,
    sender_name TEXT,
    text TEXT,
    media_type TEXT,
    media_caption TEXT,
    filename TEXT,
    mime_type TEXT,
    direct_path TEXT,
    media_key BLOB,
    file_sha256 BLOB,
    file_enc_sha256 BLOB,
    file_length INTEGER,
    background_color TEXT,
    font INTEGER
);
CREATE INDEX idx_status_messages_ts ON status_messages(ts);
CREATE TABLE call_events (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_jid TEXT NOT NULL,
    chat_name TEXT,
    sender_jid TEXT,
    sender_name TEXT,
    call_id TEXT NOT NULL,
    msg_id TEXT,
    event_type TEXT NOT NULL,
    direction TEXT,
    media TEXT,
    outcome TEXT,
    reason TEXT,
    call_type TEXT,
    duration_secs INTEGER NOT NULL DEFAULT 0,
    ts INTEGER NOT NULL,
    participants TEXT,
    UNIQUE(chat_jid, call_id, event_type, ts),
    FOREIGN KEY (chat_jid) REFERENCES chats(jid) ON DELETE CASCADE
);
CREATE INDEX idx_call_events_chat_ts ON call_events(chat_jid, ts);
CREATE INDEX idx_call_events_ts ON call_events(ts);
CREATE TABLE starred (
    chat_jid TEXT NOT NULL,
    msg_id TEXT NOT NULL,
    sender_jid TEXT,
    from_me INTEGER NOT NULL DEFAULT 0,
    starred_at INTEGER NOT NULL,
    PRIMARY KEY (chat_jid, msg_id)
);
CREATE INDEX idx_starred_starred_at ON starred(starred_at);
CREATE TABLE polls (
    chat_jid TEXT NOT NULL,
    msg_id TEXT NOT NULL,
    sender_jid TEXT,
    question TEXT NOT NULL,
    options_json TEXT NOT NULL,
    selectable_count INTEGER NOT NULL DEFAULT 1,
    created_ts INTEGER NOT NULL,
    PRIMARY KEY (chat_jid, msg_id)
);
CREATE INDEX idx_polls_chat_ts ON polls(chat_jid, created_ts);
CREATE TABLE message_locations (
    chat_jid TEXT NOT NULL,
    msg_id TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    name TEXT,
    address TEXT,
    is_live INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_jid, msg_id)
);
CREATE TABLE poll_votes (
    chat_jid TEXT NOT NULL,
    poll_msg_id TEXT NOT NULL,
    voter_jid TEXT NOT NULL,
    vote_msg_id TEXT NOT NULL,
    selected_options_json TEXT NOT NULL,
    ts INTEGER NOT NULL,
    PRIMARY KEY (chat_jid, poll_msg_id, voter_jid)
);
CREATE INDEX idx_poll_votes_poll ON poll_votes(chat_jid, poll_msg_id);
CREATE VIRTUAL TABLE messages_fts USING fts5(
				text,
				media_caption,
				filename,
				chat_name,
				sender_name,
				display_text
			);
CREATE TABLE IF NOT EXISTS 'messages_fts_data'(id INTEGER PRIMARY KEY, block BLOB);
CREATE TABLE IF NOT EXISTS 'messages_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS 'messages_fts_content'(id INTEGER PRIMARY KEY, c0, c1, c2, c3, c4, c5);
CREATE TABLE IF NOT EXISTS 'messages_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
CREATE TABLE IF NOT EXISTS 'messages_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;
CREATE INDEX idx_groups_linked_parent_jid ON groups(linked_parent_jid);
CREATE TABLE app_state_recovery_intents (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			collection TEXT NOT NULL
		);
CREATE INDEX idx_app_state_recovery_intents_collection
		ON app_state_recovery_intents(collection);
CREATE INDEX idx_messages_sender_jid ON messages(sender_jid);
CREATE INDEX idx_messages_quoted_sender_jid ON messages(quoted_sender_jid);
CREATE TRIGGER messages_ai AFTER INSERT ON messages WHEN new.deleted_at IS NULL BEGIN
			INSERT INTO messages_fts(rowid, text, media_caption, filename, chat_name, sender_name, display_text)
			VALUES (new.rowid, COALESCE(new.text,''), COALESCE(new.media_caption,''), COALESCE(new.filename,''), COALESCE(new.chat_name,''), COALESCE(new.sender_name,''), COALESCE(new.display_text,''));
		END;
CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
			DELETE FROM messages_fts WHERE rowid = old.rowid;
		END;
CREATE TRIGGER messages_au AFTER UPDATE ON messages
		WHEN old.rowid IS NOT new.rowid
			OR old.deleted_at IS NOT new.deleted_at
			OR old.text IS NOT new.text
			OR old.media_caption IS NOT new.media_caption
			OR old.filename IS NOT new.filename
			OR old.chat_name IS NOT new.chat_name
			OR old.sender_name IS NOT new.sender_name
			OR old.display_text IS NOT new.display_text
		BEGIN
			DELETE FROM messages_fts WHERE rowid = old.rowid;
			INSERT INTO messages_fts(rowid, text, media_caption, filename, chat_name, sender_name, display_text)
			SELECT new.rowid, COALESCE(new.text,''), COALESCE(new.media_caption,''), COALESCE(new.filename,''), COALESCE(new.chat_name,''), COALESCE(new.sender_name,''), COALESCE(new.display_text,'')
			WHERE new.deleted_at IS NULL;
		END;
