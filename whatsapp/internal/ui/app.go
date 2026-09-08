package ui

import (
	"context"
	"fmt"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/action"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/config"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/daemon"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/keys"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/live"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/lock"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/store"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/theme"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/ui/render"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/vim"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/wacli"
)

// Focus is which pane the keyboard is aimed at.
type Focus int

const (
	FocusList Focus = iota
	FocusChat
	FocusComposer
)

func (f Focus) String() string {
	switch f {
	case FocusList:
		return "list"
	case FocusChat:
		return "chat"
	default:
		return "composer"
	}
}

// EditTarget is which text buffer insert-mode keys reach.
type EditTarget int

const (
	TargetNone EditTarget = iota
	TargetSearch
	TargetComposer
	TargetCmdLine
	TargetFind
)

// Deps are what the application needs to run.
type Deps struct {
	Cfg      config.Config
	Styles   theme.Styles
	Store    store.Reader
	Client   *wacli.Client
	Daemon   *daemon.Daemon
	Live     live.Source
	LockPath string
	Log      *Log
	// ConfigPath and OverridesPath back :set! and :reload.
	ConfigPath    string
	OverridesPath string
}

// reversible is one entry on the undo ring: an action and the call that
// reverses it.
type reversible struct {
	what    string
	inverse func(context.Context) error
}

// App is the Bubble Tea root model.
type App struct {
	deps   Deps
	cfg    config.Config
	styles theme.Styles
	log    *Log

	reg    *action.Registry
	keymap *vim.Keymap
	engine *vim.Engine

	list     *ChatList
	pane     *MessagePane
	composer *Composer
	cache    *render.Cache

	focus      Focus
	editTarget EditTarget

	// searchBuf is the chat-list search box: a real buffer, so the same vim
	// editing works there as in the composer.
	searchBuf  *vim.Buffer
	searchUndo *vim.Undo

	// cmdline is the : prompt, and findLine the / prompt.
	cmdline     string
	cmdHistory  *vim.History
	findLine    string
	findForward bool
	findHistory *vim.History
	completions []string
	completeAt  int

	jumps  Jumplist
	qf     Quickfix
	picker Picker
	showQF bool

	lockScreen *LockScreen
	idle       *lock.Idle

	undoRing []reversible

	width  int
	height int

	status    string
	statusErr bool
	quitting  bool
	showLog   bool
	showHelp  bool

	marks map[rune]Jump

	// pending carries asynchronous work an action queued, collected by
	// takeCmd once the action returns.
	pending tea.Cmd
}

// Msg types the application sends itself.
type (
	eventMsg    struct{ ev domain.Event }
	sentMsg     struct{ localID, realID string }
	sendFailMsg struct {
		localID string
		text    string
		err     error
	}
	statusMsg struct {
		text  string
		isErr bool
	}
	reloadedMsg struct {
		cfg   config.Config
		warns []config.Warning
		err   error
	}
	timeoutMsg struct{}
	refreshMsg struct{}
	quitMsg    struct{}
)

// NewApp wires everything together.
func NewApp(d Deps) (*App, error) {
	if d.Log == nil {
		d.Log = NewLog()
	}
	a := &App{
		deps:        d,
		cfg:         d.Cfg,
		styles:      d.Styles,
		log:         d.Log,
		cache:       render.NewCache(1024),
		cmdHistory:  vim.NewHistory(200),
		findHistory: vim.NewHistory(200),
		marks:       map[rune]Jump{},
		width:       80,
		height:      24,
	}

	a.searchBuf = vim.NewBuffer()
	a.searchUndo = vim.NewUndo(a.searchBuf)

	a.list = NewChatList(d.Store, d.Styles, a.listWidth(), a.bodyHeight())
	a.pane = NewMessagePane(d.Store, a.cache, d.Styles, a.chatWidth(), a.bodyHeight())
	a.composer = NewComposer(d.Styles, a.chatWidth())

	a.reg = action.NewRegistry()
	registerAll(a.reg, a)

	if err := a.applyConfig(d.Cfg); err != nil {
		return nil, err
	}

	a.lockScreen = NewLockScreen(d.LockPath, d.Cfg.Lock.Enabled)
	if d.Cfg.Lock.Enabled && d.Cfg.Lock.IdleTimeout > 0 {
		a.idle = lock.NewIdle(d.Cfg.Lock.IdleTimeout.D(), func() { a.lockScreen.Lock() })
	}
	return a, nil
}

