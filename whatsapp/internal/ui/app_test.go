package ui

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/config"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/keys"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/lock"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/vim"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/wacli"
)

// testApp builds an application over a fake store and a fake wacli binary.
// Nothing here touches the real store, a real account, or the network.
type testApp struct {
	*App
	store   *fakeStore
	callLog string
	dir     string
}

func newTestApp(t *testing.T, opts ...func(*Deps)) *testApp {
	t.Helper()

	s := newFakeStore(
		chat(t, "Ana", "a@s.whatsapp.net"),
		chat(t, "Beka", "b@s.whatsapp.net"),
	)
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 12)
	s.messages["b@s.whatsapp.net"] = msgs(t, "b@s.whatsapp.net", 4)

	dir := t.TempDir()
	client, logPath := fakeWacli(t, dir)

	d := Deps{
		Cfg:           config.Default(),
		Styles:        plainStyles(t),
		Store:         s,
		Client:        client,
		LockPath:      filepath.Join(dir, "lock.json"),
		Log:           NewLog(),
		ConfigPath:    filepath.Join(dir, "config.toml"),
		OverridesPath: filepath.Join(dir, "overrides.toml"),
	}
	for _, o := range opts {
		o(&d)
	}

	a, err := NewApp(d)
	if err != nil {
		t.Fatalf("NewApp: %v", err)
	}
	a.resize(100, 30)

	ctx := context.Background()
	if err := a.list.Load(ctx); err != nil {
		t.Fatal(err)
	}
	if c, ok := a.list.Selected(); ok {
		if err := a.pane.Open(ctx, c); err != nil {
			t.Fatal(err)
		}
		a.composer.SwitchDraft(c.JID)
	}
	return &testApp{App: a, store: s, callLog: logPath, dir: dir}
}

// fakeWacli compiles the stand-in binary and returns a client aimed at it.
func fakeWacli(t *testing.T, dir string) (*wacli.Client, string) {
	t.Helper()
	bin := filepath.Join(dir, "wacli")

	cmd := exec.Command("go", "build", "-o", bin, "../wacli/testdata/fakewacli")
	cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("building the fake wacli: %v\n%s", err, out)
	}

	script := filepath.Join(dir, "script.json")
	os.WriteFile(script, []byte(
		`{"*": {"stdout": "{\"success\":true,\"data\":{\"id\":\"3EB0REAL\",\"sent\":true},\"error\":null}", "exit": 0}}`), 0o644)
	logPath := filepath.Join(dir, "calls.log")
	t.Setenv("WA_FAKE_SCRIPT", script)
	t.Setenv("WA_FAKE_LOG", logPath)

	return wacli.New(config.Wacli{Bin: bin, Timeout: config.Duration(10 * time.Second)}), logPath
}

// feed sends key notation into the application.
func (a *testApp) feed(t *testing.T, notation string) {
	t.Helper()
	for _, k := range keys.MustParse(notation) {
		if cmd := a.HandleKey(k); cmd != nil {
			// Run the queued work synchronously and apply its result, so a
			// test sees the same end state the event loop would produce.
			if msg := cmd(); msg != nil {
				a.App.Update(msg)
			}
		}
	}
}

// timeout fires the ambiguity timer, which is what a real session does after
// timeoutlen elapses with a prefix pending. <leader>i is both a binding and
// the start of <leader>in, so it only resolves this way.
func (a *testApp) timeout(t *testing.T) {
	t.Helper()
	for _, r := range a.engine.Timeout() {
		a.apply(r)
	}
}

func (a *testApp) called(sub string) bool {
	body, err := os.ReadFile(a.callLog)
	if err != nil {
		return false
	}
	return strings.Contains(string(body), sub)
}

// --- configuration and bindings ---------------------------------------------

