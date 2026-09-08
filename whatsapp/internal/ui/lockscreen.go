package ui

import (
	"strings"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/lock"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/theme"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/ui/render"
)

// LockScreen is the password gate.
//
// While it is up, no chat data is drawn at all - not a name, not a snippet.
// A lock screen that leaves the conversation legible behind it protects
// nothing.
type LockScreen struct {
	path    string
	locked  bool
	input   []rune
	message string
	// attempts counts failures, shown so a mistyped password is obvious.
	attempts int
}

// NewLockScreen returns a screen for the credential at path.
func NewLockScreen(path string, startLocked bool) *LockScreen {
	return &LockScreen{path: path, locked: startLocked && lock.Exists(path)}
}

// Locked reports whether the interface is gated.
func (l *LockScreen) Locked() bool { return l.locked }

// Lock raises the screen. It does nothing when no password is set, since
// there would be no way back in.
func (l *LockScreen) Lock() bool {
	if !lock.Exists(l.path) {
		return false
	}
	l.locked = true
	l.input = nil
	l.message = ""
	return true
}

// Type adds a character to the password.
func (l *LockScreen) Type(r rune) { l.input = append(l.input, r) }

// Backspace removes one.
func (l *LockScreen) Backspace() {
	if n := len(l.input); n > 0 {
		l.input = l.input[:n-1]
	}
}

// Clear empties the input, for ctrl-u.
func (l *LockScreen) Clear() { l.input = nil }

// Submit checks the typed password.
func (l *LockScreen) Submit() (bool, error) {
	pw := string(l.input)
	l.input = nil

	ok, err := lock.Verify(l.path, pw)
	if err != nil {
		l.message = err.Error()
		return false, err
	}
	if !ok {
		l.attempts++
		l.message = "wrong password"
		return false, nil
	}
	l.locked = false
	l.attempts = 0
	l.message = ""
	return true, nil
}

// View renders the screen, centred.
func (l *LockScreen) View(st theme.Styles, width, height int) string {
	title := "wa"
	prompt := "password: " + strings.Repeat("•", len(l.input))

	lines := []string{title, "", prompt}
	if l.message != "" {
		lines = append(lines, "", l.message)
	}

	top := maxInt(0, (height-len(lines))/2)
	var b strings.Builder
	for i := 0; i < height; i++ {
		if i > 0 {
			b.WriteString("\n")
		}
		idx := i - top
		if idx < 0 || idx >= len(lines) {
			continue
		}
		text := lines[idx]
		style := st.Lock
		if l.message != "" && idx == len(lines)-1 {
			style = st.StatusErr
		}
		pad := maxInt(0, (width-render.VisibleWidth(text))/2)
		b.WriteString(strings.Repeat(" ", pad))
		b.WriteString(style.Render(text))
	}
	return b.String()
}
