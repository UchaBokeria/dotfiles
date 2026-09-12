package ui

import (
	"context"
	"strings"
	"sync"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
)

// fakeClip records what the interface copied.
type fakeClip struct {
	mu      sync.Mutex
	written []string
	content string
	err     error
}

func (f *fakeClip) Write(s string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.err != nil {
		return f.err
	}
	f.written = append(f.written, s)
	return nil
}

func (f *fakeClip) Read() (string, error) { return f.content, f.err }

func (f *fakeClip) last() string {
	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.written) == 0 {
		return ""
	}
	return f.written[len(f.written)-1]
}

func withClip(c Clipboard) func(*Deps) {
	return func(d *Deps) { d.Clipboard = c }
}

// press, drag and release drive the mouse.
func (a *testApp) press(button tea.MouseButton, x, y int) {
	a.App.Update(tea.MouseMsg{Action: tea.MouseActionPress, Button: button, X: x, Y: y})
}

func (a *testApp) drag(x, y int) {
	a.App.Update(tea.MouseMsg{Action: tea.MouseActionMotion, Button: tea.MouseButtonLeft, X: x, Y: y})
}

func (a *testApp) release(x, y int) {
	a.App.Update(tea.MouseMsg{Action: tea.MouseActionRelease, Button: tea.MouseButtonLeft, X: x, Y: y})
}

func (a *testApp) wheelAt(x, y int, up bool) {
	b := tea.MouseButtonWheelDown
	if up {
		b = tea.MouseButtonWheelUp
	}
	a.App.Update(tea.MouseMsg{Action: tea.MouseActionPress, Button: b, X: x, Y: y})
}

func TestRegionHitTesting(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	l := a.layout()

	cases := []struct {
		name string
		x, y int
		want region
	}{
		{"header", 5, 0, regionHeader},
		{"chat list", 5, l.bodyTop + 3, regionList},
		{"divider", l.listWidth, l.bodyTop + 3, regionDivider},
		{"messages", l.chatX + 5, l.bodyTop + 2, regionMessages},
		{"composer", l.chatX + 5, l.bodyTop + l.bodyHeight - 1, regionComposer},
		{"status", 10, l.statusRow, regionStatus},
		{"prompt", 10, l.promptRow, regionPrompt},
	}
	for _, c := range cases {
		if got, _ := a.regionAt(c.x, c.y); got != c.want {
			t.Errorf("%s at (%d,%d) = %v, want %v", c.name, c.x, c.y, got, c.want)
		}
	}
}

func TestLeftClickSelectsAChat(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)

	// Row 0 is the top bar and row 1 is the list's own title, so the second
	// chat is on row 3.
	a.press(tea.MouseButtonLeft, 5, 3)

	if a.Focus() != FocusList {
		t.Errorf("focus = %v, want the chat list", a.Focus())
	}
	if a.list.Index() != 1 {
		t.Errorf("selected index = %d, want the second chat", a.list.Index())
	}
	got, _ := a.CurrentChat()
	if got.User != "b" {
		t.Errorf("opened %v, want Beka", got)
	}
}

func TestLeftClickOnTheHeaderSelectsNothing(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	before := a.list.Index()
	a.press(tea.MouseButtonLeft, 5, 0)
	if a.list.Index() != before {
		t.Error("clicking the filter header changed the selection")
	}
}

func TestLeftClickSelectsAMessage(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	l := a.layout()

	// Click well inside the conversation; whichever message is there, the
	// cursor must land on a real one.
	a.press(tea.MouseButtonLeft, l.chatX+6, 4)

	if a.Focus() != FocusChat {
		t.Errorf("focus = %v, want the conversation", a.Focus())
	}
	if _, ok := a.pane.Selected(); !ok {
		t.Error("clicking a message left nothing selected")
	}
}

func TestClickingTheComposerFocusesIt(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	l := a.layout()

	a.press(tea.MouseButtonLeft, l.chatX+3, l.bodyTop+l.bodyHeight-1)
	if a.Focus() != FocusComposer {
		t.Errorf("focus = %v, want the composer", a.Focus())
	}
}

