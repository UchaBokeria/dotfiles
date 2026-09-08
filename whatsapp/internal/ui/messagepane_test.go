package ui

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/ui/render"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/vim"
)

func newPane(t *testing.T, s *fakeStore, chatID string, w, h int) *MessagePane {
	t.Helper()
	p := NewMessagePane(s, render.NewCache(256), plainStyles(t), w, h)
	c := chat(t, "Ana", chatID)
	s.setChat(c)
	if err := p.Open(context.Background(), c); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestOpenSelectsTheNewestMessage(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 30)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	m, ok := p.Selected()
	if !ok || m.ID != "M30" {
		t.Fatalf("selected = %q (%v), want the newest message", m.ID, ok)
	}
	if p.Count() != 30 {
		t.Errorf("loaded %d messages, want 30", p.Count())
	}
}

func TestOpenOfAnEmptyChat(t *testing.T) {
	p := newPane(t, newFakeStore(), "a@s.whatsapp.net", 60, 20)
	if _, ok := p.Selected(); ok {
		t.Error("an empty chat must report no selection")
	}
	p.Move(1)
	p.Bottom()
	p.HalfPage(1)
	if v := p.View(); v == "" {
		t.Error("an empty chat should still render a pane")
	}
}

func TestLoadOlderPrependsWithoutDuplicates(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 150)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	before := p.Count()
	n, err := p.LoadOlder(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if n == 0 {
		t.Fatal("LoadOlder returned nothing on a chat with 150 messages")
	}
	if p.Count() <= before {
		t.Errorf("count went from %d to %d", before, p.Count())
	}

	seen := map[string]bool{}
	for _, m := range p.Messages() {
		if seen[m.ID] {
			t.Fatalf("duplicate message %s after LoadOlder", m.ID)
		}
		seen[m.ID] = true
	}
}

func TestLoadOlderKeepsChronologicalOrder(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 150)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)
	p.LoadOlder(context.Background())

	all := p.Messages()
	for i := 1; i < len(all); i++ {
		if all[i].TS.Before(all[i-1].TS) {
			t.Fatalf("messages out of order at %d: %v before %v",
				i, all[i].TS, all[i-1].TS)
		}
	}
}

func TestLoadOlderStopsAtTheStartOfHistory(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 10)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	if !p.Exhausted() {
		t.Fatal("a short chat should be exhausted after the first page")
	}
	n, err := p.LoadOlder(context.Background())
	if err != nil || n != 0 {
		t.Errorf("LoadOlder at the start = %d, %v", n, err)
	}
}

func TestLoadOlderKeepsTheCursorOnTheSameMessage(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 150)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	before, _ := p.Selected()
	p.LoadOlder(context.Background())
	after, ok := p.Selected()
	if !ok || after.ID != before.ID {
		t.Errorf("the cursor moved from %s to %s when older messages were prepended",
			before.ID, after.ID)
	}
}

func TestMoveClampsAtBothEnds(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 5)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	p.Move(-100)
	if m, _ := p.Selected(); m.ID != "M1" {
		t.Errorf("after moving up past the start: %s", m.ID)
	}
	p.Move(100)
	if m, _ := p.Selected(); m.ID != "M5" {
		t.Errorf("after moving down past the end: %s", m.ID)
	}
}

func TestSearchFindsAndReportsFailure(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = []domain.Message{
		{RowID: 1, ID: "M1", TS: time.Unix(1000, 0), Text: "alpha"},
		{RowID: 2, ID: "M2", TS: time.Unix(2000, 0), Text: "beta"},
		{RowID: 3, ID: "M3", TS: time.Unix(3000, 0), Text: "gamma"},
	}
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	if !p.Search("alpha", false, true, true) {
		t.Error("searching backwards for alpha should succeed")
	}
	if m, _ := p.Selected(); m.ID != "M1" {
		t.Errorf("search landed on %s, want M1", m.ID)
	}
	if p.Search("omega", true, true, true) {
		t.Error("an absent pattern must report false rather than silently staying put")
	}
}

func TestSearchSmartCase(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = []domain.Message{
		{RowID: 1, ID: "M1", TS: time.Unix(1000, 0), Text: "Deploy"},
		{RowID: 2, ID: "M2", TS: time.Unix(2000, 0), Text: "deploy"},
	}
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	// Lower-case pattern with smartcase: both match.
	p.Search("deploy", true, true, true)
	if p.MatchCount() != 2 {
		t.Errorf("lower-case search matched %d, want both", p.MatchCount())
	}
	// A capital in the pattern makes it case-sensitive.
	p.Search("Deploy", true, true, true)
	if p.MatchCount() != 1 {
		t.Errorf("mixed-case search matched %d, want 1", p.MatchCount())
	}
}

