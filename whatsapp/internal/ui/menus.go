package ui

import (
	"context"
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/ui/render"
)

// The context menus.
//
// Every entry here is backed by something wacli can actually do. WhatsApp's
// own menus have items wa cannot honour yet - starring a message, pinning one
// inside a chat - and those are left out rather than shown greyed out forever:
// a permanently disabled row promises something the program will not deliver.

// openChatMenu is the right-click menu on the chat list.
func (a *App) openChatMenu(x, y int) {
	c, ok := a.list.Selected()
	if !ok {
		return
	}
	muted := c.Muted(time.Now())
	unread := c.Unread || c.UnreadCount > 0

	items := []MenuItem{
		{Label: "Open", Key: "Enter", Run: func() error {
			a.followSelection()
			a.setFocus(FocusChat)
			return nil
		}},
		{Separator: true},
		{Label: label(unread, "Mark as read", "Mark as unread"), Key: "<leader>r",
			Run: func() error { return a.toggleChat("read") }},
		{Label: label(c.Pinned, "Unpin chat", "Pin chat"), Key: "<leader>p",
			Run: func() error { return a.toggleChat("pin") }},
		{Label: label(muted, "Unmute notifications", "Mute notifications"), Key: "<leader>m",
			Run: func() error { return a.toggleChat("mute") }},
		{Label: label(c.Archived, "Unarchive chat", "Archive chat"), Key: "<leader>a",
			Run: func() error { return a.toggleChat("archive") }},
		{Separator: true},
		{Label: "Search in chat", Key: "/", Run: func() error {
			a.setFocus(FocusChat)
			a.startFind(true)
			return nil
		}},
		{Label: "Copy name", Run: func() error { return a.copyText(c.DisplayName()) }},
		{Label: "Copy number", Run: func() error { return a.copyText(c.JID.Display()) }},
		{Label: "Chat info", Run: func() error { return a.showChatInfo(c) }},
		{Separator: true},
		{Label: "Delete chat locally", Danger: true, Run: func() error { return a.deleteChat(c) }},
	}
	a.menu.Open(c.DisplayName(), items, x, y, a.width, a.height)
}

// openMessageMenu is the right-click menu on a message.
func (a *App) openMessageMenu(x, y int) {
	m, ok := a.pane.Selected()
	if !ok {
		return
	}

	items := []MenuItem{
		{Label: "Reply", Key: "r", Run: func() error { return a.startReply(m) }},
		{Label: "React 👍", Run: func() error { return a.react(m, "👍") }},
		{Label: "React ❤️", Run: func() error { return a.react(m, "❤️") }},
		{Label: "React …", Run: func() error { return a.promptReaction(m) }},
		{Label: "Forward to…", Run: func() error { a.forwardPicker(m); return nil }},
		{Separator: true},
		{Label: "Copy text", Key: "y", Run: func() error { return a.copyText(m.Body()) }},
	}

	// Every link, not only the first: a message often carries several, and
	// having to copy the text to reach the second one is silly.
	for _, run := range render.SplitLinks(m.Body()) {
		if run.URL == "" {
			continue
		}
		url := run.URL
		items = append(items,
			MenuItem{Label: "Open " + render1line(url, 32),
				Run: func() error { return a.openExternally(url) }},
			MenuItem{Label: "Copy " + render1line(url, 32),
				Run: func() error { return a.copyText(url) }},
		)
	}

	if m.HasMedia() {
		items = append(items, MenuItem{Separator: true})
		kind := mediaKind(m)
		if path, have := a.media.localPath(m); have {
			open := "Open " + kind.String()
			if media.Playable(kind) {
				open = "Play " + kind.String()
			}
			items = append(items,
				MenuItem{Label: open, Key: "<leader>o", Run: func() error { return a.openMedia(m) }},
				MenuItem{Label: "Copy file path", Run: func() error { return a.copyText(path) }},
			)
		} else {
			items = append(items,
				MenuItem{Label: "Download " + kind.String(), Key: "<leader>d",
					Run: func() error { return a.downloadMedia(m) }},
				MenuItem{Label: "Download all in this chat", Key: "<leader>D",
					Run: func() error { return a.downloadAllInChat() }},
			)
		}
	}

	items = append(items,
		MenuItem{Separator: true},
		MenuItem{Label: "Message info", Run: func() error { return a.showMessageInfo(m) }},
		MenuItem{Separator: true},
		MenuItem{Label: "Delete for me", Danger: true,
			Run: func() error { return a.deleteMessage(m, false) }},
	)
	if m.FromMe {
		items = append(items, MenuItem{Label: "Delete for everyone", Danger: true,
			Run: func() error { return a.deleteMessage(m, true) }})
	}

	title := m.SenderName
	if m.FromMe {
		title = "You"
	}
	if title == "" {
		title = "Message"
	}
	a.menu.Open(title, items, x, y, a.width, a.height)
}