func TestWheelScrollsWithoutMovingTheSelection(t *testing.T) {
	// Scrolling is reading. It should no more change which chat is open, or
	// which message is under the cursor, than scrolling a web page changes
	// which link is focused.
	a := newTestApp(t)
	a.resize(100, 16)
	l := a.layout()
	a.View()

	msgSel := a.pane.Index()
	msgOffset := a.pane.Offset()
	a.wheelAt(l.chatX+5, 3, true)

	if a.pane.Offset() == msgOffset {
		t.Error("the wheel over the conversation did not scroll it")
	}
	if a.pane.Index() != msgSel {
		t.Errorf("the wheel moved the message cursor from %d to %d", msgSel, a.pane.Index())
	}
}

func TestWheelOverTheChatListDoesNotChangeTheOpenChat(t *testing.T) {
	a := newTestApp(t)
	// Short enough that the chat list actually overflows and can scroll.
	a.resize(100, 8)
	for i := 0; i < 20; i++ {
		a.store.setChat(chat(t, string(rune('A'+i)), string(rune('a'+i))+"@s.whatsapp.net"))
	}
	if err := a.list.Load(context.Background()); err != nil {
		t.Fatal(err)
	}

	openBefore, _ := a.CurrentChat()
	selBefore := a.list.Index()
	offsetBefore := a.list.Offset()

	a.wheelAt(3, 3, false)

	if a.list.Offset() == offsetBefore {
		t.Error("the wheel over the chat list did not scroll it")
	}
	if a.list.Index() != selBefore {
		t.Errorf("the wheel moved the list cursor from %d to %d", selBefore, a.list.Index())
	}
	openAfter, _ := a.CurrentChat()
	if openAfter != openBefore {
		t.Errorf("scrolling the list changed the open chat from %v to %v", openBefore, openAfter)
	}
}

func TestDragSelectionCopies(t *testing.T) {
	clip := &fakeClip{}
	a := newTestApp(t, withClip(clip))
	a.resize(100, 30)
	a.View() // the selection reads the rendered frame

	a.press(tea.MouseButtonLeft, 2, 2)
	a.drag(12, 2)
	a.release(12, 2)

	if clip.last() == "" {
		t.Fatalf("nothing was copied; status = %q", a.Status())
	}
	if !strings.Contains(a.Status(), "copied") {
		t.Errorf("status = %q, want it to confirm the copy", a.Status())
	}
}

func TestSelectionAlsoReachesTheUnnamedRegister(t *testing.T) {
	clip := &fakeClip{}
	a := newTestApp(t, withClip(clip))
	a.resize(100, 30)
	a.View()

	a.press(tea.MouseButtonLeft, 2, 2)
	a.drag(14, 2)
	a.release(14, 2)

	if got := a.engine.Registers().Get('"').Text; got == "" {
		t.Error("a mouse selection should also fill the unnamed register so p pastes it")
	}
}

func TestAClickWithoutDraggingCopiesNothing(t *testing.T) {
	clip := &fakeClip{}
	a := newTestApp(t, withClip(clip))
	a.resize(100, 30)
	a.View()

	a.press(tea.MouseButtonLeft, 5, 2)
	a.release(5, 2)

	if clip.last() != "" {
		t.Errorf("a plain click copied %q", clip.last())
	}
}

func TestSelectionSpansLines(t *testing.T) {
	clip := &fakeClip{}
	a := newTestApp(t, withClip(clip))
	a.resize(100, 30)
	a.View()

	a.press(tea.MouseButtonLeft, 2, 1)
	a.drag(20, 3)
	a.release(20, 3)

	if !strings.Contains(clip.last(), "\n") {
		t.Errorf("a selection over three rows produced one line: %q", clip.last())
	}
}