func TestEveryDefaultBindingResolvesToARegisteredAction(t *testing.T) {
	// The shipped keymap must not name an action that does not exist: an
	// unknown name is a startup failure, so this would break wa outright.
	a := newTestApp(t)
	for mode, binds := range config.Default().Keys {
		if mode == "motion" || mode == "textobj" {
			continue
		}
		for notation, name := range binds {
			if !a.reg.Has(name) {
				t.Errorf("default binding %s %q -> %q is not a registered action",
					mode, notation, name)
			}
		}
	}
}

func TestDefaultConfigValidates(t *testing.T) {
	a := newTestApp(t)
	if err := config.Default().Validate(a.reg.Has); err != nil {
		t.Fatalf("the shipped configuration does not validate:\n%v", err)
	}
}

func TestUnknownActionInAKeymapFailsStartup(t *testing.T) {
	cfg := config.Default()
	cfg.Keys["normal"]["<C-y>"] = "nope.nope"

	_, err := NewApp(Deps{
		Cfg: cfg, Styles: plainStyles(t), Store: newFakeStore(), Log: NewLog(),
	})
	if err == nil {
		t.Fatal("a binding to an unknown action must stop startup")
	}
	if !strings.Contains(err.Error(), "nope.nope") {
		t.Errorf("err = %v, want it to name the offending action", err)
	}
}

// --- focus and modes --------------------------------------------------------

func TestTabTogglesFocus(t *testing.T) {
	a := newTestApp(t)
	if a.Focus() != FocusList {
		t.Fatalf("focus starts at %v, want the chat list", a.Focus())
	}
	a.feed(t, "<Tab>")
	if a.Focus() != FocusChat {
		t.Fatalf("after Tab focus = %v", a.Focus())
	}
	a.feed(t, "<Tab>")
	if a.Focus() != FocusList {
		t.Fatal("Tab must toggle back")
	}
}

func TestInsertGoesToSearchOnTheLeftAndTheComposerOnTheRight(t *testing.T) {
	a := newTestApp(t)

	a.feed(t, "i")
	if a.Mode() != vim.Insert || a.InsertTarget() != TargetSearch {
		t.Fatalf("i on the left = %v/%v, want insert into the search box",
			a.Mode(), a.InsertTarget())
	}

	a.feed(t, "<Esc><Esc><Tab>i")
	if a.Mode() != vim.Insert || a.InsertTarget() != TargetComposer {
		t.Fatalf("i on the right = %v/%v, want insert into the composer",
			a.Mode(), a.InsertTarget())
	}
}

func TestTypingOnTheLeftFiltersTheChatList(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "ibek")
	if got := a.list.Len(); got != 1 {
		t.Errorf("typing in the search box left %d chats, want 1: %v",
			got, chatNames(a.list.Rows()))
	}
}

func TestEscapeStepsOutOfTheComposerInTwoStages(t *testing.T) {
	// The first Esc leaves insert but keeps the draft editable with vim
	// motions; the second returns to the conversation.
	a := newTestApp(t)
	a.feed(t, "<Tab>ihello")

	a.feed(t, "<Esc>")
	if a.Mode() != vim.Normal {
		t.Fatalf("mode = %v, want Normal", a.Mode())
	}
	if a.InsertTarget() != TargetComposer {
		t.Fatalf("target = %v, want the draft to stay editable", a.InsertTarget())
	}

	a.feed(t, "<Esc>")
	if a.InsertTarget() != TargetNone || a.Focus() != FocusChat {
		t.Fatalf("second Esc = %v/%v, want back in the conversation",
			a.InsertTarget(), a.Focus())
	}
}

func TestVimEditingWorksInTheDraft(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>ithe quick brown<Esc>")
	a.feed(t, "0wdw")
	if got := a.composer.Text(); got != "the brown" {
		t.Errorf("draft = %q, want %q", got, "the brown")
	}
}

// --- sending ----------------------------------------------------------------

