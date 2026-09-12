// Package config loads wa's TOML configuration, merges it over the embedded
// defaults, validates keymaps, and supports runtime changes through :set.
package config

import (
	"fmt"
	"time"
)

// Duration is a time.Duration written in TOML as a string, "10m".
type Duration time.Duration

// UnmarshalText implements encoding.TextUnmarshaler for the TOML decoder.
func (d *Duration) UnmarshalText(b []byte) error {
	v, err := time.ParseDuration(string(b))
	if err != nil {
		return fmt.Errorf("%q is not a duration (try \"10m\", \"2s\"): %w", string(b), err)
	}
	*d = Duration(v)
	return nil
}

// MarshalText implements encoding.TextMarshaler so :set! round trips.
func (d Duration) MarshalText() ([]byte, error) { return []byte(d.String()), nil }

func (d Duration) String() string { return time.Duration(d).String() }

// D is the duration as the standard library type.
func (d Duration) D() time.Duration { return time.Duration(d) }

// UI holds presentation and editing settings.
type UI struct {
	ListWidth        int    `toml:"list_width"`
	MinWidth         int    `toml:"min_width"`
	Timestamp        string `toml:"timestamp"`
	DaySeparator     string `toml:"day_separator"`
	Gutter           string `toml:"gutter"`
	Scrolloff        int    `toml:"scrolloff"`
	Border           string `toml:"border"`
	BubbleMaxPercent int    `toml:"bubble_max_percent"`
	Render           string `toml:"render"`
	Leader           string `toml:"leader"`
	TimeoutLen       int    `toml:"timeoutlen"`
	IgnoreCase       bool   `toml:"ignorecase"`
	SmartCase        bool   `toml:"smartcase"`
	Clipboard        string `toml:"clipboard"`
	SendTyping       bool   `toml:"send_typing"`
	Opener           string `toml:"opener"`
	Links            bool   `toml:"links"`
}

// Lock configures the password gate.
type Lock struct {
	Enabled     bool     `toml:"enabled"`
	IdleTimeout Duration `toml:"idle_timeout"`
	OnSuspend   bool     `toml:"on_suspend"`
}

// Sync configures the background wacli sync process.
type Sync struct {
	Autostart      bool     `toml:"autostart"`
	PollInterval   Duration `toml:"poll_interval"`
	DownloadMedia  bool     `toml:"download_media"`
	SendSocketWait Duration `toml:"send_socket_wait"`
}

// Media controls inline previews.
type Media struct {
	Preview   bool `toml:"preview"`
	Rows      int  `toml:"rows"`
	TextLines int  `toml:"text_lines"`
	// AutoDownload is the largest attachment fetched without being asked.
	// Zero downloads nothing.
	AutoDownload Size `toml:"auto_download"`
	// Graphics draws real pixels where the terminal can. False falls back to
	// half blocks everywhere.
	Graphics bool `toml:"graphics"`
}

// Theme points at a generated palette.
type Theme struct {
	File string `toml:"file"`
}

// Wacli configures how the CLI is invoked.
type Wacli struct {
	Bin     string   `toml:"bin"`
	Account string   `toml:"account"`
	Store   string   `toml:"store"`
	Timeout Duration `toml:"timeout"`
	// PostSendWait is how long wacli holds the connection open after sending,
	// so it can answer a retry receipt itself.
	PostSendWait Duration `toml:"post_send_wait"`
}

// Config is the whole configuration.
type Config struct {
	UI    UI                           `toml:"ui"`
	Lock  Lock                         `toml:"lock"`
	Sync  Sync                         `toml:"sync"`
	Media Media                        `toml:"media"`
	Theme Theme                        `toml:"theme"`
	Wacli Wacli                        `toml:"wacli"`
	Keys  map[string]map[string]string `toml:"keys"`
}

// Warning is a non-fatal problem found while loading, such as a key that no
// version of wa understands. Warnings are shown once and then ignored.
type Warning struct {
	File string
	Key  string
	Msg  string
}

func (w Warning) Error() string {
	if w.Key != "" {
		return fmt.Sprintf("%s: unknown setting %q", w.File, w.Key)
	}
	return fmt.Sprintf("%s: %s", w.File, w.Msg)
}

// actionModes are the key tables whose values are action names.
var actionModes = map[string]bool{
	"normal": true, "insert": true, "visual": true,
	"cmdline": true, "search": true,
}

// grammarModes are the key tables whose values name a motion or a text object.
// Their names are checked by the modal engine, which owns the grammar.
var grammarModes = map[string]bool{"motion": true, "textobj": true}