func TestCopiedTextHasNoEscapeCodes(t *testing.T) {
	clip := &fakeClip{}
	a := newTestApp(t, withClip(clip))
	a.resize(100, 30)
	a.View()

	a.press(tea.MouseButtonLeft, 0, 1)
	a.drag(40, 2)
	a.release(40, 2)

	if strings.Contains(clip.last(), "\x1b") {
		t.Errorf("copied text carries escape codes: %q", clip.last())
	}
}

func TestSelectionIsHighlightedWhileDragging(t *testing.T) {
	a := newTestApp(t, withClip(&fakeClip{}))
	a.resize(100, 30)
	a.View()

	a.press(tea.MouseButtonLeft, 2, 2)
	a.drag(20, 2)

	if !a.sel.active {
		t.Fatal("dragging did not start a selection")
	}
	// With the ascii colour profile there are no escapes to look for, so the
	// check is that rendering with a live selection still produces a frame of
	// the right shape rather than a mangled one.
	lines := strings.Split(a.View(), "\n")
	if len(lines) > 30 {
		t.Errorf("highlighting produced %d lines in a 30-row terminal", len(lines))
	}
}

// --- context menus ----------------------------------------------------------

func TestRightClickOpensTheChatMenu(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)

	a.press(tea.MouseButtonRight, 5, 2)
	if !a.menu.IsOpen() {
		t.Fatal("right-clicking a chat opened no menu")
	}
	labels := menuLabels(a.menu)
	for _, want := range []string{"Open", "Pin chat", "Archive chat", "Delete chat locally"} {
		if !containsLabel(labels, want) {
			t.Errorf("the chat menu is missing %q: %v", want, labels)
		}
	}
}

func TestRightClickOpensTheMessageMenu(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	l := a.layout()

	a.press(tea.MouseButtonRight, l.chatX+6, 4)
	if !a.menu.IsOpen() {
		t.Fatal("right-clicking a message opened no menu")
	}
	labels := menuLabels(a.menu)
	for _, want := range []string{"Reply", "Copy text", "Forward to…", "Message info", "Delete for me"} {
		if !containsLabel(labels, want) {
			t.Errorf("the message menu is missing %q: %v", want, labels)
		}
	}
}

func TestTheMenuReflectsTheChatsState(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)

	a.press(tea.MouseButtonRight, 5, 1)
	if !containsLabel(menuLabels(a.menu), "Pin chat") {
		t.Errorf("an unpinned chat should offer Pin: %v", menuLabels(a.menu))
	}
	a.menu.Close()

	// Pin it, then the menu must offer the opposite.
	a.store.setChat(chat(t, "Ana", "a@s.whatsapp.net", pinned()))
	a.list.Load(context.Background())
	a.press(tea.MouseButtonRight, 5, 1)
	if !containsLabel(menuLabels(a.menu), "Unpin chat") {
		t.Errorf("a pinned chat should offer Unpin: %v", menuLabels(a.menu))
	}
}

func TestMenuKeysNavigateAndClose(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	a.press(tea.MouseButtonRight, 5, 2)

	first := a.menu.Index()
	a.HandleKey(keys.Key{Rune: 'j'})
	if a.menu.Index() == first {
		t.Error("j did not move down the menu")
	}
	a.HandleKey(keys.Key{Special: keys.Esc})
	if a.menu.IsOpen() {
		t.Error("Esc did not close the menu")
	}
}

func TestMenuSkipsSeparators(t *testing.T) {
	m := &Menu{}
	m.Open("t", []MenuItem{
		{Label: "one", Run: func() error { return nil }},
		{Separator: true},
		{Label: "two", Run: func() error { return nil }},
	}, 0, 0, 40, 20)

	m.Move(1)
	if got := m.Index(); got != 2 {
		t.Errorf("Move landed on %d, want the row past the separator", got)
	}
}

func TestClickingOutsideDismissesTheMenu(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	a.press(tea.MouseButtonRight, 5, 2)

	x, y, w, _ := a.menu.Bounds()
	a.press(tea.MouseButtonLeft, x+w+3, y+10)
	if a.menu.IsOpen() {
		t.Error("a click outside the menu did not dismiss it")
	}
}