func TestSendDrawsAnOptimisticBubbleAndReconciles(t *testing.T) {
	a := newTestApp(t)
	before := a.pane.Count()

	a.feed(t, "<Tab>ihello there<CR>")

	if a.pane.Count() != before+1 {
		t.Fatalf("the message count went %d -> %d", before, a.pane.Count())
	}
	if !a.called("send text") {
		t.Error("no send reached wacli")
	}
	m, _ := a.pane.Selected()
	if m.ID != "3EB0REAL" || m.Local {
		t.Errorf("the optimistic bubble was not reconciled: %+v", m)
	}
	if !a.composer.Empty() {
		t.Errorf("the draft survived the send: %q", a.composer.Text())
	}
}

func TestSendOfAnEmptyDraftDoesNothing(t *testing.T) {
	a := newTestApp(t)
	before := a.pane.Count()
	a.feed(t, "<Tab>i<CR>")
	if a.pane.Count() != before {
		t.Error("an empty draft was sent")
	}
	if a.called("send text") {
		t.Error("wacli was invoked for an empty draft")
	}
}

func TestFailedSendKeepsTheText(t *testing.T) {
	a := newTestApp(t)
	os.WriteFile(filepath.Join(a.dir, "script.json"), []byte(
		`{"*": {"stdout": "{\"success\":false,\"data\":null,\"error\":\"network down\"}", "exit": 1}}`), 0o644)

	a.feed(t, "<Tab>ilost message<CR>")

	if got := a.composer.Text(); got != "lost message" {
		t.Errorf("draft = %q, want the text returned after a failure", got)
	}
	m, ok := a.pane.Selected()
	if !ok || m.Delivery != domain.Failed {
		t.Errorf("message = %+v, want it marked failed", m)
	}
	if !strings.Contains(a.Status(), "send failed") {
		t.Errorf("status = %q", a.Status())
	}
}

// --- undo -------------------------------------------------------------------

func TestUndoReversesAnArchive(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":archive"); err != nil {
		t.Fatal(err)
	}
	if !a.called("chats archive") {
		t.Fatal("archive was not sent")
	}
	a.feed(t, "u")
	if !a.called("chats unarchive") {
		t.Fatal("u did not reverse the archive")
	}
}

func TestUndoRefusesToUnsend(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>ihello<CR>")
	// Two escapes: the first leaves insert, the second leaves the draft, so u
	// is pressed in the message pane rather than in the composer.
	a.feed(t, "<Esc><Esc>u")

	if a.called("messages revoke") {
		t.Fatal("u revoked a sent message; that must only ever happen on an explicit :revoke")
	}
	if !strings.Contains(a.Status(), "revoke") {
		t.Errorf("status = %q, want it to point at :revoke", a.Status())
	}
}

func TestUndoWithNothingToUndo(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "u")
	if !strings.Contains(a.Status(), "nothing to undo") {
		t.Errorf("status = %q", a.Status())
	}
}

// --- search and quickfix ----------------------------------------------------

func TestSearchInAChatAndClearWithEscape(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>/message 3<CR>")

	if !a.SearchHighlighted() {
		t.Fatal("a search should highlight")
	}
	m, _ := a.pane.Selected()
	if m.Text != "message 3" {
		t.Errorf("search landed on %q", m.Text)
	}

	a.feed(t, "<Esc>")
	if a.SearchHighlighted() {
		t.Error("Esc in normal mode must clear the highlight")
	}
}

func TestSearchForAbsentTextReportsIt(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>/nothing here<CR>")
	if !strings.Contains(a.Status(), "not found") {
		t.Errorf("status = %q, want it to say the pattern was not found", a.Status())
	}
}

func TestGrepFillsTheQuickfixList(t *testing.T) {
	a := newTestApp(t)
	a.store.search = []domain.Message{
		{ChatJID: jid(t, "a@s.whatsapp.net"), ID: "M1", Text: "deploy the nuc", TS: time.Now()},
		{ChatJID: jid(t, "b@s.whatsapp.net"), ID: "M2", Text: "nuc is up", TS: time.Now()},
	}
	if err := a.RunCommand(":grep nuc"); err != nil {
		t.Fatal(err)
	}
	if n := a.QuickfixList().Len(); n != 2 {
		t.Fatalf("quickfix holds %d items, want 2", n)
	}
	if !strings.Contains(a.Status(), "2 results") {
		t.Errorf("status = %q", a.Status())
	}
}