// openComposerMenu is the right-click menu on the input box.
func (a *App) openComposerMenu(x, y int) {
	items := []MenuItem{
		{Label: "Paste", Key: "<C-r>", Run: func() error {
			text, err := a.clip.Read()
			if err != nil {
				return err
			}
			a.setFocus(FocusComposer)
			a.composer.Buffer().Insert(text)
			return nil
		}},
		{Label: "Copy draft", Run: func() error { return a.copyText(a.composer.Text()) }},
		{Label: "Clear draft", Danger: true, Run: func() error {
			a.composer.Undo().Checkpoint()
			a.composer.Buffer().SetText("")
			return nil
		}},
	}
	if a.replyTo.ID != "" {
		items = append(items, MenuItem{Separator: true},
			MenuItem{Label: "Cancel reply", Run: func() error {
				a.replyTo = domain.Message{}
				a.setStatus("reply cancelled")
				return nil
			}})
	}
	a.menu.Open("Draft", items, x, y, a.width, a.height)
}

// openMenuAtCursor opens the right menu for whichever pane has focus, so the
// keyboard reaches the same entries the right mouse button does.
func (a *App) openMenuAtCursor() {
	l := a.layout()
	switch a.focus {
	case FocusList:
		row := a.list.Index() - a.list.Offset() + 1
		a.openChatMenu(2, clampInt(row, 0, l.bodyHeight-1))
	case FocusComposer:
		a.openComposerMenu(l.chatX+2, maxInt(0, l.bodyHeight-l.composerRows))
	default:
		a.openMessageMenu(l.chatX+4, maxInt(0, l.paneRows/2))
	}
}

func label(cond bool, whenTrue, whenFalse string) string {
	if cond {
		return whenTrue
	}
	return whenFalse
}

// locked runs a wacli command that cannot be delegated to a running sync.
//
// Pinning, muting, archiving, deleting, forwarding and downloading media all
// need the store lock, which the sync process holds. The daemon stops it, runs
// the command and starts it again; that costs a few seconds, so the status
// line says what is happening rather than appearing to hang.
func (a *App) locked(doing, done string, fn func(context.Context) error, after ...func() error) error {
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	a.setStatus(doing + "…")

	// Queued, not run here. Handing the store lock over means stopping the
	// sync process, waiting for it to let go, running the command, and
	// starting it again - several seconds, during which this ran on the
	// interface's own goroutine and froze every key press. Pinning a chat
	// looked broken for exactly as long as it took.
	daemon := a.deps.Daemon
	var finish func() error
	if len(after) > 0 {
		finish = after[0]
	}

	a.queue(func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
		defer cancel()
		return lockedMsg{
			what: doing, done: done,
			err: daemon.WithLock(ctx, fn), after: finish,
		}
	})
	return nil
}

// --- the actions the menus call --------------------------------------------

func (a *App) copyText(text string) error {
	if strings.TrimSpace(text) == "" {
		return fmt.Errorf("nothing to copy")
	}
	if err := a.clip.Write(text); err != nil {
		return err
	}
	a.engine.Registers().Yank('"', text, false)
	a.setStatus("copied")
	return nil
}

// startReply arms the next send as a reply, the way tapping reply in the app
// does.
func (a *App) startReply(m domain.Message) error {
	a.replyTo = m
	a.setFocus(FocusComposer)
	a.enterInsert(false)
	a.setStatus("replying to " + render1line(m.Body(), 40))
	return nil
}

func (a *App) react(m domain.Message, emoji string) error {
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}

	args := append([]string{"send", "react", "--to", m.StoreJID().String(),
		"--id", m.ID, "--reaction", emoji}, a.deps.Client.PostSendWaitArgs()...)
	// A group reaction needs the sender, because the message id alone is not
	// unique across senders in a group.
	if m.ChatJID.Kind() == domain.KindGroup && !m.SenderJID.IsZero() {
		args = append(args, "--sender", m.SenderJID.String())
	}

	// Draw it now, ask afterwards. The send takes a couple of seconds and the
	// row it produces arrives later still, so a reaction that waited for
	// either looked like it had done nothing: the tap registered, the screen
	// did not change, and only reopening the client showed it.
	previous := m.Reactions
	a.pane.ApplyReaction(m.ID, emoji, a.deps.Self, "", true)
	if emoji == "" {
		a.setStatus("removing the reaction…")
	} else {
		a.setStatus("reacting " + emoji + "…")
	}

	client := a.deps.Client
	timeout := a.cfg.Wacli.Timeout.D()
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	msgID := m.ID

	a.queue(func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), timeout)
		defer cancel()
		_, err := client.Raw(ctx, args...)
		return reactedMsg{msgID: msgID, emoji: emoji, previous: previous, err: err}
	})
	return nil
}

