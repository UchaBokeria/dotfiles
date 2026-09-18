package ui

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
)

// The things the phone app puts behind a long press.
//
// Everything here goes through wacli, and wacli cannot do everything WhatsApp
// can: there is no block, and no disappearing-messages timer. Where the
// command does not exist the action says so in one line and names what it
// would take, rather than pretending or failing silently.

// favouriteTag is how a favourite is kept. WhatsApp's own favourites never
// reach a linked device, so this is one of wacli's local contact tags: it
// survives a sync and it is visible to `wacli contacts tags`.
const favouriteTag = "favourite"

// toggleFavourite marks or unmarks the chats being acted on.
func (a *App) toggleFavourite() error {
	chats := a.markedChats()
	if len(chats) == 0 {
		return fmt.Errorf("no chat is selected")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// The first chat decides the direction, so a mixed selection ends up all
	// one way rather than each one flipped to the opposite of what it was.
	on := !a.isFavourite(ctx, chats[0].JID)
	client := a.deps.Client
	jids := chatJIDs(chats)

	verb := map[bool]string{true: "favouriting", false: "unfavouriting"}[on]
	done := map[bool]string{true: "favourited", false: "unfavourited"}[on]
	return a.locked(verb, done+" "+plural(len(jids), "chat", "chats"),
		func(ctx context.Context) error {
			for _, j := range jids {
				if err := client.Tag(ctx, j, favouriteTag, on); err != nil {
					return err
				}
			}
			return nil
		}, a.reloadList)
}

// isFavourite reads the tag back off the store.
func (a *App) isFavourite(ctx context.Context, jid domain.JID) bool {
	c, err := a.deps.Store.Contact(ctx, jid)
	if err != nil {
		return false
	}
	for _, t := range c.Tags {
		if t == favouriteTag {
			return true
		}
	}
	return false
}

// exportChat writes a conversation to a file.
func (a *App) exportChat() error {
	chats := a.markedChats()
	if len(chats) == 0 {
		return fmt.Errorf("no chat is selected")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	dir := a.exportDir()
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}

	client := a.deps.Client
	paths := make([]string, 0, len(chats))
	type job struct {
		jid  domain.JID
		path string
	}
	jobs := make([]job, 0, len(chats))
	for _, c := range chats {
		name := exportName(c)
		p := filepath.Join(dir, name)
		jobs = append(jobs, job{jid: c.JID, path: p})
		paths = append(paths, p)
	}

	// Exporting reads the store, which the sync process may be holding; it
	// goes through the same handover as everything else that touches it.
	return a.locked("exporting", "exported to "+strings.Join(shortPaths(paths), ", "),
		func(ctx context.Context) error {
			for _, j := range jobs {
				if err := client.Export(ctx, j.jid, j.path, 0); err != nil {
					return err
				}
			}
			return nil
		})
}

// exportDir is where an export lands: alongside the downloads, under the
// state directory, so it is somewhere findable rather than the working
// directory of whatever shell started wa.
func (a *App) exportDir() string {
	if home, err := os.UserHomeDir(); err == nil {
		return filepath.Join(home, "Downloads", "wa-export")
	}
	return filepath.Join(a.deps.CacheDir, "export")
}

// exportName is a filename that says which chat and when.
func exportName(c domain.Chat) string {
	name := strings.Map(func(r rune) rune {
		switch {
		case r >= 'a' && r <= 'z', r >= 'A' && r <= 'Z', r >= '0' && r <= '9':
			return r
		case r == ' ', r == '-', r == '_':
			return '-'
		}
		return -1
	}, c.DisplayName())
	name = strings.Trim(name, "-")
	if name == "" {
		name = c.JID.User
	}
	return name + "-" + time.Now().Format("20060102") + ".json"
}

func shortPaths(paths []string) []string {
	out := make([]string, 0, len(paths))
	for _, p := range paths {
		out = append(out, shortenPath(p))
	}
	return out
}

// clearChat removes the local copy of a conversation.
func (a *App) clearChat() error {
	chats := a.markedChats()
	if len(chats) == 0 {
		return fmt.Errorf("no chat is selected")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	client := a.deps.Client
	jids := chatJIDs(chats)

	return a.locked("clearing",
		"cleared locally; a sync brings back whatever WhatsApp still holds",
		func(ctx context.Context) error {
			for _, j := range jids {
				if err := client.ClearChat(ctx, j); err != nil {
					return err
				}
			}
			return nil
		}, a.reloadList)
}

// markChatsRead marks every selected chat read, or unread.
func (a *App) markChatsRead(read bool) error {
	chats := a.markedChats()
	if len(chats) == 0 {
		return fmt.Errorf("no chat is selected")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	client := a.deps.Client
	jids := chatJIDs(chats)

	verb := map[bool]string{true: "marking read", false: "marking unread"}[read]
	done := map[bool]string{true: "marked read", false: "marked unread"}[read]
	return a.locked(verb, done+" · "+plural(len(jids), "chat", "chats"),
		func(ctx context.Context) error {
			for _, j := range jids {
				var err error
				if read {
					err = client.MarkRead(ctx, j)
				} else {
					err = client.MarkUnread(ctx, j)
				}
				if err != nil {
					return err
				}
			}
			return nil
		}, a.reloadList)
}

// archiveChats and muteChats apply the phone app's two other switches to a
// whole selection.
func (a *App) archiveChats(on bool) error {
	return a.chatSwitch(on, "archiving", "unarchiving", "archived", "unarchived",
		func(ctx context.Context, j domain.JID, on bool) error {
			return a.deps.Client.Archive(ctx, j, on)
		})
}

func (a *App) muteChats(on bool) error {
	return a.chatSwitch(on, "muting", "unmuting", "muted", "unmuted",
		func(ctx context.Context, j domain.JID, on bool) error {
			return a.deps.Client.Mute(ctx, j, on)
		})
}

func (a *App) pinChats(on bool) error {
	return a.chatSwitch(on, "pinning", "unpinning", "pinned", "unpinned",
		func(ctx context.Context, j domain.JID, on bool) error {
			return a.deps.Client.Pin(ctx, j, on)
		})
}

func (a *App) chatSwitch(on bool, doingOn, doingOff, doneOn, doneOff string,
	fn func(context.Context, domain.JID, bool) error) error {

	chats := a.markedChats()
	if len(chats) == 0 {
		return fmt.Errorf("no chat is selected")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	jids := chatJIDs(chats)

	doing, done := doingOff, doneOff
	if on {
		doing, done = doingOn, doneOn
	}
	return a.locked(doing, done+" · "+plural(len(jids), "chat", "chats"),
		func(ctx context.Context) error {
			for _, j := range jids {
				if err := fn(ctx, j, on); err != nil {
					return err
				}
			}
			return nil
		}, a.reloadList)
}

// blockContact is not something wacli can do.
func (a *App) blockContact() error {
	c, ok := a.targetChat()
	if !ok {
		return fmt.Errorf("no chat is selected")
	}
	return fmt.Errorf("wacli cannot block %s: it has no block command, and WhatsApp's "+
		"block list is not in the local store. Block from the phone", c.DisplayName())
}

// setDisappearing is not something wacli can do either.
func (a *App) setDisappearing() error {
	return fmt.Errorf("wacli has no disappearing-messages command; " +
		"set the timer on the phone and wa will show what arrives")
}

// reloadList re-reads the chat list after something changed several rows.
func (a *App) reloadList() error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	return a.list.Load(ctx)
}

func chatJIDs(chats []domain.Chat) []domain.JID {
	out := make([]domain.JID, 0, len(chats))
	for _, c := range chats {
		out = append(out, c.JID)
	}
	return out
}

// --- contacts ----------------------------------------------------------------

// openContacts shows the address book. It is a tab in the sense that matters:
// a way to reach someone wa has never had a conversation with.
func (a *App) openContacts() error {
	if a.deps.Store == nil {
		return fmt.Errorf("no store")
	}
	a.picker.OpenLive("contacts", func(q string) []PickerItem {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		list, err := a.deps.Store.Contacts(ctx, store.ContactFilter{Query: q, Limit: 500})
		if err != nil {
			a.log.Warnf("contacts: %v", err)
			return nil
		}
		out := make([]PickerItem, 0, len(list))
		for _, c := range list {
			detail := c.JID.Display()
			if len(c.Tags) > 0 {
				detail += "  " + strings.Join(c.Tags, " ")
			}
			out = append(out, PickerItem{
				Label:  c.DisplayName(),
				Detail: detail,
				Value:  c.JID.String(),
			})
		}
		return out
	}, func(it PickerItem) error {
		// Several marked: hand them to the chat list as a selection, where
		// every bulk action already lives - favourite, tag, archive, export.
		// Opening five conversations at once is not a thing anybody wants.
		if marked := a.picker.Accepted(); len(marked) > 1 {
			return a.selectContacts(marked)
		}
		jid, err := domain.ParseJID(it.Value)
		if err != nil {
			return err
		}
		return a.openChat(jid)
	})
	return nil
}

// selectContacts turns a set of marked contacts into the chat-list selection,
// so the drawer's actions apply to them.
func (a *App) selectContacts(items []PickerItem) error {
	a.chatMarks.clear()
	known, missing := 0, 0
	for _, it := range items {
		jid, err := domain.ParseJID(it.Value)
		if err != nil {
			continue
		}
		if !a.list.Select(jid) && !a.hasChat(jid) {
			// A contact with no conversation yet has no row to act on. Saying
			// how many were left out beats silently acting on fewer.
			missing++
			continue
		}
		a.chatMarks.toggle(jid.String())
		known++
	}
	a.list.SetMarks(a.chatMarks.ids)
	a.setFocus(FocusList)

	msg := plural(known, "contact", "contacts") + " selected; <Space>g acts on all of them"
	if missing > 0 {
		msg += fmt.Sprintf(" (%d with no conversation yet were left out)", missing)
	}
	a.setStatus(msg)
	return nil
}

// hasChat reports whether a conversation exists for a contact.
func (a *App) hasChat(jid domain.JID) bool {
	for _, c := range a.list.All() {
		if c.JID == jid || (c.JID.User != "" && c.JID.User == jid.User) {
			return true
		}
	}
	return false
}

// setAlias renames a contact locally: WhatsApp's own name comes from the
// phone's address book, which a linked device cannot write.
func (a *App) setAlias(name string) error {
	c, ok := a.targetChat()
	if !ok {
		return fmt.Errorf("no chat is selected")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	client, jid := a.deps.Client, c.JID
	done := "renamed to " + name
	if strings.TrimSpace(name) == "" {
		done = "name cleared"
	}
	return a.locked("renaming", done, func(ctx context.Context) error {
		return client.Alias(ctx, jid, name)
	}, a.reloadList)
}

// tagContact adds or removes one of wacli's local tags.
func (a *App) tagContact(tag string, on bool) error {
	c, ok := a.targetChat()
	if !ok {
		return fmt.Errorf("no chat is selected")
	}
	if tag == "" {
		return fmt.Errorf("which tag?")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	client, jid := a.deps.Client, c.JID
	doing, done := "tagging", "tagged "+tag
	if !on {
		doing, done = "untagging", "untagged "+tag
	}
	return a.locked(doing, done, func(ctx context.Context) error {
		return client.Tag(ctx, jid, tag, on)
	}, a.reloadList)
}

// cmdGroupParticipant is the ":group-add" and ":group-remove" commands, and
// what a name picked from the members list falls through to for removal.
func (a *App) cmdGroupParticipant(who, action string) error {
	c, ok := a.targetChat()
	if !ok {
		return fmt.Errorf("no chat is selected")
	}
	if c.Kind != domain.KindGroup {
		return fmt.Errorf("%s is not a group", c.DisplayName())
	}
	if who == "" {
		return fmt.Errorf("group-%s: a phone number or JID", action)
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	client, jid := a.deps.Client, c.JID
	doing, done := "adding "+who, "added "+who+" to the group"
	if action == "remove" {
		doing, done = "removing "+who, "removed "+who+" from the group"
	}
	return a.locked(doing, done, func(ctx context.Context) error {
		_, err := client.Raw(ctx, "groups", "participants", action,
			"--jid", jid.String(), "--user", who)
		return err
	})
}

// groupParticipant is one row of `wacli groups participants list --json`.
type groupParticipant struct {
	UserJID string `json:"user_jid"`
	Role    string `json:"role"`
}

// groupMembersMsg carries the participant snapshot back to the main loop,
// which is where a picker is allowed to open.
type groupMembersMsg struct {
	jid  domain.JID
	name string
	data []byte
	err  error
}

// showGroupMembers is what a click on a group's name in the header opens: who
// is in it, and a way to add or remove someone without leaving the keyboard.
//
// The list is wacli's local snapshot, not a live fetch - the same one `wacli
// groups participants list` reads - because asking WhatsApp on every click
// would make opening the panel feel like a network request instead of a
// glance at a roster.
func (a *App) showGroupMembers() error {
	c, ok := a.targetChat()
	if !ok {
		return fmt.Errorf("no chat is selected")
	}
	if c.Kind != domain.KindGroup {
		return fmt.Errorf("%s is not a group", c.DisplayName())
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	client, jid, name := a.deps.Client, c.JID, a.list.DisplayName(c)
	a.setStatus("loading members…")
	a.queue(func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		data, err := client.Raw(ctx, "groups", "participants", "list", "--jid", jid.String())
		return groupMembersMsg{jid: jid, name: name, data: data, err: err}
	})
	return nil
}

// openGroupMembersPicker turns the participant snapshot into rows: an "add"
// entry first, since that is the one action nothing else on the row can be
// mistaken for, then everyone else with their role. Picking a member removes
// them - the picker already asks "are you sure" with the keystroke it takes
// to get the cursor there, the same way every other destructive row in wa
// works.
func (a *App) openGroupMembersPicker(m groupMembersMsg) {
	var rows []groupParticipant
	if err := json.Unmarshal(m.data, &rows); err != nil {
		a.setError("group members: " + err.Error())
		return
	}
	a.setStatus(plural(len(rows), "member", "members"))

	items := make([]PickerItem, 0, len(rows)+1)
	items = append(items, PickerItem{Label: "+ add a participant", Value: ""})
	for _, r := range rows {
		label := r.UserJID
		if u, err := domain.ParseJID(r.UserJID); err == nil {
			label = a.chatName(u)
		}
		items = append(items, PickerItem{Label: label, Detail: r.Role, Value: r.UserJID})
	}

	jid := m.jid
	a.picker.Open(m.name+" · enter removes, esc closes", items, func(it PickerItem) error {
		if it.Value == "" {
			a.startCommand("group-add ")
			return nil
		}
		c, ok := a.targetChat()
		if !ok || c.JID != jid {
			// The open chat moved on while the picker was up; acting on a
			// group that is no longer the one on screen would be a surprise.
			return fmt.Errorf("no longer viewing that group")
		}
		return a.cmdGroupParticipant(it.Value, "remove")
	})
}

// addContact checks a number is on WhatsApp and opens the conversation,
// naming it if a name was given.
//
// There is no "add to address book": the address book belongs to the phone.
// What can be done is exactly what is useful here - confirm the number exists,
// give it a local name, and open the chat.
func (a *App) addContact(number, name string) error {
	number = strings.TrimSpace(number)
	if number == "" {
		return fmt.Errorf("which number?")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	jid, err := domain.ParseJID(normalizeNumber(number))
	if err != nil {
		return fmt.Errorf("%q is not a number wa can read: %w", number, err)
	}

	client := a.deps.Client
	a.setStatus("checking " + number + "…")
	a.queue(func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		body, err := client.Registered(ctx, number)
		if err != nil {
			return statusMsg{text: "checking " + number + ": " + err.Error(), isErr: true}
		}
		if !strings.Contains(strings.ToLower(string(body)), "true") {
			return statusMsg{text: number + " is not on WhatsApp", isErr: true}
		}
		if name != "" {
			if err := client.Alias(ctx, jid, name); err != nil {
				return statusMsg{text: "naming " + number + ": " + err.Error(), isErr: true}
			}
		}
		return statusMsg{text: number + " is on WhatsApp; opening"}
	})
	return a.openChat(jid)
}

// forgetContact drops wa's local additions - the name and the tags - and
// nothing else. The contact itself belongs to WhatsApp.
func (a *App) forgetContact() error {
	c, ok := a.targetChat()
	if !ok {
		return fmt.Errorf("no chat is selected")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	contact, _ := a.deps.Store.Contact(ctx, c.JID)

	client, jid, tags := a.deps.Client, c.JID, contact.Tags
	return a.locked("forgetting", "local name and tags removed",
		func(ctx context.Context) error {
			if err := client.Alias(ctx, jid, ""); err != nil {
				return err
			}
			for _, t := range tags {
				if err := client.Tag(ctx, jid, t, false); err != nil {
					return err
				}
			}
			return nil
		}, a.reloadList)
}

// normalizeNumber turns what people type into what a JID needs.
func normalizeNumber(s string) string {
	if strings.Contains(s, "@") {
		return s
	}
	var digits strings.Builder
	for _, r := range s {
		if r >= '0' && r <= '9' {
			digits.WriteRune(r)
		}
	}
	return digits.String() + "@s.whatsapp.net"
}