// applyConfig rebuilds everything a setting can change. It is called at
// startup and again on every hot reload, so a reload is not a special case
// with its own half-applied behaviour.
func (a *App) applyConfig(cfg config.Config) error {
	if err := cfg.Validate(a.reg.Has); err != nil {
		return err
	}
	a.cfg = cfg

	km, err := buildKeymap(cfg)
	if err != nil {
		return err
	}
	a.keymap = km

	mode := vim.Normal
	if a.engine != nil {
		mode = a.engine.Mode()
	}
	a.engine = vim.NewEngine(km, vim.NewRegisters(nil, cfg.UI.Clipboard == "unnamedplus"),
		vim.Options{
			TimeoutLen:  time.Duration(cfg.UI.TimeoutLen) * time.Millisecond,
			TextObjects: textObjectTable(cfg),
		})
	a.engine.SetMode(mode)

	a.list.SetScrolloff(cfg.UI.Scrolloff)
	a.pane.Configure(cfg.UI.Scrolloff, cfg.UI.Timestamp, cfg.UI.DaySeparator, cfg.UI.BubbleMaxPercent)
	a.resize(a.width, a.height)
	return nil
}

// buildKeymap turns the configured tables into one trie per mode.
func buildKeymap(cfg config.Config) (*vim.Keymap, error) {
	km := vim.NewKeymap()
	leader := cfg.Leader()

	for name, binds := range cfg.Keys {
		if name == "textobj" {
			continue
		}
		for notation, target := range binds {
			seq, err := keys.Parse(notation, leader)
			if err != nil {
				return nil, fmt.Errorf("keys.%s: %q: %w", name, notation, err)
			}
			if name == "motion" {
				// Motions are available bare in normal and visual mode, and
				// after an operator.
				for _, m := range []vim.Mode{vim.Normal, vim.Visual, vim.VisualLine, vim.OpPending} {
					if err := km.Bind(m, seq, vim.Target{Kind: vim.TargetMotion, Name: target}); err != nil {
						return nil, err
					}
				}
				continue
			}
			mode, ok := vim.ModeName(name)
			if !ok {
				return nil, fmt.Errorf("keys.%s is not a mode", name)
			}
			if err := km.Bind(mode, seq, vim.Target{Kind: vim.TargetAction, Name: target}); err != nil {
				return nil, err
			}
		}
	}

	// Action bindings are applied last so that a key present in both tables -
	// j is nav.down and the "down" motion - resolves to the action, which is
	// what routes it to whichever pane has focus.
	for _, name := range []string{"normal", "visual"} {
		mode, _ := vim.ModeName(name)
		for notation, target := range cfg.Keys[name] {
			seq, err := keys.Parse(notation, leader)
			if err != nil {
				return nil, err
			}
			if err := km.Bind(mode, seq, vim.Target{Kind: vim.TargetAction, Name: target}); err != nil {
				return nil, err
			}
		}
	}
	return km, nil
}

func textObjectTable(cfg config.Config) map[rune]string {
	out := map[rune]string{}
	for notation, object := range cfg.Keys["textobj"] {
		seq, err := keys.Parse(notation, cfg.Leader())
		if err != nil || len(seq) != 1 {
			continue
		}
		if r, ok := seq[0].Printable(); ok {
			out[r] = object
		}
	}
	return out
}

// --- bubbletea -------------------------------------------------------------

// Init starts the live-event pump.
func (a *App) Init() tea.Cmd {
	return tea.Batch(a.loadInitial(), a.waitForEvent())
}

func (a *App) loadInitial() tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := a.list.Load(ctx); err != nil {
			return statusMsg{text: err.Error(), isErr: true}
		}
		if c, ok := a.list.Selected(); ok {
			if err := a.pane.Open(ctx, c); err != nil {
				return statusMsg{text: err.Error(), isErr: true}
			}
			a.composer.SwitchDraft(c.JID)
		}
		return refreshMsg{}
	}
}

func (a *App) waitForEvent() tea.Cmd {
	if a.deps.Live == nil {
		return nil
	}
	return func() tea.Msg {
		ev, ok := <-a.deps.Live.Events()
		if !ok {
			return nil
		}
		return eventMsg{ev: ev}
	}
}

