package ui

import (
	"strings"
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/action"
)

func TestMarkingChatsAndActingOnAllOfThem(t *testing.T) {
	a := newTestApp(t)
	if a.Focus() != FocusList {
		t.Fatalf("focus = %v, want the list", a.Focus())
	}

	a.feed(t, "<C-v>") // marks the first chat and moves on
	a.feed(t, "<C-v>") // marks the second
	if got := a.chatMarks.len(); got != 2 {
		t.Fatalf("%d chats marked, want 2", got)
	}

	if err := a.reg.Run("chat.mark_read", action.Context{}); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if n := a.calls("chats mark-read"); n != 2 {
		t.Errorf("mark-read ran %d times, want one per marked chat", n)
	}
}

func TestMarksAreVisibleInTheList(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<C-v>")
	if !strings.Contains(a.list.View(), "✓") {
		t.Error("a marked chat is not drawn as marked")
	}
}

func TestEscapeDropsTheMarks(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<C-v><C-v>")
	a.feed(t, "<Esc>")
	if a.chatMarks.len() != 0 {
		t.Error("escape left the marks in place")
	}
	if strings.Contains(a.list.View(), "✓") {
		t.Error("the list still draws marks")
	}
}

func TestMarkingMessages(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	// Marking advances the cursor, so start away from the last message.
	a.pane.Move(-4)
	a.feed(t, "<C-v><C-v>")
	if got := a.msgMarks.len(); got != 2 {
		t.Fatalf("%d messages marked, want 2", got)
	}
	if got := len(a.markedMessages()); got != 2 {
		t.Errorf("markedMessages returned %d", got)
	}
	// And with nothing marked it falls back to the cursor, so every action
	// works the same whether or not anything is selected.
	a.clearMarks()
	if got := len(a.markedMessages()); got != 1 {
		t.Errorf("with no marks, markedMessages returned %d, want the one under the cursor", got)
	}
}

func TestMarkedMessagesComeBackInOrder(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.pane.Move(-3)
	a.feed(t, "<C-v>")
	a.pane.Move(-2)
	a.feed(t, "<C-v>")

	got := a.markedMessages()
	if len(got) != 2 {
		t.Fatalf("%d marked", len(got))
	}
	if !got[0].TS.Before(got[1].TS) {
		t.Error("marked messages came back in click order rather than in time order")
	}
}

// --- the chat drawer ---------------------------------------------------------

func TestExportWritesAFilePerChat(t *testing.T) {
	a := newTestApp(t)
	t.Setenv("HOME", a.dir)
	a.feed(t, "<C-v><C-v>")

	if err := a.reg.Run("chat.export", action.Context{}); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if n := a.calls("messages export"); n != 2 {
		t.Errorf("export ran %d times for two marked chats", n)
	}
	if !a.called("--output") {
		t.Error("export was not given a file to write")
	}
}

func TestFavouriteTagsTheContact(t *testing.T) {
	a := newTestApp(t)
	if err := a.reg.Run("chat.favourite_toggle", action.Context{}); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if !a.called("contacts tags add") || !a.called("--tag favourite") {
		t.Error("favouriting did not tag the contact")
	}
}

func TestBlockingSaysWhatItCannotDo(t *testing.T) {
	// wacli has no block command. Saying so is better than a silent failure
	// or a menu entry that lies.
	a := newTestApp(t)
	err := a.reg.Run("chat.block", action.Context{})
	if err == nil {
		t.Fatal("blocking reported success")
	}
	if !strings.Contains(err.Error(), "phone") {
		t.Errorf("the error does not say where to do it instead: %v", err)
	}
}

func TestDisappearingSaysWhatItCannotDo(t *testing.T) {
	a := newTestApp(t)
	err := a.reg.Run("chat.disappearing", action.Context{})
	if err == nil || !strings.Contains(err.Error(), "phone") {
		t.Errorf("err = %v", err)
	}
}

func TestTheAddressBookOpensAndPicksAChat(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, "contacts"); err != nil {
		t.Fatal(err)
	}
	if !a.picker.IsOpen() {
		t.Fatal("the address book did not open")
	}
	a.picker.SetQuery("Beka")
	if a.picker.Len() == 0 {
		t.Fatal("no contact matched")
	}
	if err := a.picker.Accept(); err != nil {
		t.Fatal(err)
	}
	if got := a.pane.Chat().JID.String(); got != "b@s.whatsapp.net" {
		t.Errorf("opened %s", got)
	}
}

func TestAliasRenamesLocally(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, "alias Nickname"); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if !a.called("contacts alias set") || !a.called("--alias Nickname") {
		t.Error("the alias was not set")
	}
}

func TestTagAndUntag(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, "tag work"); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if !a.called("contacts tags add") {
		t.Error("the tag was not added")
	}
	if err := a.command(t, "untag work"); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if !a.called("contacts tags rm") {
		t.Error("the tag was not removed")
	}
}

