package ui

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
)

// commandNames is what Tab completes and what :help lists.
var commandNames = []string{
	"actions", "archive", "chat", "filter", "grep", "help", "keys", "log",
	"lock", "map", "mute", "pin", "quit", "q", "read", "reload", "revoke",
	"search", "set", "sync", "unarchive", "unmap", "unmute", "unpin",
	"unread", "version", "write", "media", "download", "preview",
	"attach", "detach", "paste",
}

// runCmdLine executes what was typed at the : prompt.
func (a *App) runCmdLine() error {
	line := a.cmdline
	a.cmdline = ""
	a.completions = nil
	a.editTarget = TargetNone
	a.engine.SetMode(vim.Normal)

	if strings.TrimSpace(line) == "" {
		return nil
	}
	a.cmdHistory.Add(line)

	cmd, err := vim.ParseCommand(line)
	if err != nil {
		return err
	}
	return a.runCommand(cmd)
}

// RunCommand executes a command line, for tests and for scripted use.
func (a *App) RunCommand(line string) error {
	cmd, err := vim.ParseCommand(line)
	if err != nil {
		return err
	}
	return a.runCommand(cmd)
}

func (a *App) runCommand(cmd vim.Command) error {
	switch cmd.Name {
	case "q", "quit":
		a.quitting = true
		return nil

	case "set":
		return a.cmdSet(cmd)

	case "map":
		return a.cmdMap(cmd)

	case "unmap":
		return a.cmdUnmap(cmd)

	case "filter":
		if len(cmd.Args) == 0 {
			a.setStatus("filter: " + a.list.Filter())
			return nil
		}
		if err := a.list.SetFilter(cmd.Args[0]); err != nil {
			return err
		}
		a.setStatus("filter: " + a.list.Filter())
		return nil

	case "chat":
		return a.cmdChat(cmd)

	case "search":
		if cmd.Raw == "" {
			return fmt.Errorf("search what?")
		}
		if !a.pane.Search(cmd.Raw, true, a.cfg.UI.IgnoreCase, a.cfg.UI.SmartCase) {
			return fmt.Errorf("pattern not found: %s", cmd.Raw)
		}
		return nil

	case "grep":
		return a.cmdGrep(cmd)

	case "archive", "unarchive", "pin", "unpin", "mute", "unmute", "read", "unread":
		return a.cmdChatFlag(cmd.Name)

	case "revoke":
		return a.cmdRevoke()

	case "lock":
		if a.lockScreen == nil || !a.lockScreen.Lock() {
			return fmt.Errorf("no password is set (run: wa lock set)")
		}
		return nil

	case "reload":
		a.reload()
		return nil

	case "actions":
		a.openActionPicker()
		return nil

	case "keys":
		a.openKeyPicker()
		return nil

	case "log":
		a.openLog()
		return nil

	case "help":
		a.openHelp()
		return nil

	case "sync":
		if a.deps.Daemon == nil {
			a.setStatus("no sync process")
			return nil
		}
		a.setStatus("sync: " + a.deps.Daemon.Status())
		return nil

	case "media":
		a.overlay.Open("media in this chat", a.mediaSummary())
		return nil

	case "download":
		if len(cmd.Args) > 0 && cmd.Args[0] == "all" {
			return a.downloadAllInChat()
		}
		m, ok := a.pane.Selected()
		if !ok || !m.HasMedia() {
			return fmt.Errorf("the selected message has no media (try :download all)")
		}
		return a.downloadMedia(m)

	case "attach":
		return a.cmdAttach(cmd.Raw)

	case "detach":
		return a.cmdDetach()

	case "paste":
		return a.pasteFromClipboard()

	case "preview":
		next := a.cfg
		next.Media.Preview = !next.Media.Preview
		if err := a.applyConfig(next); err != nil {
			return err
		}
		a.pane.Invalidate()
		a.setStatus(label(next.Media.Preview, "previews on", "previews off"))
		return nil

	case "version":
		a.setStatus("wa (blackwall)")
		return nil
	}
	return fmt.Errorf("%q is not a command (try :actions)", cmd.Name)
}

