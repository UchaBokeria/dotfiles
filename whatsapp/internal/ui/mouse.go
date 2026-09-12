package ui

import (
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// region names a part of the screen, for hit testing.
type region int

const (
	regionNone region = iota
	regionList
	regionMessages
	regionQuickfix
	regionComposer
	regionStatus
	regionPrompt
	regionDivider
	regionHeader
)

// layout is where everything sits this frame. Hit testing and drawing read the
// same struct, so a click cannot land somewhere the pane is not.
type layout struct {
	listWidth  int
	chatX      int // first column of the right-hand pane
	chatWidth  int
	bodyHeight int

	paneRows     int
	quickfixRows int
	composerRows int

	// bodyTop is the first row of the panes, under the header.
	bodyTop   int
	statusRow int
	promptRow int
	narrow    bool
}

func (a *App) layout() layout {
	l := layout{
		narrow:     a.narrow(),
		listWidth:  a.listWidth(),
		chatWidth:  a.chatWidth(),
		bodyHeight: a.bodyHeight(),
		// The body starts under the header, so every row a click reports has
		// to have the header subtracted from it before it means anything.
		bodyTop:   headerRows,
		statusRow: a.height - 2,
		promptRow: a.height - 1,
	}
	l.chatX = l.listWidth + 1
	if l.narrow {
		l.chatX = 0
	}

	l.composerRows = a.composer.Height()
	if a.showQF && a.qf.Open() {
		l.quickfixRows = minInt(10, maxInt(3, l.bodyHeight/3))
	}
	l.paneRows = maxInt(1, l.bodyHeight-l.composerRows-l.quickfixRows)
	return l
}

// regionAt maps a screen position onto a region and the row within it.
func (a *App) regionAt(x, y int) (region, int) {
	l := a.layout()

	switch {
	case y == l.statusRow:
		return regionStatus, 0
	case y == l.promptRow:
		return regionPrompt, 0
	case y < l.bodyTop:
		return regionHeader, 0
	}
	y -= l.bodyTop
	if y < 0 || y >= l.bodyHeight {
		return regionNone, 0
	}

	if l.narrow {
		if a.focus == FocusList {
			return regionList, y
		}
		return a.rightRegion(l, y)
	}

	switch {
	case x < l.listWidth:
		return regionList, y
	case x == l.listWidth:
		return regionDivider, y
	default:
		return a.rightRegion(l, y)
	}
}

// rightRegion splits the right-hand column into the conversation, the results
// list and the composer.
func (a *App) rightRegion(l layout, y int) (region, int) {
	if y < l.paneRows {
		return regionMessages, y
	}
	y -= l.paneRows
	if l.quickfixRows > 0 {
		if y < l.quickfixRows {
			return regionQuickfix, y
		}
		y -= l.quickfixRows
	}
	return regionComposer, y
}

// selection is a mouse drag over the rendered frame.
type selection struct {
	active   bool
	dragging bool
	// anchor is where the drag started, head where the pointer is now. Both
	// are screen coordinates.
	anchorX, anchorY int
	headX, headY     int
}

// ordered returns the selection with the anchor before the head.
func (s selection) ordered() (x1, y1, x2, y2 int) {
	if s.anchorY < s.headY || (s.anchorY == s.headY && s.anchorX <= s.headX) {
		return s.anchorX, s.anchorY, s.headX, s.headY
	}
	return s.headX, s.headY, s.anchorX, s.anchorY
}

// empty reports whether the drag covers nothing.
func (s selection) empty() bool {
	x1, y1, x2, y2 := s.ordered()
	return y1 == y2 && x2 <= x1
}

// handleMouse routes a mouse event, then drains whatever it queued.
//
// Draining here rather than at each return keeps every branch honest: a menu
// item that forwards a message queues a background operation, and a branch
// that forgot to collect it would silently do nothing.
func (a *App) handleMouse(m tea.MouseMsg) tea.Cmd {
	return withQueued(a, a.routeMouse(m))
}

func (a *App) routeMouse(m tea.MouseMsg) tea.Cmd {
	if a.idle != nil {
		a.idle.Touch()
	}
	if a.lockScreen != nil && a.lockScreen.Locked() {
		return nil
	}

	// The menu is modal: while it is up, it takes every click.
	if a.menu.IsOpen() {
		return a.menuMouse(m)
	}
	if a.overlay.IsOpen() {
		switch m.Button {
		case tea.MouseButtonWheelUp:
			a.overlay.Scroll(-3, a.height)
		case tea.MouseButtonWheelDown:
			a.overlay.Scroll(3, a.height)
		}
		return nil
	}

	// The picker is modal too: reacting and forwarding both go through it, and
	// a list you can see but not click is a list that looks broken.
	if a.picker.IsOpen() {
		return a.pickerMouse(m)
	}

	switch m.Button {
	case tea.MouseButtonWheelUp:
		a.wheel(m.X, m.Y, -3)
		return nil
	case tea.MouseButtonWheelDown:
		a.wheel(m.X, m.Y, 3)
		return nil
	}

	switch m.Action {
	case tea.MouseActionPress:
		switch m.Button {
		case tea.MouseButtonLeft:
			return a.pressLeft(m.X, m.Y)
		case tea.MouseButtonRight:
			return a.pressRight(m.X, m.Y)
		}
	case tea.MouseActionMotion:
		if a.sel.dragging {
			a.sel.headX, a.sel.headY = m.X, m.Y
			a.sel.active = true
		}
	case tea.MouseActionRelease:
		if a.sel.dragging {
			a.sel.dragging = false
			a.sel.headX, a.sel.headY = m.X, m.Y
			a.finishSelection()
		}
	}
	return nil
}

// wheel scrolls whichever pane the pointer is over, which is what every other
// program does and what the hand expects.
func (a *App) wheel(x, y, delta int) {
	switch r, _ := a.regionAt(x, y); r {
	case regionList:
		a.list.Scroll(delta)
	case regionQuickfix:
		if delta > 0 {
			a.qf.Next()
		} else {
			a.qf.Prev()
		}
	default:
		a.pane.Scroll(delta)
		if delta < 0 {
			a.maybeLoadOlder()
		}
	}
}

// pressLeft selects what was clicked and starts a drag.
func (a *App) pressLeft(x, y int) tea.Cmd {
	r, row := a.regionAt(x, y)

	switch r {
	case regionList:
		a.setFocus(FocusList)
		if i := a.list.RowToIndex(row); i >= 0 {
			a.list.MoveTo(i)
			a.followSelection()
		}
	case regionMessages:
		a.setFocus(FocusChat)
		if i := a.pane.RowToMessage(row); i >= 0 {
			a.pane.SelectIndex(i)
		}
	case regionQuickfix:
		if it, ok := a.qf.SelectRow(row); ok {
			if err := a.openQuickfixItem(it); err != nil {
				a.setError(err.Error())
			}
		}
	case regionComposer:
		a.setFocus(FocusComposer)
	}

	// Every click also begins a potential drag. A press that never moves
	// selects nothing, so this costs the click nothing.
	a.sel = selection{dragging: true, anchorX: x, anchorY: y, headX: x, headY: y}
	return nil
}

// pressRight opens the context menu for whatever is under the pointer.
func (a *App) pressRight(x, y int) tea.Cmd {
	r, row := a.regionAt(x, y)

	switch r {
	case regionList:
		if i := a.list.RowToIndex(row); i >= 0 {
			a.list.MoveTo(i)
			a.followSelection()
		}
		a.openChatMenu(x, y)
	case regionMessages:
		if i := a.pane.RowToMessage(row); i >= 0 {
			a.pane.SelectIndex(i)
		}
		a.openMessageMenu(x, y)
	case regionComposer:
		a.openComposerMenu(x, y)
	}
	return nil
}

// pickerMouse handles clicks while the picker is up.
func (a *App) pickerMouse(m tea.MouseMsg) tea.Cmd {
	switch m.Button {
	case tea.MouseButtonWheelUp:
		a.picker.Scroll(-1)
		return nil
	case tea.MouseButtonWheelDown:
		a.picker.Scroll(1)
		return nil
	case tea.MouseButtonRight:
		if m.Action == tea.MouseActionPress {
			a.picker.Close()
		}
		return nil
	}

	switch m.Action {
	case tea.MouseActionMotion:
		// Following the pointer, the way every menu does. Without it the
		// highlight and the pointer disagree about what a click will choose.
		a.picker.SelectRow(m.Y)
	case tea.MouseActionPress:
		if m.Button != tea.MouseButtonLeft {
			return nil
		}
		if !a.picker.SelectRow(m.Y) {
			return nil
		}
		if err := a.picker.Accept(); err != nil {
			a.setError(err.Error())
		}
	}
	return nil
}

// menuMouse handles clicks while the menu is up.
func (a *App) menuMouse(m tea.MouseMsg) tea.Cmd {
	mx, my, mw, mh := a.menu.Bounds()
	inside := m.X >= mx && m.X < mx+mw && m.Y >= my && m.Y < my+mh

	switch m.Action {
	case tea.MouseActionMotion:
		if inside {
			a.menu.SelectRow(m.Y)
		}
	case tea.MouseActionPress:
		if !inside {
			// A click outside dismisses, as every menu everywhere does.
			a.menu.Close()
			return nil
		}
		if a.menu.SelectRow(m.Y) {
			if err := a.menu.Activate(); err != nil {
				a.setError(err.Error())
			}
		}
	}
	return nil
}

// finishSelection copies whatever the drag covered.
func (a *App) finishSelection() {
	if a.sel.empty() {
		a.sel.active = false
		return
	}
	text := a.selectedText()
	if strings.TrimSpace(text) == "" {
		a.sel.active = false
		return
	}
	if err := a.clip.Write(text); err != nil {
		a.setError("copy: " + err.Error())
		return
	}
	// The engine's registers should see it too, so p pastes what was selected.
	a.engine.Registers().Yank('"', text, false)
	a.setStatus(plural(len([]rune(text)), "character", "characters") + " copied")
}

// selectedText pulls the drag's contents out of the last rendered frame.
//
// Reading the frame rather than the model is deliberate: the user selected
// what they could see, including the gutter, a timestamp, or part of two
// different messages, and anything cleverer would copy something they did not
// point at.
func (a *App) selectedText() string {
	x1, y1, x2, y2 := a.sel.ordered()
	frame := a.frame
	if len(frame) == 0 {
		return ""
	}

	var out []string
	for y := y1; y <= y2 && y < len(frame); y++ {
		if y < 0 {
			continue
		}
		line := stripANSI(frame[y])
		from, to := 0, render.VisibleWidth(line)
		if y == y1 {
			from = x1
		}
		if y == y2 {
			to = x2
		}
		out = append(out, strings.TrimRight(sliceCols(line, from, to), " "))
	}
	return strings.Join(out, "\n")
}

// sliceCols returns the display columns [from, to) of a plain string.
func sliceCols(s string, from, to int) string {
	if to <= from {
		return ""
	}
	return takeCols(dropCols(s, from), to-from)
}

// stripANSI removes escape sequences so copied text is text.
//
// Shared with the renderer: a hyperlink's payload is a URL full of letters, so
// a stripper that ends a sequence at the first letter copies half the escape
// into the clipboard.
func stripANSI(s string) string { return render.StripEscapes(s) }

// highlightSelection redraws the selected span so the drag is visible.
func (a *App) highlightSelection(frame []string) []string {
	if !a.sel.active || a.sel.empty() {
		return frame
	}
	x1, y1, x2, y2 := a.sel.ordered()

	out := make([]string, len(frame))
	copy(out, frame)
	for y := y1; y <= y2 && y < len(out); y++ {
		if y < 0 {
			continue
		}
		plain := stripANSI(out[y])
		width := render.VisibleWidth(plain)
		from, to := 0, width
		if y == y1 {
			from = clampInt(x1, 0, width)
		}
		if y == y2 {
			to = clampInt(x2, 0, width)
		}
		if to <= from {
			continue
		}
		out[y] = takeCols(out[y], from) +
			a.styles.Match.Render(sliceCols(plain, from, to)) +
			dropCols(out[y], to)
	}
	return out
}

func plural(n int, one, many string) string {
	word := many
	if n == 1 {
		word = one
	}
	return itoa(n) + " " + word
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var b [20]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		b[i] = '-'
	}
	return string(b[i:])
}