func TestQuickfixNextJumpsToAResult(t *testing.T) {
	a := newTestApp(t)
	a.store.search = []domain.Message{
		{ChatJID: jid(t, "b@s.whatsapp.net"), ID: "M2", Text: "message 2", TS: time.Now()},
	}
	a.RunCommand(":grep message")

	a.feed(t, "<Space>in")
	got, ok := a.CurrentChat()
	if !ok || got.User != "b" {
		t.Errorf("leader-i-n did not jump to the result's chat, landed on %v", got)
	}
}

func TestQuickfixToggle(t *testing.T) {
	a := newTestApp(t)
	a.store.search = []domain.Message{
		{ChatJID: jid(t, "a@s.whatsapp.net"), ID: "M1", Text: "x", TS: time.Now()},
	}
	a.RunCommand(":grep x")

	before := a.showQF
	a.feed(t, "<Space>i")
	a.timeout(t)
	if a.showQF == before {
		t.Error("leader-i did not toggle the quickfix window")
	}
}

// --- : commands -------------------------------------------------------------

func TestSetChangesConfigLive(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":set ui.list_width=48"); err != nil {
		t.Fatal(err)
	}
	if a.Config().UI.ListWidth != 48 {
		t.Fatalf("list_width = %d, want 48", a.Config().UI.ListWidth)
	}
}

func TestSetRejectsAnUnknownOptionVisibly(t *testing.T) {
	a := newTestApp(t)
	err := a.RunCommand(":set ui.nonsense=1")
	if err == nil {
		t.Fatal("an unknown option must be rejected")
	}
	if !strings.Contains(err.Error(), "nonsense") {
		t.Errorf("err = %v, want it to name the option", err)
	}
}

func TestSetBangPersists(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":set! ui.list_width=52"); err != nil {
		t.Fatal(err)
	}
	body, err := os.ReadFile(a.deps.OverridesPath)
	if err != nil {
		t.Fatalf("nothing was written: %v", err)
	}
	if !strings.Contains(string(body), "list_width = 52") {
		t.Errorf("overrides file:\n%s", body)
	}
}

func TestMapRebindsAtRuntime(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":map n <C-p> picker.chats"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "<C-p>")
	if !a.PickerOpen() {
		t.Error("the runtime binding did not take effect")
	}
}

func TestMapRejectsAnUnknownAction(t *testing.T) {
	a := newTestApp(t)
	err := a.RunCommand(":map n <C-y> nope.nope")
	if err == nil || !strings.Contains(err.Error(), "nope.nope") {
		t.Errorf("err = %v, want it to name the action", err)
	}
}

func TestUnmapRemovesABinding(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":unmap n <Tab>"); err != nil {
		t.Fatal(err)
	}
	before := a.Focus()
	a.feed(t, "<Tab>")
	if a.Focus() != before {
		t.Error("the unmapped key still acted")
	}
}

func TestFilterCommand(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":filter unread"); err != nil {
		t.Fatal(err)
	}
	if a.list.Filter() != "unread" {
		t.Errorf("filter = %q", a.list.Filter())
	}
	if err := a.RunCommand(":filter nonsense"); err == nil {
		t.Error("an unknown filter must be rejected")
	}
}

func TestChatCommandOpensByName(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":chat Beka"); err != nil {
		t.Fatal(err)
	}
	got, _ := a.CurrentChat()
	if got.User != "b" {
		t.Errorf("opened %v, want Beka", got)
	}
}