// cmdSet reads or writes a setting. With a bang it also persists it.
func (a *App) cmdSet(cmd vim.Command) error {
	if len(cmd.Args) == 0 {
		return fmt.Errorf("set what? (try :set with Tab)")
	}
	assignments := map[string]string{}
	next := a.cfg

	for _, arg := range cmd.Args {
		path, value, found := strings.Cut(arg, "=")
		if !found {
			// A bare name reads the setting.
			got, err := next.Get(path)
			if err != nil {
				return err
			}
			a.setStatus(fmt.Sprintf("%s=%s", path, got))
			return nil
		}
		if err := next.Set(path, value); err != nil {
			return err
		}
		assignments[path] = value
	}

	if err := a.applyConfig(next); err != nil {
		return err
	}
	if cmd.Bang {
		if a.deps.OverridesPath == "" {
			return fmt.Errorf("nowhere to persist to")
		}
		if err := config.Persist(a.deps.OverridesPath, assignments); err != nil {
			return err
		}
		a.setStatus("saved")
		return nil
	}
	a.setStatus("set")
	return nil
}

// cmdMap binds a key at runtime: :map <mode> <keys> <action>.
func (a *App) cmdMap(cmd vim.Command) error {
	if len(cmd.Args) < 3 {
		return fmt.Errorf("usage: :map <mode> <keys> <action>")
	}
	mode, notation, target := cmd.Args[0], cmd.Args[1], cmd.Args[2]
	mode = expandMode(mode)

	if _, ok := vim.ModeName(mode); !ok && mode != "motion" {
		return fmt.Errorf("%q is not a mode", mode)
	}
	if mode != "motion" && !a.reg.Has(target) {
		return fmt.Errorf("%q is not an action (try :actions)", target)
	}
	if _, err := keys.Parse(notation, a.cfg.Leader()); err != nil {
		return err
	}

	next := a.cfg
	next.Keys = cloneKeys(a.cfg.Keys)
	if next.Keys[mode] == nil {
		next.Keys[mode] = map[string]string{}
	}
	next.Keys[mode][notation] = target

	if err := a.applyConfig(next); err != nil {
		return err
	}
	a.setStatus(fmt.Sprintf("%s %s -> %s", mode, notation, target))
	return nil
}

func (a *App) cmdUnmap(cmd vim.Command) error {
	if len(cmd.Args) < 2 {
		return fmt.Errorf("usage: :unmap <mode> <keys>")
	}
	mode, notation := expandMode(cmd.Args[0]), cmd.Args[1]

	next := a.cfg
	next.Keys = cloneKeys(a.cfg.Keys)
	if next.Keys[mode] == nil {
		return fmt.Errorf("nothing is bound in %s", mode)
	}
	if _, ok := next.Keys[mode][notation]; !ok {
		return fmt.Errorf("%s is not bound in %s", notation, mode)
	}
	delete(next.Keys[mode], notation)

	if err := a.applyConfig(next); err != nil {
		return err
	}
	a.setStatus("unmapped " + notation)
	return nil
}

// expandMode accepts vim's single-letter mode names.
func expandMode(m string) string {
	switch m {
	case "n":
		return "normal"
	case "i":
		return "insert"
	case "v":
		return "visual"
	case "c":
		return "cmdline"
	case "s":
		return "search"
	}
	return m
}

func cloneKeys(in map[string]map[string]string) map[string]map[string]string {
	out := make(map[string]map[string]string, len(in))
	for mode, binds := range in {
		m := make(map[string]string, len(binds))
		for k, v := range binds {
			m[k] = v
		}
		out[mode] = m
	}
	return out
}