// Update handles one message.
func (a *App) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch m := msg.(type) {
	case tea.WindowSizeMsg:
		a.resize(m.Width, m.Height)
		return a, nil

	case tea.KeyMsg:
		if a.idle != nil {
			a.idle.Touch()
		}
		// One KeyMsg can carry several runes: the terminal delivers whatever
		// arrived in a single read, so fast typing and pasted text arrive
		// batched. Handling only the first rune silently swallows the rest.
		var cmds []tea.Cmd
		for _, k := range translateKeys(m) {
			if cmd := a.HandleKey(k); cmd != nil {
				cmds = append(cmds, cmd)
			}
		}
		if a.quitting {
			return a, tea.Quit
		}
		if len(cmds) == 0 {
			return a, nil
		}
		return a, tea.Batch(cmds...)

	case eventMsg:
		a.applyEvent(m.ev)
		return a, a.waitForEvent()

	case sentMsg:
		a.pane.Reconcile(m.localID, m.realID)
		return a, nil

	case sendFailMsg:
		a.pane.FailOptimistic(m.localID, m.err)
		a.composer.Restore(m.text)
		a.setError(fmt.Sprintf("send failed: %v", m.err))
		return a, nil

	case statusMsg:
		if m.isErr {
			a.setError(m.text)
		} else {
			a.setStatus(m.text)
		}
		return a, nil

	case reloadedMsg:
		a.applyReload(m)
		return a, nil

	case refreshMsg:
		return a, nil

	case timeoutMsg:
		a.runResolved(a.engine.Timeout())
		return a, nil

	case quitMsg:
		a.quitting = true
		return a, tea.Quit
	}
	return a, nil
}

// translateKeys converts a Bubble Tea key event into engine keys.
//
// It returns a slice because a single event can carry several runes. Bubble
// Tea hands over whatever the terminal delivered in one read, so typing
// quickly - or pasting - arrives as one message holding every character.
func translateKeys(m tea.KeyMsg) []keys.Key {
	if m.Type == tea.KeyRunes {
		out := make([]keys.Key, 0, len(m.Runes))
		for _, r := range m.Runes {
			k := keys.Key{Rune: r}
			if m.Alt {
				k.Mods |= keys.Alt
			}
			out = append(out, k)
		}
		return out
	}
	if k := translateSpecial(m); k != (keys.Key{}) {
		return []keys.Key{k}
	}
	return nil
}

// translateSpecial maps the non-rune keys.
func translateSpecial(m tea.KeyMsg) keys.Key {
	switch m.Type {
	case tea.KeySpace:
		return keys.Key{Special: keys.Space}
	case tea.KeyEnter:
		return keys.Key{Special: keys.CR}
	case tea.KeyEscape:
		return keys.Key{Special: keys.Esc}
	case tea.KeyTab:
		return keys.Key{Special: keys.Tab}
	case tea.KeyShiftTab:
		return keys.Key{Mods: keys.Shift, Special: keys.Tab}
	case tea.KeyBackspace:
		return keys.Key{Special: keys.BS}
	case tea.KeyDelete:
		return keys.Key{Special: keys.Del}
	case tea.KeyUp:
		return keys.Key{Special: keys.Up}
	case tea.KeyDown:
		return keys.Key{Special: keys.Down}
	case tea.KeyLeft:
		return keys.Key{Special: keys.Left}
	case tea.KeyRight:
		return keys.Key{Special: keys.Right}
	case tea.KeyHome:
		return keys.Key{Special: keys.Home}
	case tea.KeyEnd:
		return keys.Key{Special: keys.End}
	case tea.KeyPgUp:
		return keys.Key{Special: keys.PgUp}
	case tea.KeyPgDown:
		return keys.Key{Special: keys.PgDn}
	}

	// Control keys arrive as their own types; map by name.
	name := m.String()
	if strings.HasPrefix(name, "ctrl+") {
		r := strings.TrimPrefix(name, "ctrl+")
		if len(r) == 1 {
			return keys.Key{Mods: keys.Ctrl, Rune: rune(r[0])}
		}
	}
	if strings.HasPrefix(name, "alt+") {
		r := strings.TrimPrefix(name, "alt+")
		if len(r) == 1 {
			return keys.Key{Mods: keys.Alt, Rune: rune(r[0])}
		}
	}
	return keys.Key{}
}

// HandleKey routes one keystroke. It is exported so tests can drive the
// application without a terminal.
func (a *App) HandleKey(k keys.Key) tea.Cmd {
	if a.lockScreen != nil && a.lockScreen.Locked() {
		return a.handleLockKey(k)
	}
	if a.picker.IsOpen() {
		return a.handlePickerKey(k)
	}
	return a.runResolved(a.engine.Feed(k))
}

