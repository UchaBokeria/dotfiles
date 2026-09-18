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

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/lock"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/wacli"
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
		a.run(a.HandleKey(k))
	}
}

// run executes queued work synchronously and applies its result, so a test
// sees the end state the event loop would produce. Operations that hand over
// the store lock - pinning, forwarding, deleting - are queued rather than run
// inline, so a test that skipped this would see nothing happen at all.
func (a *testApp) run(cmd tea.Cmd) {
	for n := 0; cmd != nil && n < 8; n++ {
		msg := cmd()
		if msg == nil {
			return
		}
		_, cmd = a.App.Update(msg)
	}
}

// command runs a : command and the work it queued.
func (a *testApp) command(t *testing.T, line string) error {
	t.Helper()
	err := a.RunCommand(line)
	a.run(a.takeCmd())
	return err
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

func (a *testApp) called(sub string) bool { return a.calls(sub) > 0 }

// calls is how many times the fake wacli was invoked with this substring in
// its arguments, which is what a test about a whole selection needs.
//
// Each invocation writes a start line and an end line, so only the start lines
// are counted.
func (a *testApp) calls(sub string) int {
	body, err := os.ReadFile(a.callLog)
	if err != nil {
		return 0
	}
	n := 0
	for _, line := range strings.Split(string(body), "\n") {
		if strings.HasPrefix(line, "start") && strings.Contains(line, sub) {
			n++
		}
	}
	return n
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

func TestTabMovesBetweenTheConversationAndTheInput(t *testing.T) {
	a := newTestApp(t)
	if a.Focus() != FocusList {
		t.Fatalf("focus starts at %v, want the chat list", a.Focus())
	}
	// From the list, Tab steps into the conversation rather than skipping to
	// the input box.
	a.feed(t, "<Tab>")
	if a.Focus() != FocusChat {
		t.Fatalf("after Tab focus = %v, want the conversation", a.Focus())
	}
	a.feed(t, "<Tab>")
	if a.Focus() != FocusComposer {
		t.Fatalf("after a second Tab focus = %v, want the input", a.Focus())
	}
	a.feed(t, "<Tab>")
	if a.Focus() != FocusChat {
		t.Fatalf("Tab must toggle back to the conversation, got %v", a.Focus())
	}
	// It never wanders back to the chat list; that is Shift-Tab's job.
	a.feed(t, "<Tab><Tab>")
	if a.Focus() == FocusList {
		t.Error("Tab reached the chat list; only Shift-Tab should")
	}
}

func TestShiftTabCyclesAllThreeSections(t *testing.T) {
	a := newTestApp(t)
	want := []Focus{FocusChat, FocusComposer, FocusList}
	for i, w := range want {
		a.feed(t, "<S-Tab>")
		if a.Focus() != w {
			t.Fatalf("Shift-Tab %d landed on %v, want %v", i+1, a.Focus(), w)
		}
	}
}

func TestFocusingTheComposerMakesTheDraftEditable(t *testing.T) {
	// Reaching the input with Tab should let vim motions edit the draft
	// without pressing i first.
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>")
	if a.InsertTarget() != TargetComposer {
		t.Errorf("target = %v, want the draft editable on focus", a.InsertTarget())
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
	if err := a.command(t, ":archive"); err != nil {
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
	if !strings.Contains(err.Error(), ":lock set") {
		t.Errorf("err = %v, want it to say how to set one from in here", err)
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
		t.Error("Tab must still move between panes when they are stacked")
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

// --- lock handovers ---------------------------------------------------------

func TestALockOperationDoesNotBlockTheInterface(t *testing.T) {
	// Pinning stops the sync process, waits for it to let go of the store,
	// runs the command and starts it again - seconds, during which this ran
	// on the interface's own goroutine. Every key press waited for it, and
	// pinning a chat looked broken for exactly that long.
	a := newTestApp(t)

	// The leader on its own schedules the key popup, so a command here is
	// expected; what must not happen is the operation itself.
	a.HandleKey(keys.MustParse("<Space>")[0])
	if a.called("chats pin") {
		t.Fatal("the prefix alone pinned something")
	}
	cmd := a.HandleKey(keys.MustParse("p")[0])
	if cmd == nil {
		t.Fatal("pinning did not queue anything; it must have run inline")
	}
	if a.called("chats pin") {
		t.Error("the command ran before the queued work was executed")
	}
	if !strings.Contains(a.Status(), "…") {
		t.Errorf("status = %q, want it to say the operation is under way", a.Status())
	}

	a.run(cmd)
	if !a.called("chats pin") {
		t.Error("the queued work never ran")
	}
	if !strings.Contains(a.Status(), "pinned") {
		t.Errorf("status = %q, want the result", a.Status())
	}
}

func TestALockOperationReportsItsFailure(t *testing.T) {
	a := newTestApp(t)
	os.WriteFile(filepath.Join(a.dir, "script.json"), []byte(
		`{"*": {"stdout": "{\"success\":false,\"data\":null,\"error\":\"store is locked\"}", "exit": 1}}`), 0o644)

	a.feed(t, "<Space>p")
	if !strings.Contains(a.Status(), "store is locked") {
		t.Errorf("status = %q, want the reason", a.Status())
	}
}

func TestForwardingRunsWhenAChatIsPicked(t *testing.T) {
	// The picker's own key handling used to return no command at all, so a
	// forward chosen from it queued work that nothing ever ran.
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.feed(t, "<Space>w")

	if !a.picker.IsOpen() {
		t.Fatal("the forward picker did not open")
	}
	a.feed(t, "<CR>")

	if !a.called("messages forward") {
		t.Error("nothing was forwarded")
	}
	if !strings.Contains(a.Status(), "forwarded to") {
		t.Errorf("status = %q", a.Status())
	}
}

func TestDeletingAMessageRunsInTheBackground(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.feed(t, "<Space>x")

	if !a.called("messages delete") {
		t.Error("the delete never ran")
	}
	if !strings.Contains(a.Status(), "deleted") {
		t.Errorf("status = %q", a.Status())
	}
}

func TestReactingShowsTheChipBeforeItIsSent(t *testing.T) {
	// The send takes a couple of seconds and the row it produces arrives
	// later still. A reaction that waited for either looked like it had done
	// nothing: the key registered, the screen did not change, and only
	// reopening the client showed it.
	a := newTestApp(t)
	a.feed(t, "<Tab>")

	m, ok := a.pane.Selected()
	if !ok {
		t.Fatal("no message selected")
	}
	a.feed(t, "<Space>e")
	if !a.picker.IsOpen() {
		t.Fatal("the reaction picker did not open")
	}

	// Accept the first emoji without running the queued send.
	if cmd := a.HandleKey(keys.MustParse("<CR>")[0]); cmd == nil {
		t.Fatal("reacting did not queue a send")
	} else {
		got, _ := a.pane.Selected()
		if len(got.Reactions) != 1 {
			t.Errorf("the chip was not drawn before the send: %+v", got.Reactions)
		}
		if a.called("send react") {
			t.Error("the send ran on the interface's goroutine")
		}
		a.run(cmd)
	}

	if !a.called("send react") {
		t.Error("the reaction was never sent")
	}
	got, _ := a.pane.Selected()
	if len(got.Reactions) != 1 {
		t.Errorf("reactions = %+v", got.Reactions)
	}
	if m.ID != got.ID {
		t.Errorf("the selection moved from %q to %q", m.ID, got.ID)
	}
}

func TestAFailedReactionIsTakenBackOff(t *testing.T) {
	// A chip left on screen after the send failed is a lie about what the
	// other person can see.
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	os.WriteFile(filepath.Join(a.dir, "script.json"), []byte(
		`{"*": {"stdout": "{\"success\":false,\"data\":null,\"error\":\"no network\"}", "exit": 1}}`), 0o644)

	a.feed(t, "<Space>e")
	a.feed(t, "<CR>")

	got, _ := a.pane.Selected()
	if len(got.Reactions) != 0 {
		t.Errorf("the chip stayed after a failure: %+v", got.Reactions)
	}
	if !strings.Contains(a.Status(), "no network") {
		t.Errorf("status = %q", a.Status())
	}
}

func TestDownloadingRunsInTheBackground(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")

	// The selected message needs an attachment for there to be anything to
	// fetch.
	sel, _ := a.pane.Selected()
	a.pane.SetMediaForTest(sel.ID, &domain.MediaRef{
		Type: "image", MimeType: "image/jpeg", Filename: "photo.jpg", Length: 1000,
	})

	// The leader alone only arms the key popup.
	a.HandleKey(keys.MustParse("<Space>")[0])
	if a.called("media download") {
		t.Fatal("the prefix alone downloaded something")
	}
	cmd := a.HandleKey(keys.MustParse("d")[0])
	if cmd == nil {
		t.Fatal("downloading did not queue anything")
	}
	if a.called("media download") {
		t.Error("the download ran on the interface's goroutine")
	}
	a.run(cmd)
}

func TestAChatActionFollowsWhatYouAreReading(t *testing.T) {
	// Moving the list cursor without pressing enter leaves the cursor and the
	// open conversation on different chats. Pinning while reading one and
	// having the other pinned is not what "pin" means.
	a := newTestApp(t)
	open, _ := a.list.Selected()

	a.feed(t, "<Tab>") // to the conversation
	a.list.Move(1)     // the cursor drifts, the conversation does not
	moved, _ := a.list.Selected()
	if moved.JID == open.JID {
		t.Fatal("the fixture has only one chat")
	}

	a.feed(t, "<Space>p")
	if !strings.Contains(a.lastCall(t), open.JID.String()) {
		t.Errorf("pinned %q, but %q is the chat on screen", a.lastCall(t), open.JID)
	}
}

func TestAChatActionUsesTheCursorWhenTheListHasFocus(t *testing.T) {
	a := newTestApp(t)
	a.list.Move(1)
	want, _ := a.list.Selected()

	a.feed(t, "<Space>p")
	if !strings.Contains(a.lastCall(t), want.JID.String()) {
		t.Errorf("pinned %q, want the chat under the cursor %q", a.lastCall(t), want.JID)
	}
}

// lastCall is the most recent command the fake wacli recorded.
func (a *testApp) lastCall(t *testing.T) string {
	t.Helper()
	body, err := os.ReadFile(a.callLog)
	if err != nil {
		return ""
	}
	lines := strings.Split(strings.TrimSpace(string(body)), "\n")
	return lines[len(lines)-1]
}

// --- attachments ------------------------------------------------------------

func TestAttachingAFileAndSendingIt(t *testing.T) {
	a := newTestApp(t)
	path := filepath.Join(a.dir, "photo.jpg")
	os.WriteFile(path, []byte("not really a jpeg"), 0o644)

	if err := a.command(t, ":attach "+path); err != nil {
		t.Fatal(err)
	}
	if got := a.composer.Attachments(); len(got) != 1 || got[0] != path {
		t.Fatalf("attachments = %v", got)
	}

	a.feed(t, "ia caption<CR>")

	log := a.lastCall(t)
	if !strings.Contains(log, "send file") {
		t.Errorf("call = %q", log)
	}
	if !strings.Contains(log, "--file "+path) {
		t.Errorf("the file was not named: %q", log)
	}
	if !strings.Contains(log, "--caption a caption") {
		t.Errorf("the draft did not become the caption: %q", log)
	}
	if got := a.composer.Attachments(); len(got) != 0 {
		t.Errorf("the attachment survived the send: %v", got)
	}
}

func TestAnAttachmentAloneIsAMessage(t *testing.T) {
	// A picture with no words is a message; the composer used to call an
	// empty draft nothing to send.
	a := newTestApp(t)
	path := filepath.Join(a.dir, "photo.jpg")
	os.WriteFile(path, []byte("x"), 0o644)

	a.command(t, ":attach "+path)
	if a.composer.Empty() {
		t.Fatal("a draft with an attachment reads as empty")
	}
	a.feed(t, "<Tab>")
	a.feed(t, "i<CR>")

	if !strings.Contains(a.lastCall(t), "send file") {
		t.Errorf("call = %q", a.lastCall(t))
	}
}

func TestOnlyTheFirstAttachmentCarriesTheCaption(t *testing.T) {
	// Repeating the caption under every picture is not what anybody means by
	// captioning a batch.
	a := newTestApp(t)
	for _, n := range []string{"a.jpg", "b.jpg"} {
		p := filepath.Join(a.dir, n)
		os.WriteFile(p, []byte("x"), 0o644)
		a.command(t, ":attach "+p)
	}
	a.feed(t, "ionce<CR>")

	// The fake logs a line when a call starts and another when it ends, so
	// count the starts.
	body, _ := os.ReadFile(a.callLog)
	sends := 0
	captions := 0
	for _, line := range strings.Split(string(body), "\n") {
		if !strings.HasPrefix(line, "start send file") {
			continue
		}
		sends++
		if strings.Contains(line, "--caption") {
			captions++
		}
	}
	if sends != 2 {
		t.Errorf("%d file sends, want 2", sends)
	}
	if captions != 1 {
		t.Errorf("%d of them carried the caption, want 1", captions)
	}
}

func TestAttachingSomethingThatIsNotThere(t *testing.T) {
	a := newTestApp(t)
	err := a.command(t, ":attach /no/such/file.png")
	if err == nil {
		t.Fatal("a missing file was accepted")
	}
	if len(a.composer.Attachments()) != 0 {
		t.Error("it was attached anyway")
	}
}

func TestDetachRemovesTheLastAttachment(t *testing.T) {
	a := newTestApp(t)
	path := filepath.Join(a.dir, "photo.jpg")
	os.WriteFile(path, []byte("x"), 0o644)

	a.command(t, ":attach "+path)
	if err := a.command(t, ":detach"); err != nil {
		t.Fatal(err)
	}
	if len(a.composer.Attachments()) != 0 {
		t.Error("the attachment stayed")
	}
	if err := a.command(t, ":detach"); err == nil {
		t.Error("detaching nothing should say so")
	}
}

func TestTheComposerNamesWhatIsAttached(t *testing.T) {
	// An attachment is invisible otherwise, and a picture pasted into the
	// wrong chat cannot be taken back.
	a := newTestApp(t)
	path := filepath.Join(a.dir, "holiday.jpg")
	os.WriteFile(path, []byte("x"), 0o644)
	a.command(t, ":attach "+path)

	if got := a.composer.View(true); !strings.Contains(got, "holiday.jpg") {
		t.Errorf("the composer does not name the attachment:\n%s", got)
	}
}

// --- the header and the link bar --------------------------------------------

func TestTheHeaderNamesTheOpenChat(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)

	got := a.headerLine()
	if !strings.Contains(got, "wa") {
		t.Errorf("no application name: %q", got)
	}
	name := a.list.DisplayName(a.pane.Chat())
	if name == "" {
		t.Fatal("the fixture opened no chat")
	}
	if !strings.Contains(got, name) {
		t.Errorf("header %q does not name the open chat %q", got, name)
	}
	if render.VisibleWidth(got) != 100 {
		t.Errorf("the header is %d columns, want 100", render.VisibleWidth(got))
	}
}

func TestTheHeaderSurvivesANarrowTerminal(t *testing.T) {
	a := newTestApp(t)
	for _, w := range []int{20, 40, 12} {
		a.resize(w, 20)
		if got := render.VisibleWidth(a.headerLine()); got > w {
			t.Errorf("width %d: the header is %d columns", w, got)
		}
	}
}

func TestTheLinkBarPreviewsTheSelectedMessagesLink(t *testing.T) {
	// A URL in a conversation is unreadable and unverifiable: the text says
	// one thing and the target may say another.
	a := newTestApp(t)
	a.resize(100, 30)
	a.feed(t, "<Tab>")

	sel, _ := a.pane.Selected()
	a.pane.SetTextForTest(sel.ID, "have a look at https://wacli.sh/docs/graphics ok")

	got := a.linkCrumbs()
	if !strings.Contains(got, "wacli.sh") {
		t.Errorf("no host in the link bar: %q", got)
	}
	if !strings.Contains(got, "graphics") {
		t.Errorf("no page in the link bar: %q", got)
	}
}

func TestTheLinkBarSaysHowManyLinks(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	a.feed(t, "<Tab>")

	sel, _ := a.pane.Selected()
	a.pane.SetTextForTest(sel.ID, "https://a.com and https://b.com")

	if got := a.linkCrumbs(); !strings.Contains(got, "2") {
		t.Errorf("the bar does not say there are two links: %q", got)
	}
}

func TestNoLinkBarWithoutALink(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	a.feed(t, "<Tab>")

	if got := a.linkCrumbs(); got != "" {
		t.Errorf("a message with no links drew a link bar: %q", got)
	}
}

// --- expired media ----------------------------------------------------------

func expiredMessage(t *testing.T, a *testApp) domain.Message {
	t.Helper()
	sel, _ := a.pane.Selected()
	a.pane.SetMediaForTest(sel.ID, &domain.MediaRef{
		Type: "document", Filename: "archive.zip", Length: 4096,
		UnavailableAt: time.Now().Add(-24 * time.Hour),
	})
	got, _ := a.pane.Selected()
	return got
}

func TestDownloadingExpiredMediaSaysWhatToDo(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	m := expiredMessage(t, a)

	err := a.downloadMedia(m)
	if err == nil {
		t.Fatal("a download that cannot work was attempted")
	}
	if !strings.Contains(err.Error(), ":retry") {
		t.Errorf("err = %v, want it to point at the way out", err)
	}
	if a.called("media download") {
		t.Error("wacli was asked for a file WhatsApp no longer has")
	}
}

func TestExpiredMediaIsNotFetchedInTheBackground(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	expiredMessage(t, a)

	a.View()
	time.Sleep(50 * time.Millisecond)
	if a.called("media download") {
		t.Error("the background fetcher asked for a file that cannot be fetched")
	}
}

func TestRetryAsksThePhoneToReupload(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, ":retry"); err != nil {
		t.Fatal(err)
	}
	log := a.lastCall(t)
	if !strings.Contains(log, "media retry") {
		t.Errorf("call = %q", log)
	}
	if !strings.Contains(log, "--chat") {
		t.Errorf("the retry was not limited to one chat: %q", log)
	}
}

// --- the key popup ----------------------------------------------------------

func TestPressingTheLeaderShowsWhatComesNext(t *testing.T) {
	a := newTestApp(t)
	a.wkDelay = 0 // no waiting in a test

	if a.wkPanel != "" {
		t.Fatal("the popup is up before any key was pressed")
	}
	a.feed(t, "<Space>")
	a.View()

	if a.wkPanel == "" {
		t.Fatal("the leader did not bring up the popup")
	}
	if !strings.Contains(render.StripEscapes(a.wkPanel), "»") {
		t.Errorf("the popup does not say where you are:\n%s", a.wkPanel)
	}
}

func TestBackspaceStepsBackOutOfAGroup(t *testing.T) {
	a := newTestApp(t)
	a.wkDelay = 0

	a.feed(t, "<Space>s")
	if got := len(a.engine.Pending()); got != 2 {
		t.Fatalf("pending is %d keys, want the leader and the group", got)
	}
	a.feed(t, "<BS>")
	if got := len(a.engine.Pending()); got != 1 {
		t.Errorf("pending is %d keys after backspace, want just the leader", got)
	}
	a.View()
	if a.wkPanel == "" {
		t.Error("the popup closed instead of stepping back a level")
	}
}

func TestEscapeClosesThePopup(t *testing.T) {
	a := newTestApp(t)
	a.wkDelay = 0

	a.feed(t, "<Space>")
	a.feed(t, "<Esc>")
	a.View()

	if len(a.engine.Pending()) != 0 {
		t.Error("the sequence survived Esc")
	}
	if a.wkPanel != "" {
		t.Error("the popup survived Esc")
	}
}

func TestThePopupClosesOnceTheSequenceResolves(t *testing.T) {
	a := newTestApp(t)
	a.wkDelay = 0

	a.feed(t, "<Space>")
	a.View()
	if a.wkPanel == "" {
		t.Fatal("the popup did not open")
	}

	a.feed(t, "?") // <leader>? is bound, and takes the whole sequence
	a.View()
	if a.wkPanel != "" {
		t.Error("the popup stayed up after the sequence resolved")
	}
}

func TestThePopupTakesRoomFromTheConversation(t *testing.T) {
	// It is drawn above the status line, so the panes have to be told.
	a := newTestApp(t)
	a.resize(100, 30)
	a.wkDelay = 0

	before := a.bodyHeight()
	a.feed(t, "<Space>")
	a.View()

	if a.bodyHeight() >= before {
		t.Errorf("body height is %d with the popup up, was %d", a.bodyHeight(), before)
	}
	if got := len(strings.Split(a.View(), "\n")); got != 30 {
		t.Errorf("the frame is %d rows, want 30", got)
	}
}

func TestThePopupDoesNotSurviveThePicker(t *testing.T) {
	// The picker takes the whole screen. A popup left in the field would come
	// back with it and sit on top of the list.
	a := newTestApp(t)
	a.wkDelay = 0

	a.feed(t, "<Space>")
	a.View()
	if a.wkPanel == "" {
		t.Fatal("the popup did not open")
	}

	a.feed(t, "<Space>") // <leader><leader> opens the chat picker
	if !a.picker.IsOpen() {
		t.Fatal("the picker did not open")
	}
	if got := a.View(); strings.Contains(render.StripEscapes(got), "<BS> back") {
		t.Error("the popup is drawn over the picker")
	}
	if a.wkPanel != "" {
		t.Error("the popup survived into the picker's frame")
	}
}

func TestBackspaceWalksBackEvenWithThePopupOff(t *testing.T) {
	// The popup shows the sequence; it does not own it. With the popup off,
	// backspace was falling through to the trie, where it is unbound, and
	// dropping the whole sequence silently.
	a := newTestApp(t)
	a.wkEnabled = false

	a.feed(t, "<Space>s")
	if got := len(a.engine.Pending()); got != 2 {
		t.Fatalf("pending is %d keys", got)
	}
	a.feed(t, "<BS>")
	if got := len(a.engine.Pending()); got != 1 {
		t.Errorf("pending is %d keys after backspace, want 1", got)
	}
	a.feed(t, "<Esc>")
	if got := len(a.engine.Pending()); got != 0 {
		t.Errorf("Esc left %d keys pending", got)
	}
}

func TestAnOggAttachmentIsSentAsAVoiceNote(t *testing.T) {
	// WhatsApp draws a voice note as a waveform and an audio file as a
	// document. Only ogg/opus can be the former, and sending a recording as
	// the latter is the wrong one every time.
	a := newTestApp(t)
	path := filepath.Join(a.dir, "recording.ogg")
	os.WriteFile(path, []byte("OggS"), 0o644)

	a.command(t, ":attach "+path)
	a.feed(t, "i<CR>")

	if got := a.lastCall(t); !strings.Contains(got, "--ptt") {
		t.Errorf("call = %q, want it sent as a voice note", got)
	}
}

func TestAnOrdinaryFileIsNotSentAsAVoiceNote(t *testing.T) {
	a := newTestApp(t)
	path := filepath.Join(a.dir, "notes.pdf")
	os.WriteFile(path, []byte("%PDF"), 0o644)

	a.command(t, ":attach "+path)
	a.feed(t, "i<CR>")

	if got := a.lastCall(t); strings.Contains(got, "--ptt") {
		t.Errorf("call = %q, a document was sent as a voice note", got)
	}
}

func TestTheHeaderCountsAGroupsMembers(t *testing.T) {
	a := newTestApp(t)
	a.resize(120, 30)

	c := a.pane.Chat()
	c.Kind = domain.KindGroup
	c.Members = 12
	a.pane.SetChatForTest(c)

	got := render.StripEscapes(a.headerLine())
	if !strings.Contains(got, "12 members") {
		t.Errorf("header = %q, want the member count", got)
	}
}

// --- commands, vim style -----------------------------------------------------

func TestWriteSendsTheDraft(t *testing.T) {
	// ":write" was listed by completion and rejected by the dispatcher.
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>ihello there<Esc>")

	if err := a.command(t, ":w"); err != nil {
		t.Fatal(err)
	}
	if got := a.lastCall(t); !strings.Contains(got, "send text") {
		t.Errorf("call = %q", got)
	}
	if a.composer.Text() != "" {
		t.Errorf("the draft survived the send: %q", a.composer.Text())
	}
}

func TestWriteQuitSendsThenQuits(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>ibye<Esc>")

	if err := a.command(t, ":x"); err != nil {
		t.Fatal(err)
	}
	if !a.quitting {
		t.Error(":x did not quit")
	}
}

func TestACommandCanBeAbbreviated(t *testing.T) {
	// vim resolves an abbreviation that names exactly one command. Being told
	// ":arch" is not a command, when ":archive" is the only thing it can mean,
	// sends people back to typing the whole word every time.
	a := newTestApp(t)
	if err := a.command(t, ":arch"); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(a.lastCall(t), "archive") {
		t.Errorf("call = %q", a.lastCall(t))
	}
}

func TestAnAmbiguousAbbreviationIsRefused(t *testing.T) {
	// ":un" could be unarchive, unmute, unpin, unread or unmap. Guessing one
	// would be worse than saying so.
	a := newTestApp(t)
	if err := a.command(t, ":un"); err == nil {
		t.Error("an ambiguous abbreviation was accepted")
	}
}

// --- Enter on a message ------------------------------------------------------

func TestEnterOnAMessageWithALinkOpensIt(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	sel, _ := a.pane.Selected()
	a.pane.SetTextForTest(sel.ID, "look at https://wacli.sh/docs now")

	// A browser that exists and records being run.
	a.cfg.UI.Browser = "true"
	if err := a.openSelectedMessage(); err != nil {
		t.Fatalf("Enter on a link: %v", err)
	}
}

func TestEnterOnAPlainMessageCopiesIt(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	sel, _ := a.pane.Selected()
	a.pane.SetTextForTest(sel.ID, "just some words")

	clip := &terminalClipboard{}
	a.clip = clip
	if err := a.openSelectedMessage(); err != nil {
		t.Fatal(err)
	}
	if clip.wrote != "just some words" {
		t.Errorf("the message was not copied; the clipboard holds %q", clip.wrote)
	}
}

func TestTheMessageMenuOffersMedia(t *testing.T) {
	// The keys have had download all along; the menu is where somebody who
	// does not know the keys goes looking.
	a := newTestApp(t)
	a.resize(100, 30)
	a.feed(t, "<Tab>")
	sel, _ := a.pane.Selected()
	a.pane.SetMediaForTest(sel.ID, &domain.MediaRef{
		Type: "document", Filename: "notes.pdf", Length: 2048,
	})

	a.openMessageMenu(40, 5)
	blank := make([]string, 30)
	for i := range blank {
		blank[i] = strings.Repeat(" ", 100)
	}
	got := render.StripEscapes(strings.Join(a.menu.Overlay(blank, a.styles), "\n"))
	if !strings.Contains(got, "Download") {
		t.Errorf("no download in the message menu:\n%s", got)
	}
}

// --- the keys belong to the focused section ----------------------------------

func TestMotionsInTheComposerDoNotMoveTheConversation(t *testing.T) {
	// Writing a message, pressing Esc, then j or k: the conversation used to
	// scroll while the cursor sat in the half-written message.
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>") // to the composer
	a.feed(t, "ifirst line<M-CR>second line<Esc>")
	if a.Focus() != FocusComposer {
		t.Fatalf("focus = %v", a.Focus())
	}

	before, _ := a.pane.Selected()
	for _, key := range []string{"j", "k", "gg", "G", "<C-d>", "<C-u>"} {
		a.feed(t, key)
	}
	after, _ := a.pane.Selected()
	if before.ID != after.ID {
		t.Errorf("the conversation moved from %q to %q while the composer had focus",
			before.ID, after.ID)
	}
}

func TestMotionsInTheComposerMoveTheCursor(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>")
	a.feed(t, "ifirst<M-CR>second<Esc>")

	buf := a.composer.Buffer()
	start := buf.Cursor()
	a.feed(t, "gg")
	if buf.Cursor() == start && start.Line != 0 {
		t.Error("gg did not move the cursor in the draft")
	}
	if got := buf.Cursor().Line; got != 0 {
		t.Errorf("gg left the cursor on line %d", got)
	}
	a.feed(t, "G")
	if got := buf.Cursor().Line; got != buf.Lines()-1 {
		t.Errorf("G left the cursor on line %d of %d", got, buf.Lines())
	}
}

func TestMotionsStillMoveTheConversationWhenItHasFocus(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>") // the conversation
	before, _ := a.pane.Selected()
	a.feed(t, "k")
	after, _ := a.pane.Selected()
	if before.ID == after.ID {
		t.Error("k did not move the conversation")
	}
}

// --- the file browser --------------------------------------------------------

func TestTheFileBrowserWalksAndAttaches(t *testing.T) {
	a := newTestApp(t)
	dir := t.TempDir()
	os.MkdirAll(filepath.Join(dir, "holiday"), 0o755)
	os.WriteFile(filepath.Join(dir, "holiday", "beach.jpg"), []byte("x"), 0o644)

	if err := a.openFileBrowser(dir); err != nil {
		t.Fatal(err)
	}
	if !a.picker.IsOpen() {
		t.Fatal("the browser did not open")
	}

	// Into the directory, then onto the file.
	a.picker.SetQuery("holiday")
	if err := a.picker.Accept(); err != nil {
		t.Fatal(err)
	}
	if !a.picker.IsOpen() {
		t.Fatal("choosing a directory closed the browser instead of opening it")
	}
	a.picker.SetQuery("beach")
	if err := a.picker.Accept(); err != nil {
		t.Fatal(err)
	}

	got := a.composer.Attachments()
	if len(got) != 1 || filepath.Base(got[0]) != "beach.jpg" {
		t.Errorf("attachments = %v", got)
	}
	if a.Focus() != FocusComposer {
		t.Errorf("focus = %v, want the composer after attaching", a.Focus())
	}
}

func TestWordMotionsWorkOnTheDraftAndNowhereElse(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>")
	a.feed(t, "ione two three<Esc>")
	buf := a.composer.Buffer()

	a.feed(t, "0")
	if got := buf.Cursor().Col; got != 0 {
		t.Fatalf("0 left the cursor at column %d", got)
	}
	a.feed(t, "w")
	if got := buf.Cursor().Col; got != len("one ") {
		t.Errorf("w left the cursor at column %d", got)
	}
	a.feed(t, "$")
	if got := buf.Cursor().Col; got != len("one two three")-1 {
		t.Errorf("$ left the cursor at column %d", got)
	}
	a.feed(t, "b")
	if got := buf.Cursor().Col; got != len("one two ") {
		t.Errorf("b left the cursor at column %d", got)
	}

	// The same keys with the conversation focused touch neither the draft nor
	// the conversation.
	a.feed(t, "<Tab>")
	before, _ := a.pane.Selected()
	col := buf.Cursor().Col
	for _, key := range []string{"w", "b", "0", "$", "e"} {
		a.feed(t, key)
	}
	if after, _ := a.pane.Selected(); after.ID != before.ID {
		t.Error("a draft motion moved the conversation")
	}
	if got := buf.Cursor().Col; got != col {
		t.Errorf("a draft motion moved the draft cursor from %d to %d while the conversation had focus", col, got)
	}
}

func TestOperatorsStillTakeAMotion(t *testing.T) {
	// w is bound in normal mode now; dw has to keep meaning delete-a-word.
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>")
	a.feed(t, "ione two<Esc>0")
	a.feed(t, "dw")
	if got := a.composer.Text(); got != "two" {
		t.Errorf("dw gave %q", got)
	}
}

func TestReadlineKeysInInsertMode(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab><Tab>")
	a.feed(t, "ihello world")

	a.feed(t, "<C-a>")
	if got := a.composer.Buffer().Cursor().Col; got != 0 {
		t.Errorf("<C-a> left the cursor at %d", got)
	}
	a.feed(t, "<C-e>")
	if got, want := a.composer.Buffer().Cursor().Col, len("hello world"); got != want {
		t.Errorf("<C-e> left the cursor at %d, want %d (after the last character)", got, want)
	}
	a.feed(t, "<M-b>")
	if got := a.composer.Buffer().Cursor().Col; got != len("hello ") {
		t.Errorf("<M-b> left the cursor at %d", got)
	}
	a.feed(t, "<C-k>")
	if got := a.composer.Text(); got != "hello " {
		t.Errorf("<C-k> gave %q", got)
	}
}

func TestClickingThePaperclipOpensTheBrowser(t *testing.T) {
	a := newTestApp(t)
	l := a.layout()
	row := l.bodyTop + l.paneRows + l.quickfixRows

	a.pressLeft(l.chatX, row)
	if !a.picker.IsOpen() {
		t.Error("clicking the paperclip did not open the file browser")
	}
}

func TestClickingPastThePaperclipJustFocusesTheInput(t *testing.T) {
	a := newTestApp(t)
	l := a.layout()
	row := l.bodyTop + l.paneRows + l.quickfixRows

	a.pressLeft(l.chatX+20, row)
	if a.picker.IsOpen() {
		t.Error("clicking in the middle of the input box opened the file browser")
	}
	if a.Focus() != FocusComposer {
		t.Errorf("focus = %v", a.Focus())
	}
}

func TestTheFileBrowserPutsHiddenEntriesLast(t *testing.T) {
	// A home directory holds forty dot-directories and none of them is the
	// picture you came to attach.
	a := newTestApp(t)
	dir := t.TempDir()
	for _, name := range []string{".config", "zoo", ".bashrc", "album.png"} {
		if strings.HasSuffix(name, "rc") || strings.HasSuffix(name, ".png") {
			os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o644)
			continue
		}
		os.MkdirAll(filepath.Join(dir, name), 0o755)
	}
	if err := a.openFileBrowser(dir); err != nil {
		t.Fatal(err)
	}

	var got []string
	for i := 0; i < a.picker.Len(); i++ {
		a.picker.Move(i - a.picker.Index())
		it, ok := a.picker.Selected()
		if !ok {
			t.Fatalf("row %d is missing", i)
		}
		got = append(got, it.Label)
	}
	want := []string{"../", "zoo/", ".config/", "album.png", ".bashrc"}
	if strings.Join(got, " ") != strings.Join(want, " ") {
		t.Errorf("listing = %v, want %v", got, want)
	}
}

// --- the alternate chat ------------------------------------------------------

func TestControlCaretGoesBackToTheLastChat(t *testing.T) {
	a := newTestApp(t)
	first := a.pane.Chat().JID

	a.feed(t, "j") // the list follows the cursor, opening the next chat
	second := a.pane.Chat().JID
	if second == first {
		t.Fatal("the second chat never opened")
	}

	a.feed(t, "<C-^>")
	if got := a.pane.Chat().JID; got != first {
		t.Errorf("ctrl-^ landed on %s, want %s", got, first)
	}
	a.feed(t, "<C-^>")
	if got := a.pane.Chat().JID; got != second {
		t.Errorf("ctrl-^ does not toggle: landed on %s, want %s", got, second)
	}
}

func TestTheAlternateChatSaysSoWhenThereIsNone(t *testing.T) {
	a := newTestApp(t)
	a.altChat = domain.JID{}
	a.feed(t, "<C-^>")
	if !strings.Contains(a.status, "no other chat") {
		t.Errorf("status = %q", a.status)
	}
}
