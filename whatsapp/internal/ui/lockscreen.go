package ui

import (
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/lock"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/theme"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// LockScreen is the password gate.
//
// While it is up, no chat data is drawn at all - not a name, not a snippet.
// A lock screen that leaves the conversation legible behind it protects
// nothing.
//
// It also sets the password, because the alternative was leaving wa to run
// `wa lock set` in a shell, and somebody who has just been told "no password
// is set" is not in a shell.
type LockScreen struct {
	path    string
	locked  bool
	input   []rune
	message string
	// attempts counts failures, shown so a mistyped password is obvious.
	attempts int

	// setting is the two-step "choose a password" flow: nil when unlocking.
	setting *setFlow

	// frame advances while the screen is up, for the animation.
	frame int
	// lockedAt is when the screen went up, shown as "locked for 4 minutes".
	lockedAt time.Time
	now      func() time.Time
}

// setFlow is a password being chosen: typed once, then again.
type setFlow struct {
	first    string
	repeated bool
}

// NewLockScreen returns a screen for the credential at path.
func NewLockScreen(path string, startLocked bool) *LockScreen {
	return &LockScreen{
		path:     path,
		locked:   startLocked && lock.Exists(path),
		lockedAt: time.Now(),
		now:      time.Now,
	}
}

// Locked reports whether the interface is gated.
func (l *LockScreen) Locked() bool { return l.locked }

// Setting reports whether the screen is asking for a new password rather than
// for the existing one.
func (l *LockScreen) Setting() bool { return l.setting != nil }

// HasPassword reports whether a credential exists.
func (l *LockScreen) HasPassword() bool { return lock.Exists(l.path) }

// Lock raises the screen. It does nothing when no password is set, since
// there would be no way back in.
func (l *LockScreen) Lock() bool {
	if !lock.Exists(l.path) {
		return false
	}
	l.locked = true
	l.input = nil
	l.message = ""
	l.setting = nil
	l.lockedAt = l.clock()
	return true
}

// BeginSet raises the screen to choose a password, which is how the lock is
// turned on from inside wa.
func (l *LockScreen) BeginSet() {
	l.locked = true
	l.input = nil
	l.message = ""
	l.setting = &setFlow{}
	l.lockedAt = l.clock()
}

// ClearPassword removes the credential and lets the interface back in.
func (l *LockScreen) ClearPassword() error {
	if err := lock.Clear(l.path); err != nil {
		return err
	}
	l.locked = false
	l.setting = nil
	l.input = nil
	return nil
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

// Cancel abandons a password that was being chosen. It cannot abandon the
// gate itself: that is the point of a gate.
func (l *LockScreen) Cancel() bool {
	if l.setting == nil {
		return false
	}
	l.setting = nil
	l.locked = lock.Exists(l.path) && l.locked && false
	l.input = nil
	l.message = ""
	return true
}

// Tick advances the animation.
func (l *LockScreen) Tick() { l.frame++ }

// Submit checks the typed password, or takes the next step of setting one.
func (l *LockScreen) Submit() (bool, error) {
	pw := string(l.input)
	l.input = nil

	if l.setting != nil {
		return l.submitSet(pw)
	}

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

// submitSet is the choose-a-password flow: once for the password, once to
// confirm it.
func (l *LockScreen) submitSet(pw string) (bool, error) {
	if !l.setting.repeated {
		if strings.TrimSpace(pw) == "" {
			l.message = "an empty password would gate nothing"
			return false, nil
		}
		l.setting.first = pw
		l.setting.repeated = true
		l.message = ""
		return false, nil
	}
	if pw != l.setting.first {
		l.setting = &setFlow{}
		l.message = "they do not match; start again"
		return false, nil
	}
	if err := lock.Set(l.path, pw); err != nil {
		l.message = err.Error()
		return false, err
	}
	l.setting = nil
	l.locked = false
	l.message = ""
	return true, nil
}

// View renders the screen, centred, with the wave moving underneath it.
func (l *LockScreen) View(st theme.Styles, width, height int) string {
	if width < 8 || height < 6 {
		return strings.Repeat("\n", maxInt(0, height-1))
	}
	if st.Shape != theme.ShapeSquare {
		return l.pillView(st, width, height)
	}

	title := lockTitle
	prompt := "password"
	switch {
	case l.setting != nil && l.setting.repeated:
		prompt = "again"
	case l.setting != nil:
		prompt = "new password"
	}

	field := prompt + "  " + l.dots()
	hint := "enter to unlock · ctrl-u clears"
	switch {
	case l.setting != nil:
		hint = "enter to continue · esc to think again"
	case !l.HasPassword():
		hint = "no password is set · :lock set"
	}

	var block []string
	block = append(block, title...)
	block = append(block, "", l.wave(width/2), "", field)
	if l.message != "" {
		block = append(block, "", l.message)
	} else if l.setting == nil && l.HasPassword() {
		block = append(block, "", "locked "+lockedFor(l.clock().Sub(l.lockedAt)))
	} else {
		block = append(block, "", "")
	}
	block = append(block, "", hint)

	top := maxInt(0, (height-len(block))/2)
	var b strings.Builder
	for i := 0; i < height; i++ {
		if i > 0 {
			b.WriteString("\n")
		}
		idx := i - top
		if idx < 0 || idx >= len(block) {
			continue
		}
		text := block[idx]
		if text == "" {
			continue
		}
		style := l.styleFor(st, idx, len(block), text)
		pad := maxInt(0, (width-render.VisibleWidth(text))/2)
		b.WriteString(strings.Repeat(" ", pad))
		b.WriteString(style.Render(text))
	}
	return b.String()
}

// pillView is the lock screen in the rice's shapes.
//
// A lock icon in an accent pill, the state under it, the password as a rounded
// field of dots, and a slow wave of dots beneath that. No block letters: at
// terminal resolution pixel art is exactly the stepped, square look the rest of
// the interface was redrawn to get rid of.
func (l *LockScreen) pillView(st theme.Styles, width, height int) string {
	p := st.Palette

	heading := "locked"
	switch {
	case l.setting != nil && l.setting.repeated:
		heading = "type it again"
	case l.setting != nil:
		heading = "choose a password"
	case !l.HasPassword():
		heading = "no password is set"
	}
	sub := ""
	switch {
	case l.message != "":
		sub = l.message
	case l.setting == nil && l.HasPassword():
		sub = "locked " + lockedFor(l.clock().Sub(l.lockedAt))
	}
	hint := "enter to unlock  ·  ctrl-u clears"
	switch {
	case l.setting != nil:
		hint = "enter to continue  ·  esc to think again"
	case !l.HasPassword():
		hint = ":lock set chooses one"
	}

	fieldW := minInt(36, maxInt(12, width-8))
	dots := l.dotsFor(fieldW - 4)
	field := st.Chip(render.Pad(dots, fieldW-2), p.Fg, p.RaisedHi, false)

	subStyle := st.Timestamp
	if l.message != "" {
		subStyle = st.StatusErr.UnsetBackground()
	}

	block := []string{
		st.Chip(" "+st.Icon("lock")+" ", p.OnAccent, p.Accent, true),
		"",
		st.ListName.Bold(true).Render(heading),
		subStyle.Render(sub),
		"",
		field,
		"",
		l.dotWave(minInt(fieldW, 32), st),
		"",
		st.Timestamp.Render(hint),
	}

	top := maxInt(0, (height-len(block))/2)
	var b strings.Builder
	for i := 0; i < height; i++ {
		if i > 0 {
			b.WriteString("\n")
		}
		idx := i - top
		if idx < 0 || idx >= len(block) || block[idx] == "" {
			continue
		}
		pad := maxInt(0, (width-render.VisibleWidth(block[idx]))/2)
		b.WriteString(strings.Repeat(" ", pad) + block[idx])
	}
	return b.String()
}

// dotsFor is the typed password as filled dots, with a caret that breathes,
// fitted to a width.
func (l *LockScreen) dotsFor(width int) string {
	n := len(l.input)
	caret := "│"
	if l.frame%10 >= 5 {
		caret = " "
	}
	shown := minInt(n, maxInt(0, width-6))
	out := strings.Repeat("● ", shown)
	if n > shown {
		out += fmt.Sprintf("+%d ", n-shown)
	}
	if n == 0 {
		return caret
	}
	return strings.TrimRight(out, " ") + " " + caret
}

// dotWave is the animation: a row of dots whose size follows a travelling
// sine, drawn from the faint colour up to the accent. It moves, so a locked
// terminal is plainly alive, and it is soft, so it is not the thing you look at.
func (l *LockScreen) dotWave(width int, st theme.Styles) string {
	p := st.Palette
	glyphs := []string{"·", "∙", "•", "●"}
	var b strings.Builder
	for x := 0; x < width; x++ {
		v := (math.Sin(float64(x)/2.2-float64(l.frame)/3.0) + 1) / 2
		i := int(v * float64(len(glyphs)-1))
		colour := theme.Mix(p.Faint, p.Accent, v)
		b.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color(colour)).Render(glyphs[i]))
		if x < width-1 {
			b.WriteString(" ")
		}
	}
	return b.String()
}

// styleFor colours one line of the screen: the mark bright, the wave in the
// accent, the error red, everything else quiet.
func (l *LockScreen) styleFor(st theme.Styles, idx, total int, text string) lipgloss.Style {
	switch {
	case idx < len(lockTitle):
		return st.Lock
	case strings.ContainsAny(text, "▁▂▃▄▅▆▇█"):
		return st.ListFilter
	case l.message != "" && strings.Contains(text, l.message):
		return st.StatusErr
	case idx == total-1:
		return st.ListTime
	}
	return st.Lock
}

// dots are the typed characters, as a row of filled and empty circles, so the
// length is visible without the password being.
func (l *LockScreen) dots() string {
	const shown = 24
	n := len(l.input)
	if n > shown {
		return strings.Repeat("●", shown) + fmt.Sprintf(" +%d", n-shown)
	}
	// A cursor that blinks with the animation, so the screen is visibly alive
	// even before anything is typed.
	caret := "▁"
	if l.frame%10 < 5 {
		caret = "▂"
	}
	return strings.Repeat("●", n) + caret + strings.Repeat("·", maxInt(0, 12-n))
}

// wave is the animation: a sine of block characters, drifting sideways.
//
// It is not decoration for its own sake. A locked terminal that is perfectly
// still is indistinguishable from a hung one, and this is the cheapest
// possible way to say the session is alive and waiting.
func (l *LockScreen) wave(width int) string {
	if width < 8 {
		width = 8
	}
	if width > 48 {
		width = 48
	}
	const blocks = "▁▂▃▄▅▆▇█▇▆▅▄▃▂"
	runes := []rune(blocks)
	var b strings.Builder
	for x := 0; x < width; x++ {
		// Two sines of different periods, so the pattern does not repeat
		// visibly across the width of the screen.
		v := math.Sin(float64(x)/3.0+float64(l.frame)/4.0) +
			0.5*math.Sin(float64(x)/7.0-float64(l.frame)/6.0)
		i := int((v + 1.5) / 3.0 * float64(len(runes)-1))
		if i < 0 {
			i = 0
		}
		if i >= len(runes) {
			i = len(runes) - 1
		}
		b.WriteRune(runes[i])
	}
	return b.String()
}

func (l *LockScreen) clock() time.Time {
	if l.now != nil {
		return l.now()
	}
	return time.Now()
}

// lockTitle is the mark at the top of the screen.
var lockTitle = []string{
	"█   █  ███",
	"█ █ █ █   █",
	"█ █ █ █████",
	" █ █  █   █",
}

// lockedFor is how long the screen has been up, in the words a person uses.
func lockedFor(d time.Duration) string {
	switch {
	case d < time.Minute:
		return "just now"
	case d < 2*time.Minute:
		return "for a minute"
	case d < time.Hour:
		return fmt.Sprintf("for %d minutes", int(d.Minutes()))
	case d < 2*time.Hour:
		return "for an hour"
	default:
		return fmt.Sprintf("for %d hours", int(d.Hours()))
	}
}