// promptReaction opens the picker with the reactions WhatsApp offers.
func (a *App) promptReaction(m domain.Message) error {
	emojis := []string{"👍", "❤️", "😂", "😮", "😢", "🙏", "🔥", "🎉", "✅", "👎"}
	items := make([]PickerItem, 0, len(emojis)+1)
	for _, e := range emojis {
		items = append(items, PickerItem{Label: e, Value: e})
	}
	items = append(items, PickerItem{Label: "remove reaction", Value: ""})

	a.picker.Open("react", items, func(it PickerItem) error {
		return a.react(m, it.Value)
	})
	return nil
}

// forwardPicker asks which chat to forward to.
func (a *App) forwardPicker(m domain.Message) {
	// Names only: a snippet of the last message says nothing about where the
	// forward is going, and makes the list harder to scan.
	items := make([]PickerItem, 0, a.list.Len())
	for _, c := range a.list.Rows() {
		items = append(items, PickerItem{
			Label: a.list.DisplayName(c), Value: c.JID.String(),
		})
	}
	a.picker.Open("forward to", items, func(it PickerItem) error {
		to := it.Value
		return a.locked("forwarding", "forwarded to "+it.Label, func(ctx context.Context) error {
			args := append([]string{"messages", "forward",
				"--chat", m.StoreJID().String(), "--id", m.ID, "--to", to},
				a.deps.Client.PostSendWaitArgs()...)
			_, err := a.deps.Client.Raw(ctx, args...)
			return err
		})
	})
}

// downloadMedia fetches one attachment.
//
// It never takes the store lock. wacli's own advice, printed when a download
// collides with a running sync, is to pass --read-only with --output: that
// path reads nothing from the store and writes the file wherever it is told.
// The download is then not recorded in wacli's database, so wa keeps the file
// in its own cache and remembers it there.
func (a *App) downloadMedia(m domain.Message) error {
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	if !m.HasMedia() {
		return fmt.Errorf("the selected message has no media")
	}
	if err := a.media.cache.Ensure(); err != nil {
		return err
	}
	a.setStatus("downloading…")

	client := a.deps.Client
	cache := a.media.cache
	chat, id := m.StoreJID().String(), m.ID
	name := m.Media.Filename
	if name == "" {
		name = m.Media.Type
	}

	// In the background: an attachment is megabytes over somebody else's
	// network, and waiting for it on the interface's own goroutine meant
	// every key press waited for it too.
	a.queue(func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
		defer cancel()
		_, err := cache.Fetch(chat, id, func(args []string) error {
			_, err := client.Raw(ctx, args...)
			return err
		})
		if err != nil {
			return statusMsg{text: "downloading: " + err.Error(), isErr: true}
		}
		return downloadedMsg{what: "downloaded " + name}
	})
	return nil
}

// openExternally hands a file or a link to the desktop.
func (a *App) openExternally(target string) error {
	if target == "" {
		return fmt.Errorf("nothing to open")
	}
	opener := a.opener
	if opener == "" {
		opener = "xdg-open"
	}
	if _, err := exec.LookPath(opener); err != nil {
		return fmt.Errorf("%s is not installed", opener)
	}
	// Detached: the interface must not wait for an image viewer to close.
	cmd := exec.Command(opener, target)
	if err := cmd.Start(); err != nil {
		return err
	}
	go cmd.Wait()

	a.setStatus("opened " + filepath.Base(target))
	return nil
}

func (a *App) deleteMessage(m domain.Message, everyone bool) error {
	if everyone && !m.FromMe {
		return fmt.Errorf("only your own messages can be deleted for everyone")
	}
	// Deletion is not on the undo ring, and the status line says so, because
	// there is no way back from it.
	what := label(everyone, "deleted for everyone", "deleted for you") + " (not undoable)"
	return a.locked("deleting", what, func(ctx context.Context) error {
		if everyone {
			_, err := a.deps.Client.Raw(ctx, "messages", "revoke",
				"--chat", m.StoreJID().String(), "--id", m.ID)
			return err
		}
		_, err := a.deps.Client.Raw(ctx, "messages", "delete",
			"--chat", m.StoreJID().String(), "--id", m.ID, "--for-me")
		return err
	}, a.refreshPane)
}