func TestSearchWrapsAround(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = []domain.Message{
		{RowID: 1, ID: "M1", TS: time.Unix(1000, 0), Text: "hit"},
		{RowID: 2, ID: "M2", TS: time.Unix(2000, 0), Text: "miss"},
		{RowID: 3, ID: "M3", TS: time.Unix(3000, 0), Text: "hit"},
	}
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	p.Search("hit", true, true, true) // from M3, forward, wraps to M1
	if m, _ := p.Selected(); m.ID != "M1" {
		t.Errorf("wrapped search landed on %s, want M1", m.ID)
	}
	p.Next(true)
	if m, _ := p.Selected(); m.ID != "M3" {
		t.Errorf("n landed on %s, want M3", m.ID)
	}
}

func TestClearHighlight(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 3)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	p.Search("message", true, true, true)
	if !p.Highlighted() {
		t.Fatal("a search should highlight")
	}
	p.ClearHighlight()
	if p.Highlighted() {
		t.Error("Esc must clear the highlight")
	}
}

func TestOptimisticSendAppearsImmediately(t *testing.T) {
	p := newPane(t, newFakeStore(), "a@s.whatsapp.net", 60, 20)
	m := p.AddOptimistic("hello")

	if !strings.Contains(p.View(), "⧗") {
		t.Errorf("a pending message should render the pending glyph:\n%s", p.View())
	}
	got, ok := p.Selected()
	if !ok || got.ID != m.ID {
		t.Error("the cursor should follow an optimistic send")
	}
}

func TestOptimisticSendReconciles(t *testing.T) {
	p := newPane(t, newFakeStore(), "a@s.whatsapp.net", 60, 20)
	m := p.AddOptimistic("hello")

	if !p.Reconcile(m.ID, "3EB0REAL") {
		t.Fatal("Reconcile did not find the optimistic message")
	}
	got, _ := p.Selected()
	if got.ID != "3EB0REAL" || got.Local || got.Delivery != domain.Sent {
		t.Errorf("reconciled message = %+v", got)
	}
}

func TestFailedSendKeepsTheBubbleAndTheReason(t *testing.T) {
	p := newPane(t, newFakeStore(), "a@s.whatsapp.net", 60, 20)
	m := p.AddOptimistic("hello")

	p.FailOptimistic(m.ID, errors.New("network down"))
	got, ok := p.Selected()
	if !ok {
		t.Fatal("the failed message disappeared, taking the text with it")
	}
	if got.Delivery != domain.Failed || !strings.Contains(got.Err, "network down") {
		t.Errorf("failed message = %+v", got)
	}
}

func TestReceiptsOnlyMoveForwards(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = []domain.Message{
		{RowID: 1, ID: "M1", TS: time.Unix(1000, 0), FromMe: true, Text: "x", Delivery: domain.Sent},
	}
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	if !p.ApplyReceipt("M1", domain.Read) {
		t.Fatal("a read receipt was not applied")
	}
	if p.ApplyReceipt("M1", domain.Delivered) {
		t.Error("a late 'delivered' must not undo 'read'")
	}
	got, _ := p.Selected()
	if got.Delivery != domain.Read {
		t.Errorf("delivery = %v, want Read", got.Delivery)
	}
}

func TestRefreshKeepsUnreconciledSends(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 3)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 20)

	p.AddOptimistic("still sending")
	if err := p.Refresh(context.Background()); err != nil {
		t.Fatal(err)
	}
	found := false
	for _, m := range p.Messages() {
		if m.Local && m.Text == "still sending" {
			found = true
		}
	}
	if !found {
		t.Error("a refresh mid-send discarded the pending bubble")
	}
}

func TestViewFitsTheHeight(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 40)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 12)

	lines := strings.Split(p.View(), "\n")
	if len(lines) != 12 {
		t.Errorf("the pane rendered %d rows in a height of 12", len(lines))
	}
	for _, l := range lines {
		if render.VisibleWidth(l) > 60 {
			t.Errorf("row is %d cells wide: %q", render.VisibleWidth(l), l)
		}
	}
}

func TestSelectionStaysOnScreen(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = msgs(t, "a@s.whatsapp.net", 50)
	p := newPane(t, s, "a@s.whatsapp.net", 60, 12)

	for _, move := range []func(){p.Top, p.Bottom, func() { p.HalfPage(-1) }, func() { p.HalfPage(1) }} {
		move()
		sel, ok := p.Selected()
		if !ok {
			t.Fatal("no selection")
		}
		if !strings.Contains(p.View(), sel.Text) {
			t.Errorf("the selected message %q is off screen:\n%s", sel.Text, p.View())
		}
	}
}

func TestGutterNumbersOnlyTheFirstRowOfAMessage(t *testing.T) {
	s := newFakeStore()
	s.messages["a@s.whatsapp.net"] = []domain.Message{
		{RowID: 1, ID: "M1", TS: time.Unix(1000, 0),
			Text: strings.Repeat("a long wrapped message ", 6)},
	}
	p := newPane(t, s, "a@s.whatsapp.net", 50, 12)

	numbered := 0
	for _, l := range strings.Split(p.View(), "\n") {
		if strings.TrimSpace(l) == "" {
			continue
		}
		if head := strings.TrimSpace(l[:4]); head != "" {
			numbered++
		}
	}
	if numbered != 1 {
		t.Errorf("%d rows carry a gutter number; a wrapped message must be numbered once", numbered)
	}
}

// --- composer --------------------------------------------------------------