func (a *App) handleLockKey(k keys.Key) tea.Cmd {
	switch {
	case k.Special == keys.CR:
		ok, err := a.lockScreen.Submit()
		if err != nil {
			a.setError(err.Error())
		} else if !ok {
			a.setError("wrong password")
		} else {
			a.setStatus("unlocked")
		}
	case k.Special == keys.BS:
		a.lockScreen.Backspace()
	case k.Mods&keys.Ctrl != 0 && k.Rune == 'u':
		a.lockScreen.Clear()
	default:
		if r, ok := k.Printable(); ok {
			a.lockScreen.Type(r)
		}
	}
	return nil
}

func (a *App) handlePickerKey(k keys.Key) tea.Cmd {
	switch {
	case k.Special == keys.Esc:
		a.picker.Close()
	case k.Special == keys.CR:
		if err := a.picker.Accept(); err != nil {
			a.setError(err.Error())
		}
	case k.Special == keys.BS:
		a.picker.Backspace()
	case k.Special == keys.Up, k.Mods&keys.Ctrl != 0 && k.Rune == 'p':
		a.picker.Move(-1)
	case k.Special == keys.Down, k.Mods&keys.Ctrl != 0 && k.Rune == 'n':
		a.picker.Move(1)
	default:
		if r, ok := k.Printable(); ok {
			a.picker.AppendRune(r)
		}
	}
	return nil
}

// runResolved applies each command the engine produced.
func (a *App) runResolved(rs []vim.Resolved) tea.Cmd {
	var cmds []tea.Cmd
	for _, r := range rs {
		if cmd := a.apply(r); cmd != nil {
			cmds = append(cmds, cmd)
		}
	}
	if len(cmds) == 0 {
		return nil
	}
	return tea.Batch(cmds...)
}

func (a *App) apply(r vim.Resolved) tea.Cmd {
	switch {
	case r.Literal != nil:
		a.insertLiteral(*r.Literal)
		return nil

	case r.IsOperator():
		a.applyOperator(r)
		return nil

	case r.Motion != "":
		a.applyMotion(r)
		return nil

	case r.Action != "":
		if err := a.reg.Run(r.Action, action.Context{
			Count: r.Count, Register: r.Register, Arg: r.Arg,
		}); err != nil {
			a.setError(err.Error())
		}
		return a.takeCmd()
	}
	return nil
}

// pendingCmd lets an action queue asynchronous work without knowing about
// Bubble Tea's command type at every call site.
func (a *App) takeCmd() tea.Cmd {
	cmd := a.pending
	a.pending = nil
	return cmd
}

// activeBuffer is the text buffer keys currently edit, if any.
func (a *App) activeBuffer() (*vim.Buffer, *vim.Undo) {
	switch a.editTarget {
	case TargetSearch:
		return a.searchBuf, a.searchUndo
	case TargetComposer:
		return a.composer.Buffer(), a.composer.Undo()
	}
	return nil, nil
}

func (a *App) insertLiteral(k keys.Key) {
	r, ok := k.Printable()
	if !ok {
		return
	}
	switch a.editTarget {
	case TargetCmdLine:
		a.cmdline += string(r)
		a.completions = nil
	case TargetFind:
		a.findLine += string(r)
	case TargetSearch:
		a.searchBuf.Insert(string(r))
		a.list.SetSearch(a.searchBuf.Text())
	case TargetComposer:
		a.composer.Buffer().Insert(string(r))
	}
}

func (a *App) applyOperator(r vim.Resolved) {
	buf, undo := a.activeBuffer()
	if buf == nil {
		a.setStatus("nothing to edit here")
		return
	}
	undo.Checkpoint()

	from := buf.Cursor()
	var span vim.Span
	if r.TextObject != "" {
		s, ok := vim.TextObject(buf, r.TextObject, r.Around)
		if !ok {
			return
		}
		span = s
	} else {
		m := vim.Move(buf, r.Motion, r.EffectiveCount(), r.Arg)
		if !m.Valid && r.Motion != "line" {
			return
		}
		span = vim.SpanForMotion(buf, m, from)
	}
	if vim.Apply(buf, r.Operator, span, a.engine.Registers(), r.Register) {
		a.engine.SetMode(vim.Insert)
	}
	a.afterEdit()
}

func (a *App) applyMotion(r vim.Resolved) {
	if buf, _ := a.activeBuffer(); buf != nil {
		if m := vim.Move(buf, r.Motion, r.EffectiveCount(), r.Arg); m.Valid {
			buf.SetCursor(m.To)
		}
		return
	}
	// Outside a text buffer a motion is pane navigation.
	switch r.Motion {
	case "down", "right":
		a.navigate(r.EffectiveCount())
	case "up", "left":
		a.navigate(-r.EffectiveCount())
	case "buffer_start":
		a.navTop()
	case "buffer_end":
		a.navBottom()
	}
}