func TestMarkReadOnACommand(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, "mark read"); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if !a.called("chats mark-read") {
		t.Error("nothing was marked read")
	}
	if err := a.command(t, "mark sideways"); err == nil {
		t.Error("an unknown mark was accepted")
	}
}

func TestClearRemovesTheLocalCopy(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, "clear"); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if !a.called("chats cleanup") {
		t.Error("nothing was cleared")
	}
}

func TestContactsCanBeMarkedAndHandedToTheChatActions(t *testing.T) {
	// The third place a selection is wanted. Opening five conversations at
	// once is not a thing anybody wants, so the marks become the chat-list
	// selection and the drawer takes it from there.
	a := newTestApp(t)
	if err := a.command(t, "contacts"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "<C-v>")
	a.feed(t, "<C-v>")
	if got := a.picker.MarkCount(); got != 2 {
		t.Fatalf("%d contacts marked, want 2", got)
	}
	if !strings.Contains(a.picker.View(a.styles, 60, 10), "✓") {
		t.Error("a marked contact is not drawn as marked")
	}

	a.feed(t, "<CR>")
	if got := a.chatMarks.len(); got != 2 {
		t.Fatalf("%d chats selected after accepting, want 2", got)
	}
	if a.Focus() != FocusList {
		t.Errorf("focus = %v, want the list where the actions apply", a.Focus())
	}

	if err := a.reg.Run("chat.mark_read", action.Context{}); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if n := a.calls("chats mark-read"); n != 2 {
		t.Errorf("mark-read ran %d times, want one per selected contact", n)
	}
}

func TestEscapeInThePickerClearsMarksBeforeClosing(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, "contacts"); err != nil {
		t.Fatal(err)
	}
	a.feed(t, "<C-v>")
	a.feed(t, "<Esc>")
	if !a.picker.IsOpen() {
		t.Error("escape closed the picker instead of dropping the marks")
	}
	if a.picker.MarkCount() != 0 {
		t.Error("the marks survived")
	}
	a.feed(t, "<Esc>")
	if a.picker.IsOpen() {
		t.Error("a second escape did not close it")
	}
}

func TestOneContactStillJustOpensTheChat(t *testing.T) {
	a := newTestApp(t)
	if err := a.command(t, "contacts"); err != nil {
		t.Fatal(err)
	}
	a.picker.SetQuery("Beka")
	a.feed(t, "<CR>")
	if got := a.pane.Chat().JID.String(); got != "b@s.whatsapp.net" {
		t.Errorf("opened %q", got)
	}
}

// --- the marked messages, acted on together ---------------------------------

func TestCopyingSeveralMarkedMessages(t *testing.T) {
	a := newTestApp(t)
	clip := &terminalClipboard{}
	a.clip = clip
	a.feed(t, "<Tab>")
	a.pane.Move(-3)
	sel, _ := a.pane.Selected()
	a.pane.SetTextForTest(sel.ID, "first one")
	a.feed(t, "<C-v>")
	sel, _ = a.pane.Selected()
	a.pane.SetTextForTest(sel.ID, "second one")
	a.feed(t, "<C-v>")

	if err := a.reg.Run("msg.copy", action.Context{}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(clip.wrote, "first one") || !strings.Contains(clip.wrote, "second one") {
		t.Errorf("the clipboard holds %q", clip.wrote)
	}
	if !strings.Contains(clip.wrote, "\n\n") {
		t.Error("the messages ran together with no gap between them")
	}
}

func TestForwardingSeveralMarkedMessages(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.pane.Move(-3)
	a.feed(t, "<C-v><C-v>")

	if err := a.reg.Run("msg.forward", action.Context{}); err != nil {
		t.Fatal(err)
	}
	if !a.picker.IsOpen() {
		t.Fatal("the forward picker did not open")
	}
	a.picker.SetQuery("Beka")
	if err := a.picker.Accept(); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if n := a.calls("messages forward"); n != 2 {
		t.Errorf("forward ran %d times for two marked messages", n)
	}
}

func TestDeletingSeveralMarkedMessages(t *testing.T) {
	a := newTestApp(t)
	a.feed(t, "<Tab>")
	a.pane.Move(-3)
	a.feed(t, "<C-v><C-v>")

	if err := a.reg.Run("msg.delete", action.Context{}); err != nil {
		t.Fatal(err)
	}
	a.run(a.takeCmd())
	if n := a.calls("messages delete"); n != 2 {
		t.Errorf("delete ran %d times for two marked messages", n)
	}
}

func TestOneMessageStillActsOnItsOwn(t *testing.T) {
	// With nothing marked every one of these works on the cursor, so there is
	// nothing new to learn.
	a := newTestApp(t)
	clip := &terminalClipboard{}
	a.clip = clip
	a.feed(t, "<Tab>")
	sel, _ := a.pane.Selected()
	a.pane.SetTextForTest(sel.ID, "just this one")

	if err := a.reg.Run("msg.copy", action.Context{}); err != nil {
		t.Fatal(err)
	}
	if clip.wrote != "just this one" {
		t.Errorf("the clipboard holds %q", clip.wrote)
	}
}