// deleteChat removes a conversation from the local store. It does not delete
// anything on WhatsApp - wacli has no such command - and the wording says so.
func (a *App) deleteChat(c domain.Chat) error {
	jid := c.JID
	return a.locked("removing the chat",
		"removed from the local store; it will come back on the next sync",
		func(ctx context.Context) error {
			_, err := a.deps.Client.Raw(ctx, "chats", "cleanup",
				"--jid", jid.String(), "--confirm")
			return err
		}, func() error {
			ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer cancel()
			return a.list.Load(ctx)
		})
}

func (a *App) showChatInfo(c domain.Chat) error {
	lines := []string{
		"",
		"  name       " + c.DisplayName(),
		"  jid        " + c.JID.String(),
		"  kind       " + string(c.Kind),
		"  pinned     " + yesNo(c.Pinned),
		"  archived   " + yesNo(c.Archived),
		"  muted      " + yesNo(c.Muted(time.Now())),
		"  unread     " + itoa(c.UnreadCount),
	}
	if !c.LastMessageTS.IsZero() {
		lines = append(lines, "  last       "+c.LastMessageTS.Format("2006-01-02 15:04"))
	}
	a.overlay.Open("chat info", lines)
	return nil
}

func (a *App) showMessageInfo(m domain.Message) error {
	who := m.SenderName
	if m.FromMe {
		who = "you"
	}
	lines := []string{
		"",
		"  id         " + m.ID,
		"  chat       " + m.ChatJID.String(),
		"  from       " + who,
		"  sent       " + m.TS.Format("2006-01-02 15:04:05"),
		"  delivery   " + deliveryName(m.Delivery),
	}
	if m.Edited {
		lines = append(lines, "  edited     "+m.EditedTS.Format("2006-01-02 15:04:05"))
	}
	if m.QuotedID != "" {
		lines = append(lines, "  replying to "+m.QuotedID)
	}
	if m.HasMedia() {
		lines = append(lines,
			"",
			"  media      "+m.Media.Type,
			"  file       "+m.Media.Filename,
			"  size       "+itoa(int(m.Media.Length))+" bytes",
			"  local      "+m.Media.LocalPath,
		)
	}
	lines = append(lines, "", "  text", "")
	for _, l := range strings.Split(m.Body(), "\n") {
		lines = append(lines, "    "+l)
	}
	a.overlay.Open("message info", lines)
	return nil
}

func yesNo(b bool) string {
	if b {
		return "yes"
	}
	return "no"
}

func deliveryName(d domain.DeliveryState) string {
	switch d {
	case domain.Pending:
		return "sending"
	case domain.Sent:
		return "sent"
	case domain.Delivered:
		return "delivered"
	case domain.Read:
		return "read"
	case domain.Failed:
		return "failed"
	}
	return "unknown"
}

// firstLink finds the first URL in a message.
//
// The renderer decides what a link is, so what the menu offers to open is
// exactly what was drawn as clickable.
func firstLink(text string) string { return render.FirstLink(text) }

// render1line flattens a message for a one-line status message.
func render1line(s string, width int) string {
	s = strings.ReplaceAll(s, "\n", " ")
	if len([]rune(s)) > width {
		return string([]rune(s)[:width]) + "…"
	}
	return s
}

// pasteFromClipboard puts whatever the system clipboard holds into the draft.
//
// A picture becomes an attachment and text becomes text, because those are the
// two things a clipboard holds and doing the wrong one with either is useless.
// The picture is written into wa's cache first: wacli is given a path, and the
// clipboard is not a path.
func (a *App) pasteFromClipboard() error {
	if a.clip == nil {
		return fmt.Errorf("no clipboard")
	}
	if img, ok := a.clip.(imagePaster); ok {
		if _, has := img.HasImage(); has {
			path, err := img.ReadImage(filepath.Join(a.deps.CacheDir, "outgoing"))
			if err != nil {
				return err
			}
			a.composer.Attach(path)
			a.setFocus(FocusComposer)
			a.setStatus("pasted a picture; press enter to send")
			return nil
		}
	}

	text, err := a.clip.Read()
	if err != nil {
		return err
	}
	if strings.TrimSpace(text) == "" {
		return fmt.Errorf("the clipboard is empty")
	}
	a.setFocus(FocusComposer)
	a.composer.Buffer().Insert(text)
	a.setStatus(fmt.Sprintf("pasted %s", plural(len([]rune(text)), "character", "characters")))
	return nil
}

// imagePaster is the part of the clipboard that can hand over a picture. Not
// every clipboard can: OSC 52 carries text and nothing else.
type imagePaster interface {
	HasImage() (string, bool)
	ReadImage(dir string) (string, error)
}
