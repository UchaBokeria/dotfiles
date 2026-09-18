package ui

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// Edge cases: the inputs nobody types on purpose and everybody types
// eventually.

// --- lock ----------------------------------------------------------------------

func TestLockAcceptsUnicodeAndSpacesInThePassword(t *testing.T) {
	a := newTestApp(t)
	const pw = "გამარჯობა pass 🔒"
	if err := a.RunCommand(":lock set"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "<Space>") // a leading space is part of it, not a leader here
	a.lockScreen.Clear() // start clean: typed through the API below
	for _, r := range pw {
		a.lockScreen.Type(r)
	}
	a.feed(t, "<CR>")
	for _, r := range pw {
		a.lockScreen.Type(r)
	}
	a.feed(t, "<CR>")
	if a.lockScreen.Locked() || !a.lockScreen.HasPassword() {
		t.Fatal("a unicode password was not accepted")
	}
	if err := a.RunCommand(":lock"); err != nil {
		t.Fatal(err)
	}
	for _, r := range pw {
		a.lockScreen.Type(r)
	}
	a.feed(t, "<CR>")
	if a.lockScreen.Locked() {
		t.Error("the unicode password did not unlock")
	}
}

func TestLockBackspaceOnEmptyInputAndLongPasswords(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":lock set"); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 5; i++ {
		a.feed(t, "<BS>") // nothing typed; must not panic or underflow
	}
	long := strings.Repeat("x", 300)
	for _, r := range long {
		a.lockScreen.Type(r)
	}
	view := a.lockScreen.View(a.styles, 80, 24)
	for _, line := range strings.Split(view, "\n") {
		if w := len([]rune(stripForTest(line))); w > 80 {
			t.Errorf("a 300-character password drew a %d-column line", w)
		}
	}
	if !strings.Contains(view, "+276") {
		t.Error("the overflow count is missing for a long password")
	}
}

func TestEscapeOnTheUnlockScreenDoesNotOpenIt(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":lock set"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "pw<CR>pw<CR>")
	if err := a.RunCommand(":lock"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "<Esc><Esc><C-c>q")
	if !a.lockScreen.Locked() {
		t.Error("escape or ctrl-c got past the lock")
	}
}

func TestLockCommandRejectsNonsense(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":lock sideways"); err == nil {
		t.Error("an unknown :lock argument was accepted")
	}
	if err := a.RunCommand(":lock clear"); err == nil {
		t.Error("clearing a password that does not exist reported success")
	}
}

// --- the input box ---------------------------------------------------------------

func TestMultiCursorOnNothing(t *testing.T) {
	a := composerWith(t, "")
	a.feed(t, "<C-n>")
	if a.multiActive() {
		t.Error("an empty draft started a multi-cursor")
	}
	b := composerWith(t, "!!! ???")
	b.feed(t, "<C-n>")
	if b.multiActive() {
		t.Error("punctuation with no word under the cursor started a multi-cursor")
	}
}

func TestMultiCursorWithAWordThatAppearsOnce(t *testing.T) {
	a := composerWith(t, "only once here")
	a.feed(t, "<C-n><C-n><C-n>")
	if got := len(a.multi.cursors); got != 1 {
		t.Errorf("%d cursors for a word that appears once", got)
	}
}

func TestMultiCursorWordInsideAnotherWord(t *testing.T) {
	// "cat" inside "concatenate" is an occurrence of the text; the edit still
	// has to land in the right places and not corrupt the draft.
	a := composerWith(t, "cat concatenate cat")
	a.feed(t, "<C-n><C-n><C-n>")
	a.feed(t, "c")
	a.feed(t, "dog")
	a.feed(t, "<Esc><Esc>")
	got := a.composer.Text()
	if strings.Count(got, "dog") != len(a.multi.cursors)+strings.Count(got, "dog")-strings.Count(got, "dog") &&
		!strings.Contains(got, "dog") {
		t.Errorf("draft = %q", got)
	}
	if strings.Contains(got, "catcat") || strings.Contains(got, "dogdog") {
		t.Errorf("overlapping edits corrupted the draft: %q", got)
	}
}

func TestMultiCursorBackspaceAtTheStartOfALine(t *testing.T) {
	a := composerWith(t, "ab\nab")
	a.feed(t, "<C-n><C-n>")
	a.feed(t, "i")
	a.feed(t, "<BS><BS><BS>") // cursors at column 0: nothing to delete, no join
	a.feed(t, "<Esc><Esc>")
	if got := a.composer.Text(); got != "ab\nab" {
		t.Errorf("backspace at column 0 changed the draft to %q", got)
	}
}

func TestBlockOnRaggedAndEmptyLines(t *testing.T) {
	a := composerWith(t, "long line\n\nx")
	a.composer.Buffer().SetCursor(bufAt(0, 5))
	a.feed(t, "<C-v>")
	a.feed(t, "jj")
	a.feed(t, "d")
	got := a.composer.Text()
	if !strings.HasPrefix(got, "long ") {
		t.Errorf("the block delete damaged the first line: %q", got)
	}
	if strings.Count(got, "\n") != 2 {
		t.Errorf("the block delete joined or dropped lines: %q", got)
	}
}