func TestChatCommandWithNoMatch(t *testing.T) {
	a := newTestApp(t)
	if err := a.RunCommand(":chat nobody"); err == nil {
		t.Error("a name that matches nothing must be an error")
	}
}

func TestUnknownCommandNamesItself(t *testing.T) {
	a := newTestApp(t)
	err := a.RunCommand(":nonsense")
	if err == nil || !strings.Contains(err.Error(), "nonsense") {
		t.Errorf("err = %v", err)
	}
}

func TestRevokeRefusesSomeoneElsesMessage(t *testing.T) {
	a := newTestApp(t)
	err := a.RunCommand(":revoke")
	if err == nil || !strings.Contains(err.Error(), "your own") {
		t.Errorf("err = %v, want a refusal to revoke another person's message", err)
	}
}

func TestCompletionOfCommandNames(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, ":se")
	a.complete(1)
	if !strings.HasPrefix(a.cmdline, "se") {
		t.Errorf("cmdline = %q", a.cmdline)
	}
	if len(a.completions) == 0 {
		t.Error("no completions were offered")
	}
}

// --- live events ------------------------------------------------------------

func TestLiveEventRefreshesTheNamedChat(t *testing.T) {
	a := newTestApp(t)
	a.Emit(domain.Event{Kind: domain.EventMessage, Chat: jid(t, "b@s.whatsapp.net")})

	if a.store.loadsOf("b@s.whatsapp.net") == 0 {
		t.Error("the event's chat was not re-read")
	}
}

func TestLiveEventDoesNotDisturbAnUnrelatedConversation(t *testing.T) {
	a := newTestApp(t)
	open, _ := a.CurrentChat()

	a.Emit(domain.Event{Kind: domain.EventMessage, Chat: jid(t, "b@s.whatsapp.net")})

	after, _ := a.CurrentChat()
	if after != open {
		t.Errorf("an event in another chat moved the cursor from %v to %v", open, after)
	}
}

func TestReceiptAdvancesDeliveryWithoutAReload(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>ihi<CR>")

	a.Emit(domain.Event{
		Kind: domain.EventReceipt, Chat: a.pane.Chat().JID, MessageID: "3EB0REAL",
	})
	m, _ := a.pane.Selected()
	if m.Delivery != domain.Delivered {
		t.Errorf("delivery = %v, want Delivered", m.Delivery)
	}
}

// --- degradations -----------------------------------------------------------

func TestDegradationIsAnnouncedOnce(t *testing.T) {
	a := newTestApp(t)
	msg := "schema version 31 is newer than this build understands"

	a.Announce("schema", msg)
	a.Announce("schema", msg)
	a.Announce("schema", msg)

	if !strings.Contains(a.Status(), "schema") {
		t.Errorf("the degradation is not visible: %q", a.Status())
	}
	if n := strings.Count(a.LogText(), "schema version 31"); n != 1 {
		t.Errorf("the degradation was logged %d times, want exactly 1", n)
	}
}

func TestErrorsReachTheLog(t *testing.T) {
	a := newTestApp(t)
	a.RunCommand(":set ui.nonsense=1")
	a.feed(t, ":set ui.nonsense=1<CR>")
	if !strings.Contains(a.LogText(), "nonsense") {
		t.Errorf("the error never reached the log:\n%s", a.LogText())
	}
}

// --- lock -------------------------------------------------------------------

func TestLockScreenBlocksUntilTheRightPassword(t *testing.T) {
	dir := t.TempDir()
	lockPath := filepath.Join(dir, "lock.json")
	if err := lock.Set(lockPath, "hunter2"); err != nil {
		t.Fatal(err)
	}

	a := newTestApp(t, func(d *Deps) {
		d.LockPath = lockPath
		d.Cfg.Lock.Enabled = true
	})
	if !a.Locked() {
		t.Fatal("the application should start locked")
	}
	if strings.Contains(a.View(), "Ana") {
		t.Fatal("chat data is visible behind the lock screen")
	}

	a.feed(t, "wrong<CR>")
	if !a.Locked() {
		t.Fatal("a wrong password unlocked it")
	}

	a.feed(t, "hunter2<CR>")
	if a.Locked() {
		t.Fatal("the right password did not unlock it")
	}
}

