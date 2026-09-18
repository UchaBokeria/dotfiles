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
	// Glass leaves the bars unpainted so a compositor's blur shows through.
	// "auto" turns it on where there is something behind worth seeing.
	Glass string `toml:"glass"`
	// WhichKey shows what can be pressed next once a key sequence is under
	// way, and WhichKeyDelay is how long to wait before showing it. Zero
	// shows it at once, which is what somebody learning the keys wants.
	WhichKey      bool     `toml:"whichkey"`
	WhichKeyDelay Duration `toml:"whichkey_delay"`
	// Groups names a prefix, so a popup can say "+media" rather than listing
	// a letter with nothing beside it.
	Groups map[string]string `toml:"groups"`

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
	// Browser opens a link. Empty falls back to $BROWSER, then to whichever
	// browser is on PATH, then to the desktop's own handler.
	Browser string `toml:"browser"`
	Links   bool   `toml:"links"`

	// Shape is the edge language every chip, badge, field and bubble shares:
	// "pill" rounds them into capsules with the same Nerd Font half circles
	// the rice's tmux and waybar use, "rounded" softens them with half blocks
	// any font has, "square" leaves them as blocks.
	Shape string `toml:"shape"`
	// IconSet is "nerd", "unicode" or "ascii". Individual glyphs are replaced
	// in the top-level [icons] table.
	IconSet string `toml:"icon_set"`
	// Layout is the spacing scale.
	Layout Layout `toml:"layout"`
	// BubbleEdges is how a message of several lines is rounded: "half" caps
	// its first and last rows with half circles and gives the rows between
	// half-block sides that meet them; "ends" keeps the sides full width;
	// "all" caps every row.
	BubbleEdges string `toml:"bubble_edges"`
}

// Layout is every gap in the interface, in cells.
//
// One scale, set in one place. A TUI with a margin here, a two-cell gap there
// and no padding anywhere else looks improvised; this is the terminal's
// version of the rice's s_xs..s_xl spacing tokens.
type Layout struct {
	// Margin is the empty border between the screen edge and everything.
	Margin int `toml:"margin"`
	// Gap separates the chat list from the conversation. Space does the
	// separating; there is no rule to draw.
	Gap int `toml:"gap"`
	// ListRows is lines per chat in the list: 2 adds the last message under
	// the name, 1 is dense.
	ListRows int `toml:"list_rows"`
	// BubbleGap is blank rows between messages.
	BubbleGap int `toml:"bubble_gap"`
	// Padding is space inside a bubble, a field or a popup, left and right.
	Padding int `toml:"padding"`
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
	// MaxDownload is the largest attachment wacli will fetch. It is wacli's
	// compiled-in limit, not wa's, and it is a setting here only because a
	// wacli built with a bigger one is the only way past it.
	MaxDownload Size `toml:"max_download"`
}

// Theme points at a generated palette.
type Theme struct {
	// Colors replace individual palette roles - accent, bubble_mine, raised,
	// any key of theme.toml - on top of whatever the palette came from, so a
	// single colour can be adjusted without forking a theme file.
	Colors map[string]string `toml:"colors"`
	File   string            `toml:"file"`
	// FollowWallpaper reads the colours wallust or pywal pulled out of the
	// wallpaper, when no file of our own is given.
	FollowWallpaper bool `toml:"follow_wallpaper"`
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
	// Icons replaces individual glyphs by name, whatever the icon set.
	Icons map[string]string `toml:"icons"`
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