// afterEdit keeps the derived views in step with the buffer that just changed.
func (a *App) afterEdit() {
	if a.editTarget == TargetSearch {
		a.list.SetSearch(a.searchBuf.Text())
	}
}

// --- layout ----------------------------------------------------------------

func (a *App) resize(w, h int) {
	a.width, a.height = w, h
	a.list.Resize(a.listWidth(), a.bodyHeight())
	a.pane.Resize(a.chatWidth(), a.bodyHeight()-a.composer.Height())
	a.composer.Resize(a.chatWidth())
	a.cache.Clear()
}

// narrow reports whether the terminal is too small for two panes, in which
// case Tab switches between them instead.
func (a *App) narrow() bool { return a.width < a.cfg.UI.MinWidth }

func (a *App) listWidth() int {
	if a.narrow() {
		return a.width
	}
	w := a.cfg.UI.ListWidth
	if w < 12 {
		w = 12
	}
	if w > a.width-20 {
		w = maxInt(12, a.width/3)
	}
	return w
}

func (a *App) chatWidth() int {
	if a.narrow() {
		return a.width
	}
	return maxInt(20, a.width-a.listWidth()-1)
}

// bodyHeight is the space above the status and command lines.
func (a *App) bodyHeight() int { return maxInt(1, a.height-2) }

// View renders the whole screen.
func (a *App) View() string {
	if a.lockScreen != nil && a.lockScreen.Locked() {
		return a.lockScreen.View(a.styles, a.width, a.height)
	}
	if a.showHelp {
		return a.helpView()
	}
	if a.showLog {
		return a.log.View(a.styles, a.width, a.height-1) + "\n" + a.statusLine()
	}
	if a.picker.IsOpen() {
		return a.picker.View(a.styles, a.width, a.height-1) + "\n" + a.statusLine()
	}

	body := a.bodyView()
	return body + "\n" + a.statusLine() + "\n" + a.promptLine()
}

func (a *App) bodyView() string {
	chatArea := a.chatArea()
	if a.narrow() {
		if a.focus == FocusList {
			return a.list.View()
		}
		return chatArea
	}

	left := strings.Split(a.list.View(), "\n")
	right := strings.Split(chatArea, "\n")
	rows := a.bodyHeight()

	var b strings.Builder
	for i := 0; i < rows; i++ {
		if i > 0 {
			b.WriteString("\n")
		}
		l := ""
		if i < len(left) {
			l = left[i]
		}
		r := ""
		if i < len(right) {
			r = right[i]
		}
		b.WriteString(render.Pad(render.Truncate(l, a.listWidth()), a.listWidth()))
		b.WriteString(a.styles.Divider.Render("│"))
		b.WriteString(render.Pad(render.Truncate(r, a.chatWidth()), a.chatWidth()))
	}
	return b.String()
}

// chatArea is the message pane with the composer, and the quickfix window when
// it is open.
func (a *App) chatArea() string {
	composerHeight := a.composer.Height()
	qfHeight := 0
	if a.showQF && a.qf.Open() {
		qfHeight = minInt(10, maxInt(3, a.bodyHeight()/3))
	}
	paneHeight := maxInt(1, a.bodyHeight()-composerHeight-qfHeight)
	a.pane.Resize(a.chatWidth(), paneHeight)

	parts := []string{a.pane.View()}
	if qfHeight > 0 {
		parts = append(parts, a.qf.View(a.styles, a.chatWidth(), qfHeight))
	}
	parts = append(parts, a.composer.View(a.focus == FocusComposer))
	return strings.Join(parts, "\n")
}

// statusLine shows the mode, the chat, the sync state, and the last message.
func (a *App) statusLine() string {
	mode := a.engine.Mode().String()
	if name, on := a.engine.Recording(); on {
		mode += fmt.Sprintf(" REC @%c", name)
	}

	chat := ""
	if c, ok := a.list.Selected(); ok {
		chat = c.DisplayName()
	}

	sync := "off"
	if a.deps.Daemon != nil {
		sync = a.deps.Daemon.Mode().String()
	}

	left := a.styles.StatusKey.Render(" "+mode+" ") + " " +
		a.styles.Status.Render(chat)

	right := a.styles.Status.Render(fmt.Sprintf("%s  %s ", a.focus, sync))

	middle := a.status
	style := a.styles.Status
	if a.statusErr {
		style = a.styles.StatusErr
	}

	gap := a.width - render.VisibleWidth(left) - render.VisibleWidth(right)
	body := render.Truncate(middle, maxInt(0, gap))
	return left + style.Render(render.Pad(" "+body, maxInt(0, gap))) + right
}