func TestLockCommandWithNoPasswordSet(t *testing.T) {
	a := newTestApp(t)
	err := a.RunCommand(":lock")
	if err == nil {
		t.Fatal("locking with no password set would be a door with no key")
	}
	if !strings.Contains(err.Error(), "wa lock set") {
		t.Errorf("err = %v, want it to say how to set one", err)
	}
}

// --- rendering --------------------------------------------------------------

func TestViewFitsTheTerminal(t *testing.T) {
	a := newTestApp(t)
	for _, size := range [][2]int{{100, 30}, {80, 24}, {60, 20}, {40, 15}} {
		a.resize(size[0], size[1])
		lines := strings.Split(a.View(), "\n")
		if len(lines) > size[1] {
			t.Errorf("%dx%d: rendered %d lines", size[0], size[1], len(lines))
		}
	}
}

func TestNarrowTerminalCollapsesToOnePane(t *testing.T) {
	a := newTestApp(t)
	a.resize(50, 20) // below the default min_width of 80

	if !a.narrow() {
		t.Fatal("a 50-column terminal should be narrow")
	}
	view := a.View()
	if strings.Contains(view, "│") {
		t.Error("a narrow terminal should not draw the pane divider")
	}
	a.feed(t, "<Tab>")
	if a.Focus() != FocusChat {
		t.Error("Tab must still switch panes when they are stacked")
	}
}

func TestStatusLineShowsTheMode(t *testing.T) {
	a := newTestApp(t)
	if !strings.Contains(a.View(), "NORMAL") {
		t.Error("the status line does not show the mode")
	}
	a.feed(t, "<Tab>i")
	if !strings.Contains(a.View(), "INSERT") {
		t.Error("the status line did not follow the mode into insert")
	}
}

func TestMacroRecordingIsVisible(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "qq")
	if !strings.Contains(a.View(), "REC") {
		t.Error("a recording macro should be visible in the status line")
	}
}

// --- key translation --------------------------------------------------------

func TestKeyMsgWithSeveralRunesIsNotTruncated(t *testing.T) {
	// The terminal delivers whatever arrived in one read, so typing quickly
	// or pasting produces a single KeyMsg holding every character. Handling
	// only the first rune silently swallowed the rest: ":filter all" became
	// ":fil a", and ZZ became a single Z that never quit.
	got := translateKeys(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("lter")})
	if len(got) != 4 {
		t.Fatalf("translateKeys returned %d keys for 4 runes: %v", len(got), got)
	}
	for i, want := range []rune("lter") {
		if got[i].Rune != want {
			t.Errorf("key %d = %q, want %q", i, got[i].Rune, want)
		}
	}
}

func TestBatchedRunesReachTheCommandLine(t *testing.T) {
	a := newTestApp(t)
	a.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(":")})
	a.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("filter unread")})

	if a.cmdline != "filter unread" {
		t.Fatalf("cmdline = %q, want the whole command", a.cmdline)
	}
	a.Update(tea.KeyMsg{Type: tea.KeyEnter})
	if a.list.Filter() != "unread" {
		t.Errorf("filter = %q, want unread", a.list.Filter())
	}
}

func TestBatchedRunesCompleteAMultiKeyBinding(t *testing.T) {
	// ZZ arriving as one event must still quit.
	a := newTestApp(t)
	a.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("ZZ")})
	if !a.quitting {
		t.Error("ZZ delivered in a single event did not quit")
	}
}

func TestBatchedRunesTypeIntoTheComposer(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>i")
	a.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("hello there")})
	if got := a.composer.Text(); got != "hello there" {
		t.Errorf("draft = %q, want the whole pasted string", got)
	}
}