func TestDraftsAreKeptPerChat(t *testing.T) {
	c := NewComposer(plainStyles(t), 60)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	c.Buffer().SetText("hello ana")

	c.SwitchDraft(jid(t, "b@s.whatsapp.net"))
	if c.Text() != "" {
		t.Errorf("switching chats should show an empty draft, got %q", c.Text())
	}
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	if c.Text() != "hello ana" {
		t.Errorf("the draft for chat a was lost: %q", c.Text())
	}
}

func TestUndoStacksAreIndependentPerDraft(t *testing.T) {
	c := NewComposer(plainStyles(t), 60)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	c.Buffer().SetText("one")
	c.Undo().Checkpoint()
	c.Buffer().SetText("one two")

	c.SwitchDraft(jid(t, "b@s.whatsapp.net"))
	if c.Undo().Undo() {
		t.Error("a fresh draft must not undo into another chat's history")
	}
	if c.Text() != "" {
		t.Errorf("chat b's draft = %q", c.Text())
	}
}

func TestTakeClearsTheDraft(t *testing.T) {
	c := NewComposer(plainStyles(t), 60)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	c.Buffer().SetText("send me")

	if got := c.Take(); got != "send me" {
		t.Fatalf("Take = %q", got)
	}
	if c.Text() != "" {
		t.Error("Take must clear the draft")
	}
	if !c.Empty() {
		t.Error("the composer should report empty after Take")
	}
}

func TestTakeGivesAFreshUndoStack(t *testing.T) {
	// Undoing after a send must not resurrect the sent text into the box.
	c := NewComposer(plainStyles(t), 60)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	c.Buffer().SetText("sent already")
	c.Take()

	if c.Undo().Undo() {
		t.Error("u after sending walked back into the sent message")
	}
	if c.Text() != "" {
		t.Errorf("draft = %q after undo", c.Text())
	}
}

func TestRestorePutsTextBackAfterAFailedSend(t *testing.T) {
	c := NewComposer(plainStyles(t), 60)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	c.Buffer().SetText("did not go")
	text := c.Take()

	c.Restore(text)
	if c.Text() != "did not go" {
		t.Errorf("draft = %q, want the text back", c.Text())
	}
	cur := c.Buffer().Cursor()
	if cur.Col != len([]rune("did not go")) {
		t.Errorf("cursor = %+v, want it at the end for further typing", cur)
	}
}

func TestComposerEmptyIsWhitespaceAware(t *testing.T) {
	c := NewComposer(plainStyles(t), 60)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	c.Buffer().SetText("   \n  ")
	if !c.Empty() {
		t.Error("a draft of only whitespace should count as empty; sending it would post a blank message")
	}
}

func TestComposerGrowsAndIsCapped(t *testing.T) {
	c := NewComposer(plainStyles(t), 30)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	if got := c.Height(); got != 1 {
		t.Errorf("an empty composer is %d rows, want 1", got)
	}

	c.Buffer().SetText(strings.Repeat("word ", 60))
	if got := c.Height(); got < 2 {
		t.Errorf("a long draft did not grow the composer: %d rows", got)
	}
	if got := c.Height(); got > maxComposerHeight {
		t.Errorf("the composer grew to %d rows, past its cap of %d", got, maxComposerHeight)
	}
}

func TestComposerViewFitsTheWidth(t *testing.T) {
	c := NewComposer(plainStyles(t), 24)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	c.Buffer().SetText(strings.Repeat("hello ", 20))
	for _, l := range strings.Split(c.View(true), "\n") {
		if render.VisibleWidth(l) > 24 {
			t.Errorf("row is %d cells wide: %q", render.VisibleWidth(l), l)
		}
	}
}

func TestComposerShowsAPlaceholderWhenIdle(t *testing.T) {
	c := NewComposer(plainStyles(t), 40)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	if !strings.Contains(c.View(false), "write a message") {
		t.Errorf("an unfocused empty composer should prompt:\n%s", c.View(false))
	}
	c.Buffer().SetText("typing")
	if strings.Contains(c.View(false), "write a message") {
		t.Error("the placeholder survived once there was text")
	}
}

func TestComposerCursorColumnCountsDisplayCells(t *testing.T) {
	c := NewComposer(plainStyles(t), 40)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	c.Buffer().SetText("漢字ab")
	c.Buffer().SetCursor(vim.Pos{Line: 0, Col: 3})

	// Two double-width characters plus one narrow one, past a two-cell prompt.
	if got := c.CursorColumn(); got != 2+5 {
		t.Errorf("CursorColumn = %d, want %d", got, 2+5)
	}
}

func TestDraftCount(t *testing.T) {
	c := NewComposer(plainStyles(t), 40)
	c.SwitchDraft(jid(t, "a@s.whatsapp.net"))
	c.Buffer().SetText("unsent")
	c.SwitchDraft(jid(t, "b@s.whatsapp.net"))
	c.Buffer().SetText("   ")

	if got := c.DraftCount(); got != 1 {
		t.Errorf("DraftCount = %d, want 1 (whitespace is not a draft)", got)
	}
}