// cmdChat opens a conversation by name or number.
func (a *App) cmdChat(cmd vim.Command) error {
	if cmd.Raw == "" {
		return fmt.Errorf("which chat?")
	}
	needle := strings.ToLower(strings.Trim(cmd.Raw, `"`))

	var matches []int
	for i, c := range a.list.Rows() {
		if strings.Contains(strings.ToLower(c.DisplayName()), needle) ||
			strings.Contains(c.JID.User, needle) {
			matches = append(matches, i)
		}
	}
	switch len(matches) {
	case 0:
		return fmt.Errorf("no chat matches %q", cmd.Raw)
	case 1:
		a.list.MoveTo(matches[0])
		a.followSelection()
		a.setFocus(FocusChat)
		return nil
	}
	// Ambiguous: offer the choice rather than guessing.
	items := make([]PickerItem, 0, len(matches))
	for _, i := range matches {
		c := a.list.Rows()[i]
		items = append(items, PickerItem{
			Label: c.DisplayName(), Detail: c.LastSnippet, Value: c.JID.String(),
		})
	}
	a.picker.Open("chats matching "+cmd.Raw, items, func(it PickerItem) error {
		j, err := parseJID(it.Value)
		if err != nil {
			return err
		}
		return a.openChat(j)
	})
	return nil
}