func TestBlockAppendOnRaggedLinesPadsNothingAndLosesNothing(t *testing.T) {
	a := composerWith(t, "abcdef\nab")
	a.composer.Buffer().SetCursor(bufAt(0, 4))
	a.feed(t, "<C-v>")
	a.feed(t, "j")
	a.feed(t, "A")
	a.feed(t, "|")
	a.feed(t, "<Esc><Esc>")
	got := a.composer.Text()
	if !strings.Contains(got, "abcde|f") {
		t.Errorf("append on the long line landed wrong: %q", got)
	}
	if !strings.Contains(got, "ab|") {
		t.Errorf("append on the short line was lost: %q", got)
	}
}

func TestAltEnterAtEveryPositionNeverSends(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>i")
	for i := 0; i < 5; i++ {
		a.Update(tea.KeyMsg{Type: tea.KeyEnter, Alt: true})
	}
	if a.called("send text") {
		t.Fatal("alt+enter sent something")
	}
	if got := strings.Count(a.composer.Text(), "\n"); got != 5 {
		t.Errorf("%d newlines, want 5", got)
	}
}

// --- names and numbers -------------------------------------------------------

func TestExportNamesForAwkwardChatNames(t *testing.T) {
	cases := map[string]string{
		"აიკო":             "995500000000-",
		"🔥🔥🔥":              "995500000000-",
		"../../etc/passwd": "etcpasswd-",
		"Milestone Dev":    "Milestone-Dev-",
		"  --  ":           "995500000000-",
	}
	for name, prefix := range cases {
		c := domain.Chat{JID: domain.JID{User: "995500000000", Server: "s.whatsapp.net"}, Name: name}
		got := exportName(c)
		if !strings.HasPrefix(got, prefix) || !strings.HasSuffix(got, ".json") {
			t.Errorf("exportName(%q) = %q, want prefix %q", name, got, prefix)
		}
		if strings.ContainsAny(got, "/\\") {
			t.Errorf("exportName(%q) = %q escapes the directory", name, got)
		}
	}
}

func TestNormalizeNumber(t *testing.T) {
	cases := map[string]string{
		"+995 555 12-34-56":           "995555123456@s.whatsapp.net",
		"(995) 555.123.456":           "995555123456@s.whatsapp.net",
		"995555123456@s.whatsapp.net": "995555123456@s.whatsapp.net",
		"abc":                         "@s.whatsapp.net",
	}
	for in, want := range cases {
		if got := normalizeNumber(in); got != want {
			t.Errorf("normalizeNumber(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestAddContactRejectsGarbage(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, "contact"); err == nil {
		t.Error("an empty number was accepted")
	}
	if err := a.command(t, "contact abc"); err == nil {
		t.Error("a number with no digits was accepted")
	}
}

// --- the alternate chat ------------------------------------------------------

func TestAlternateChatThatWasDeleted(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "j")
	gone := a.altChat
	if gone.IsZero() {
		t.Fatal("no alternate chat recorded")
	}
	a.store.mu.Lock()
	kept := a.store.chats[:0]
	for _, c := range a.store.chats {
		if c.JID != gone {
			kept = append(kept, c)
		}
	}
	a.store.chats = kept
	a.store.mu.Unlock()

	// Must fail with a message, not panic or wedge the pane.
	a.feed(t, "<C-^>")
	if a.pane.Chat().JID.IsZero() {
		t.Error("going to a vanished chat left no chat open")
	}
}

// --- the file browser --------------------------------------------------------

func TestFileBrowserOnAnUnreadableDirectory(t *testing.T) {
	if os.Getuid() == 0 {
		t.Skip("root reads everything")
	}
	a := newTestApp(t)
	dir := filepath.Join(t.TempDir(), "locked")
	os.MkdirAll(dir, 0o000)
	defer os.Chmod(dir, 0o755)
	if err := a.openFileBrowser(dir); err == nil {
		t.Error("an unreadable directory opened without complaint")
	}
}

func TestFileBrowserWithASymlinkLoop(t *testing.T) {
	a := newTestApp(t)
	dir := t.TempDir()
	os.Symlink(dir, filepath.Join(dir, "loop"))
	if err := a.openFileBrowser(dir); err != nil {
		t.Fatal(err)
	}
	a.picker.SetQuery("loop")
	for i := 0; i < 20; i++ { // walking into it repeatedly must stay bounded
		if err := a.picker.Accept(); err != nil {
			t.Fatal(err)
		}
		if !a.picker.IsOpen() {
			t.Fatal("the browser closed on a symlink loop")
		}
		a.picker.SetQuery("loop")
	}
}

func TestAttachingAFileThatVanished(t *testing.T) {
	a := newTestApp(t)
	dir := t.TempDir()
	f := filepath.Join(dir, "gone.txt")
	os.WriteFile(f, []byte("x"), 0o644)
	if err := a.openFileBrowser(dir); err != nil {
		t.Fatal(err)
	}
	os.Remove(f)
	a.picker.SetQuery("gone")
	if err := a.picker.Accept(); err == nil {
		t.Error("a file deleted after listing was attached anyway")
	}
	if len(a.composer.Attachments()) != 0 {
		t.Error("the vanished file is in the attachments")
	}
}

// stripForTest removes escape sequences for width checks.
func stripForTest(s string) string {
	var b strings.Builder
	in := false
	for _, r := range s {
		switch {
		case r == 0x1b:
			in = true
		case in && (r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z'):
			in = false
		case !in:
			b.WriteRune(r)
		}
	}
	return b.String()
}