// promptLine is the : or / prompt, or the pending key sequence.
func (a *App) promptLine() string {
	switch a.engine.Mode() {
	case vim.CmdLine:
		return a.styles.CmdLine.Render(":"+a.cmdline) + "▏" + a.completionHint()
	case vim.Search:
		sigil := "/"
		if !a.findForward {
			sigil = "?"
		}
		return a.styles.Search.Render(sigil+a.findLine) + "▏"
	}
	if pending := a.engine.Pending(); len(pending) > 0 {
		return a.styles.Placeholder.Render(keys.Notation(pending))
	}
	if n := a.engine.PendingCount(); n > 0 {
		return a.styles.Placeholder.Render(fmt.Sprintf("%d", n))
	}
	return ""
}

func (a *App) completionHint() string {
	if len(a.completions) == 0 {
		return ""
	}
	return a.styles.Placeholder.Render("  " + strings.Join(a.completions, " "))
}

func (a *App) helpView() string {
	var b strings.Builder
	b.WriteString(a.styles.ListFilter.Render("wa - keys"))
	b.WriteString("\n\n")

	binds := a.keymap.Bindings(vim.Normal)
	notations := make([]string, 0, len(binds))
	for n := range binds {
		notations = append(notations, n)
	}
	SortStrings(notations)

	rows := a.height - 4
	for i, n := range notations {
		if i >= rows {
			b.WriteString("\n" + a.styles.Placeholder.Render("…"))
			break
		}
		b.WriteString(fmt.Sprintf("\n  %-16s %s", n, binds[n].Name))
	}
	b.WriteString("\n\n" + a.styles.Placeholder.Render("any key to close"))
	return b.String()
}

// --- status ----------------------------------------------------------------

func (a *App) setStatus(text string) {
	a.status = text
	a.statusErr = false
	if text != "" {
		a.log.Infof("%s", text)
	}
}

func (a *App) setError(text string) {
	a.status = text
	a.statusErr = true
	a.log.Errorf("%s", text)
}

// Announce reports a degradation once and shows it in the status line.
func (a *App) Announce(key, text string) {
	if a.log.Announce(key, text) {
		a.status = text
		a.statusErr = false
	}
}

// --- accessors used by tests and actions -----------------------------------

// Focus is which pane has the keyboard.
func (a *App) Focus() Focus { return a.focus }

// Mode is the editing mode.
func (a *App) Mode() vim.Mode { return a.engine.Mode() }

// InsertTarget is which buffer insert-mode keys reach.
func (a *App) InsertTarget() EditTarget { return a.editTarget }

// Status is the status line's text.
func (a *App) Status() string { return a.status }

// LogText is the :log buffer, for tests.
func (a *App) LogText() string { return a.log.Text() }

// Config is the live configuration.
func (a *App) Config() config.Config { return a.cfg }

// Quickfix is the result list.
func (a *App) QuickfixList() *Quickfix { return &a.qf }

// PickerOpen reports whether the overlay is showing.
func (a *App) PickerOpen() bool { return a.picker.IsOpen() }

// Locked reports whether the lock screen is up.
func (a *App) Locked() bool { return a.lockScreen != nil && a.lockScreen.Locked() }

// CurrentChat is the conversation on screen.
func (a *App) CurrentChat() (domain.JID, bool) {
	c, ok := a.list.Selected()
	return c.JID, ok
}

// SearchHighlighted reports whether search matches are marked.
func (a *App) SearchHighlighted() bool { return a.pane.Highlighted() }

// List, Pane and ComposerPane expose the panes for tests.
func (a *App) List() *ChatList         { return a.list }
func (a *App) Pane() *MessagePane      { return a.pane }
func (a *App) ComposerPane() *Composer { return a.composer }

// Emit injects a live event, for tests.
func (a *App) Emit(ev domain.Event) { a.applyEvent(ev) }

// SortStrings is a tiny helper kept here so the help view has no extra import.
func SortStrings(s []string) {
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j] < s[j-1]; j-- {
			s[j], s[j-1] = s[j-1], s[j]
		}
	}
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