func TestMenuStaysOnScreenNearAnEdge(t *testing.T) {
	a := newTestApp(t)
	a.resize(60, 20)
	a.press(tea.MouseButtonRight, 58, 18)

	x, y, w, h := a.menu.Bounds()
	if x < 0 || x+w > 60 {
		t.Errorf("menu spans x %d..%d in a 60-column terminal", x, x+w)
	}
	if y < 0 || y+h > 20 {
		t.Errorf("menu spans y %d..%d in a 20-row terminal", y, y+h)
	}
}

func TestMenuIsCompositedOverTheFrame(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	a.press(tea.MouseButtonRight, 5, 2)

	view := a.View()
	if !strings.Contains(view, "Archive chat") {
		t.Errorf("the menu is not drawn:\n%s", view)
	}
	if n := len(strings.Split(view, "\n")); n > 30 {
		t.Errorf("the menu changed the frame height to %d rows", n)
	}
}

func TestMenuOpensFromTheKeyboardToo(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	a.feed(t, "<Space>.")
	if !a.menu.IsOpen() {
		t.Error("leader-. did not open the context menu")
	}
}

func menuLabels(m Menu) []string {
	var out []string
	for _, it := range m.Items() {
		if !it.Separator {
			out = append(out, it.Label)
		}
	}
	return out
}

func containsLabel(labels []string, want string) bool {
	for _, l := range labels {
		if l == want {
			return true
		}
	}
	return false
}

// --- the picker -------------------------------------------------------------

// clickPicker draws the picker first, because a click is only meaningful once
// the rows are on screen, and then runs whatever the click queued.
func (a *testApp) clickPicker(button tea.MouseButton, y int) {
	a.View()
	_, cmd := a.App.Update(tea.MouseMsg{Action: tea.MouseActionPress, Button: button, X: 4, Y: y})
	a.run(cmd)
}

func TestClickingAPickerRowChoosesIt(t *testing.T) {
	// Reacting and forwarding both go through the picker. A list you can see
	// but not click is a list that looks broken.
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.feed(t, "<Space>e")
	if !a.picker.IsOpen() {
		t.Fatal("the reaction picker did not open")
	}

	// Row 0 is the title, so the third item is on row 3.
	a.clickPicker(tea.MouseButtonLeft, 3)

	if a.picker.IsOpen() {
		t.Error("the picker stayed open after a click")
	}
	if !a.called("send react") {
		t.Error("nothing was reacted")
	}
}

func TestClickingChoosesTheRowUnderThePointer(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.feed(t, "<Space>e")
	a.View()

	a.App.Update(tea.MouseMsg{Action: tea.MouseActionMotion, X: 4, Y: 4})
	if got := a.picker.Index(); got != 3 {
		t.Errorf("the highlight is on %d, want the row under the pointer", got)
	}
}

func TestTheWheelScrollsThePicker(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.feed(t, "<Space>e")
	a.View()

	before := a.picker.Index()
	a.App.Update(tea.MouseMsg{Action: tea.MouseActionPress, Button: tea.MouseButtonWheelDown, X: 4, Y: 4})
	if a.picker.Index() == before {
		t.Error("the wheel did not move the highlight")
	}
}

func TestRightClickClosesThePicker(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.feed(t, "<Space>e")

	a.clickPicker(tea.MouseButtonRight, 3)
	if a.picker.IsOpen() {
		t.Error("right click did not dismiss the picker")
	}
	if a.called("send react") {
		t.Error("right click reacted")
	}
}

func TestClickingTheTitleRowChoosesNothing(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.feed(t, "<Space>e")

	a.clickPicker(tea.MouseButtonLeft, 0)
	if !a.picker.IsOpen() {
		t.Error("clicking the title closed the picker")
	}
}

func TestClickingAForwardTargetSendsIt(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.feed(t, "<Space>w")
	if !a.picker.IsOpen() {
		t.Fatal("the forward picker did not open")
	}

	a.clickPicker(tea.MouseButtonLeft, 1)
	if !a.called("messages forward") {
		t.Error("nothing was forwarded")
	}
}
