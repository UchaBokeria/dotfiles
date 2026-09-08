package ui

import (
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/theme"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/ui/render"
)

// maxLogLines bounds the :log buffer.
const maxLogLines = 500

// Level is how loud a log entry is.
type Level int

const (
	LevelInfo Level = iota
	LevelWarn
	LevelError
)

// LogEntry is one recorded message.
type LogEntry struct {
	At    time.Time
	Level Level
	Text  string
}

// Log is the :log buffer.
//
// Everything that reaches the status line is recorded here too. A status line
// shows one thing at a time and is overwritten by the next event; without a
// buffer behind it, an error that flashed past while the user was typing is
// simply gone.
type Log struct {
	mu      sync.Mutex
	entries []LogEntry
	// announced records one-time degradation notices, so a fallback is
	// reported once rather than on every read.
	announced map[string]bool
}

// NewLog returns an empty buffer.
func NewLog() *Log {
	return &Log{announced: map[string]bool{}}
}

func (l *Log) add(level Level, text string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.entries = append(l.entries, LogEntry{At: time.Now(), Level: level, Text: text})
	if len(l.entries) > maxLogLines {
		l.entries = l.entries[len(l.entries)-maxLogLines:]
	}
}

// Infof, Warnf and Errorf record an entry.
func (l *Log) Infof(format string, args ...any)  { l.add(LevelInfo, fmt.Sprintf(format, args...)) }
func (l *Log) Warnf(format string, args ...any)  { l.add(LevelWarn, fmt.Sprintf(format, args...)) }
func (l *Log) Errorf(format string, args ...any) { l.add(LevelError, fmt.Sprintf(format, args...)) }

// Announce records a message once per key. It is what makes "each degradation
// is reported exactly once" true rather than aspirational.
func (l *Log) Announce(key, text string) bool {
	l.mu.Lock()
	if l.announced[key] {
		l.mu.Unlock()
		return false
	}
	l.announced[key] = true
	l.mu.Unlock()

	l.add(LevelWarn, text)
	return true
}

// Entries copies the buffer.
func (l *Log) Entries() []LogEntry {
	l.mu.Lock()
	defer l.mu.Unlock()
	return append([]LogEntry{}, l.entries...)
}

// Last returns the most recent entry.
func (l *Log) Last() (LogEntry, bool) {
	l.mu.Lock()
	defer l.mu.Unlock()
	if len(l.entries) == 0 {
		return LogEntry{}, false
	}
	return l.entries[len(l.entries)-1], true
}

// Text is the whole buffer as plain lines, for tests and :log.
func (l *Log) Text() string {
	var b strings.Builder
	for _, e := range l.Entries() {
		fmt.Fprintf(&b, "%s %s\n", e.At.Format("15:04:05"), e.Text)
	}
	return b.String()
}

// View renders the buffer, newest at the bottom.
func (l *Log) View(st theme.Styles, width, height int) string {
	entries := l.Entries()
	if len(entries) > height {
		entries = entries[len(entries)-height:]
	}
	var b strings.Builder
	for i, e := range entries {
		if i > 0 {
			b.WriteString("\n")
		}
		line := fmt.Sprintf("%s  %s", e.At.Format("15:04:05"), e.Text)
		line = render.Pad(render.Truncate(line, width), width)
		switch e.Level {
		case LevelError:
			b.WriteString(st.StatusErr.Render(line))
		case LevelWarn:
			b.WriteString(st.StatusWarn.Render(line))
		default:
			b.WriteString(st.Picker.Render(line))
		}
	}
	return b.String()
}