// cmdGrep searches every chat and fills the quickfix list.
func (a *App) cmdGrep(cmd vim.Command) error {
	if cmd.Raw == "" {
		return fmt.Errorf("grep for what?")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	found, err := a.deps.Store.Search(ctx, store.Query{Text: cmd.Raw, Limit: 200})
	if err != nil {
		return err
	}
	if len(found) == 0 {
		a.qf.Set("grep "+cmd.Raw, nil)
		return fmt.Errorf("no results for %q", cmd.Raw)
	}

	names := map[string]string{}
	for _, c := range a.list.Rows() {
		names[c.JID.String()] = c.DisplayName()
	}

	items := make([]QFItem, 0, len(found))
	for _, m := range found {
		name := names[m.ChatJID.String()]
		if name == "" {
			name = m.ChatJID.Display()
		}
		items = append(items, QFItem{
			Chat: m.ChatJID, ChatName: name,
			MessageID: m.ID, Text: m.Body(), TS: m.TS,
		})
	}
	sort.SliceStable(items, func(i, j int) bool { return items[i].TS.After(items[j].TS) })

	a.qf.Set("grep "+cmd.Raw, items)
	a.showQF = true
	a.setStatus(fmt.Sprintf("%d results", len(items)))
	return nil
}

// cmdChatFlag is the : form of the chat toggles, which unlike the keys say
// exactly what they mean rather than flipping.
func (a *App) cmdChatFlag(name string) error {
	c, ok := a.targetChat()
	if !ok {
		return fmt.Errorf("no chat is selected")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	client := a.deps.Client

	var (
		act     func(context.Context) error
		inverse func(context.Context) error
	)
	switch name {
	case "archive":
		act = func(ctx context.Context) error { return client.Archive(ctx, c.JID, true) }
		inverse = func(ctx context.Context) error { return client.Archive(ctx, c.JID, false) }
	case "unarchive":
		act = func(ctx context.Context) error { return client.Archive(ctx, c.JID, false) }
		inverse = func(ctx context.Context) error { return client.Archive(ctx, c.JID, true) }
	case "pin":
		act = func(ctx context.Context) error { return client.Pin(ctx, c.JID, true) }
		inverse = func(ctx context.Context) error { return client.Pin(ctx, c.JID, false) }
	case "unpin":
		act = func(ctx context.Context) error { return client.Pin(ctx, c.JID, false) }
		inverse = func(ctx context.Context) error { return client.Pin(ctx, c.JID, true) }
	case "mute":
		act = func(ctx context.Context) error { return client.Mute(ctx, c.JID, true) }
		inverse = func(ctx context.Context) error { return client.Mute(ctx, c.JID, false) }
	case "unmute":
		act = func(ctx context.Context) error { return client.Mute(ctx, c.JID, false) }
		inverse = func(ctx context.Context) error { return client.Mute(ctx, c.JID, true) }
	case "read":
		act = func(ctx context.Context) error { return client.MarkRead(ctx, c.JID) }
		inverse = func(ctx context.Context) error { return client.MarkUnread(ctx, c.JID) }
	case "unread":
		act = func(ctx context.Context) error { return client.MarkUnread(ctx, c.JID) }
		inverse = func(ctx context.Context) error { return client.MarkRead(ctx, c.JID) }
	}
	gated := inverse
	jid := c.JID
	a.pushUndo(name, func(context.Context) error {
		return a.locked("undoing "+name, "undone", gated,
			func() error { return a.refreshChat(jid) })
	})
	return a.locked(name+"…", name, act, func() error { return a.refreshChat(jid) })
}

// cmdRevoke deletes a sent message for everyone.
//
// This is the only way to unsend, and it is deliberately a typed command. The
// undo key never does it: an undo that sometimes retracts a message already
// read by another person is a trap.
func (a *App) cmdRevoke() error {
	m, ok := a.pane.Selected()
	if !ok {
		return fmt.Errorf("no message is selected")
	}
	if !m.FromMe {
		return fmt.Errorf("only your own messages can be revoked")
	}
	return a.locked("revoking", "revoked", func(ctx context.Context) error {
		_, err := a.deps.Client.Raw(ctx, "messages", "revoke",
			"--chat", m.StoreJID().String(), "--id", m.ID)
		return err
	}, a.refreshPane)
}

// complete cycles Tab completion at the : prompt.
func (a *App) complete(dir int) {
	if strings.ContainsAny(a.cmdline, " \t") {
		a.completeArgument(dir)
		return
	}
	cands := vim.CompleteCommand(a.cmdline, commandNames)
	if len(cands) == 0 {
		return
	}
	if len(cands) == 1 {
		a.cmdline = cands[0] + " "
		a.completions = nil
		return
	}
	a.completions = cands
	a.completeAt = (a.completeAt + dir + len(cands)) % len(cands)
	a.cmdline = cands[a.completeAt]
}

// completeArgument completes the last word against whatever the command takes.
func (a *App) completeArgument(dir int) {
	cmd, err := vim.ParseCommand(a.cmdline)
	if err != nil {
		return
	}
	var cands []string
	switch cmd.Name {
	case "set":
		cands = vim.CompleteArg(a.cmdline, config.Paths())
	case "filter":
		cands = vim.CompleteArg(a.cmdline, chatFilters)
	case "map", "unmap":
		if len(cmd.Args) <= 1 {
			cands = vim.CompleteArg(a.cmdline, []string{"normal", "insert", "visual", "cmdline", "search", "motion"})
		} else {
			cands = vim.CompleteArg(a.cmdline, a.reg.Names())
		}
	case "chat":
		var names []string
		for _, c := range a.list.Rows() {
			names = append(names, c.DisplayName())
		}
		cands = vim.CompleteArg(a.cmdline, names)
	}
	if len(cands) == 0 {
		return
	}
	a.completions = cands
	a.completeAt = (a.completeAt + dir + len(cands)) % len(cands)

	fields := strings.Fields(a.cmdline)
	if strings.HasSuffix(a.cmdline, " ") {
		a.cmdline += cands[a.completeAt]
		return
	}
	fields[len(fields)-1] = cands[a.completeAt]
	a.cmdline = strings.Join(fields, " ")
}

// cmdAttach adds a file to the next message.
//
// The file is checked here rather than at send time: a path typed wrong should
// say so while it is still on screen, not two keystrokes later when the
// message has already left the composer.
func (a *App) cmdAttach(path string) error {
	path = strings.TrimSpace(path)
	if path == "" {
		return fmt.Errorf("usage: :attach <file>")
	}
	expanded, err := expandPath(path)
	if err != nil {
		return err
	}
	fi, err := os.Stat(expanded)
	if err != nil {
		return fmt.Errorf("%s: %w", path, err)
	}
	if fi.IsDir() {
		return fmt.Errorf("%s is a directory", path)
	}

	a.composer.Attach(expanded)
	a.setFocus(FocusComposer)
	a.setStatus("attached " + filepath.Base(expanded) + "; press enter to send")
	return nil
}

// cmdDetach removes the last attachment.
func (a *App) cmdDetach() error {
	last, ok := a.composer.DropAttachment()
	if !ok {
		return fmt.Errorf("nothing is attached")
	}
	a.setStatus("removed " + filepath.Base(last))
	return nil
}

// expandPath resolves ~ and makes the path absolute, because wacli is given it
// verbatim and runs somewhere else.
func expandPath(p string) (string, error) {
	if strings.HasPrefix(p, "~") {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		p = filepath.Join(home, strings.TrimPrefix(p, "~"))
	}
	return filepath.Abs(p)
}
