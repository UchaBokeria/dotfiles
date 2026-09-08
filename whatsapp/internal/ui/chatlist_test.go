package ui

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/ui/render"
)

func newList(t *testing.T, s *fakeStore, w, h int) *ChatList {
	t.Helper()
	c := NewChatList(s, plainStyles(t), w, h)
	if err := c.Load(context.Background()); err != nil {
		t.Fatal(err)
	}
	return c
}

func TestListLoadsAndSelectsTheFirstRow(t *testing.T) {
	s := newFakeStore(
		chat(t, "Ana", "a@s.whatsapp.net"),
		chat(t, "Beka", "b@s.whatsapp.net"),
	)
	c := newList(t, s, 34, 10)

	if c.Len() != 2 {
		t.Fatalf("loaded %d chats, want 2", c.Len())
	}
	got, ok := c.Selected()
	if !ok || got.Name != "Ana" {
		t.Errorf("selected = %v (%v), want Ana", got.Name, ok)
	}
}

func TestSearchFiltersIncrementally(t *testing.T) {
	s := newFakeStore(
		chat(t, "Ana", "a@s.whatsapp.net"),
		chat(t, "Beka", "b@s.whatsapp.net"),
		chat(t, "Nika", "n@s.whatsapp.net"),
		chat(t, "Nino", "o@s.whatsapp.net"),
	)
	c := newList(t, s, 34, 10)

	c.SetSearch("ni")
	got := chatNames(c.Rows())
	if len(got) != 2 || got[0] != "Nika" || got[1] != "Nino" {
		t.Errorf("search \"ni\" = %v, want [Nika Nino]", got)
	}
	c.SetSearch("")
	if c.Len() != 4 {
		t.Errorf("clearing the search left %d rows, want 4", c.Len())
	}
}

func TestSearchIsCaseInsensitive(t *testing.T) {
	s := newFakeStore(chat(t, "Ana", "a@s.whatsapp.net"), chat(t, "beka", "b@s.whatsapp.net"))
	c := newList(t, s, 34, 10)
	c.SetSearch("BEK")
	if c.Len() != 1 {
		t.Errorf("case-insensitive search failed: %v", chatNames(c.Rows()))
	}
}

func TestSearchMatchesTheSnippetAndNumber(t *testing.T) {
	ana := chat(t, "Ana", "995111@s.whatsapp.net")
	ana.LastSnippet = "about the deployment"
	s := newFakeStore(ana, chat(t, "Beka", "b@s.whatsapp.net"))
	c := newList(t, s, 34, 10)

	c.SetSearch("deploy")
	if c.Len() != 1 {
		t.Errorf("searching the snippet failed: %v", chatNames(c.Rows()))
	}
	c.SetSearch("995111")
	if c.Len() != 1 {
		t.Errorf("searching the number failed: %v", chatNames(c.Rows()))
	}
}

func TestFilters(t *testing.T) {
	s := newFakeStore(
		chat(t, "Ana", "a@s.whatsapp.net"),
		chat(t, "Beka", "b@s.whatsapp.net", unread(3)),
		chat(t, "Cezar", "c@s.whatsapp.net", pinned()),
		chat(t, "Team", "1@g.us"),
		chat(t, "Dato", "d@s.whatsapp.net", mutedFor(time.Hour)),
		chat(t, "Old", "e@s.whatsapp.net", archived()),
	)
	c := newList(t, s, 34, 20)

	cases := []struct {
		filter string
		want   []string
	}{
		{"unread", []string{"Beka"}},
		{"pinned", []string{"Cezar"}},
		{"groups", []string{"Team"}},
		{"muted", []string{"Dato"}},
		{"archived", []string{"Old"}},
	}
	for _, tc := range cases {
		t.Run(tc.filter, func(t *testing.T) {
			if err := c.SetFilter(tc.filter); err != nil {
				t.Fatal(err)
			}
			got := chatNames(c.Rows())
			if len(got) != len(tc.want) || got[0] != tc.want[0] {
				t.Errorf("filter %q = %v, want %v", tc.filter, got, tc.want)
			}
		})
	}
}

func TestArchivedChatsAreHiddenByDefault(t *testing.T) {
	s := newFakeStore(
		chat(t, "Ana", "a@s.whatsapp.net"),
		chat(t, "Old", "e@s.whatsapp.net", archived()),
	)
	c := newList(t, s, 34, 10)
	if got := chatNames(c.Rows()); len(got) != 1 || got[0] != "Ana" {
		t.Errorf("default view = %v, want just Ana", got)
	}
}

func TestUnknownFilterIsRejected(t *testing.T) {
	c := newList(t, newFakeStore(), 34, 10)
	err := c.SetFilter("nonsense")
	if err == nil {
		t.Fatal("an unknown filter must be rejected so a typo at : is visible")
	}
	if !strings.Contains(err.Error(), "nonsense") {
		t.Errorf("err = %v, want it to name the filter", err)
	}
	if c.Filter() != "all" {
		t.Errorf("a rejected filter changed the state to %q", c.Filter())
	}
}

func TestCycleFilterVisitsEveryFilter(t *testing.T) {
	c := newList(t, newFakeStore(), 34, 10)
	seen := map[string]bool{}
	for i := 0; i < len(chatFilters); i++ {
		seen[c.Filter()] = true
		c.CycleFilter()
	}
	if len(seen) != len(chatFilters) {
		t.Errorf("the cycle visited %d of %d filters", len(seen), len(chatFilters))
	}
	if c.Filter() != "all" {
		t.Errorf("a full cycle should return to the start, got %q", c.Filter())
	}
}

func TestSelectionClampsAtBothEnds(t *testing.T) {
	s := newFakeStore(chat(t, "Ana", "a@s.whatsapp.net"), chat(t, "Beka", "b@s.whatsapp.net"))
	c := newList(t, s, 34, 10)

	c.Move(-5)
	if got, _ := c.Selected(); got.Name != "Ana" {
		t.Error("moving up past the top must clamp")
	}
	c.Move(99)
	if got, _ := c.Selected(); got.Name != "Beka" {
		t.Error("moving down past the bottom must clamp")
	}
}

func TestSelectionFollowsTheChatNotTheIndex(t *testing.T) {
	// A new message reorders the list. The cursor must stay on the same
	// conversation, not on the same row.
	early := time.Date(2026, 9, 8, 9, 0, 0, 0, time.UTC)
	late := time.Date(2026, 9, 8, 18, 0, 0, 0, time.UTC)

	s := newFakeStore(
		chat(t, "Ana", "a@s.whatsapp.net", at(late)),
		chat(t, "Beka", "b@s.whatsapp.net", at(early)),
	)
	c := newList(t, s, 34, 10)
	c.Move(1) // on Beka
	if got, _ := c.Selected(); got.Name != "Beka" {
		t.Fatalf("selected %v", got.Name)
	}

	// Beka sends something and jumps to the top.
	s.setChat(chat(t, "Beka", "b@s.whatsapp.net", at(late.Add(time.Hour))))
	if err := c.Invalidate(context.Background(), jid(t, "b@s.whatsapp.net")); err != nil {
		t.Fatal(err)
	}
	if got, _ := c.Selected(); got.Name != "Beka" {
		t.Errorf("the cursor followed the row instead of the chat: now on %v", got.Name)
	}
	if c.Index() != 0 {
		t.Errorf("Beka should now be the first row, index = %d", c.Index())
	}
}

func TestSelectionSurvivesAShrinkingList(t *testing.T) {
	s := newFakeStore(
		chat(t, "Ana", "a@s.whatsapp.net"),
		chat(t, "Beka", "b@s.whatsapp.net"),
		chat(t, "Nika", "n@s.whatsapp.net"),
	)
	c := newList(t, s, 34, 10)
	c.Move(2) // on Nika

	c.SetSearch("a") // Nika still matches
	if got, ok := c.Selected(); !ok || got.Name != "Nika" {
		t.Errorf("selected = %v, want Nika to be kept", got.Name)
	}
	c.SetSearch("beka") // Nika is gone
	if got, ok := c.Selected(); !ok || got.Name != "Beka" {
		t.Errorf("selected = %v (%v), want a valid fallback", got.Name, ok)
	}
}

func TestEmptyListHasNoSelection(t *testing.T) {
	c := newList(t, newFakeStore(), 34, 10)
	if _, ok := c.Selected(); ok {
		t.Error("an empty list must report no selection")
	}
	c.Move(1)
	c.Top()
	c.Bottom()
	c.HalfPage(1) // none of these may panic
}

func TestInvalidateAddsANewChat(t *testing.T) {
	s := newFakeStore(chat(t, "Ana", "a@s.whatsapp.net"))
	c := newList(t, s, 34, 10)

	s.setChat(chat(t, "New", "z@s.whatsapp.net"))
	if err := c.Invalidate(context.Background(), jid(t, "z@s.whatsapp.net")); err != nil {
		t.Fatal(err)
	}
	if c.Len() != 2 {
		t.Errorf("a first message from a new contact did not appear: %v", chatNames(c.Rows()))
	}
}

func TestInvalidateReadsOnlyTheNamedChat(t *testing.T) {
	s := newFakeStore(
		chat(t, "Ana", "a@s.whatsapp.net"),
		chat(t, "Beka", "b@s.whatsapp.net"),
	)
	c := newList(t, s, 34, 10)

	if err := c.Invalidate(context.Background(), jid(t, "b@s.whatsapp.net")); err != nil {
		t.Fatal(err)
	}
	if s.loadsOf("b@s.whatsapp.net") != 1 {
		t.Errorf("the named chat was read %d times, want 1", s.loadsOf("b@s.whatsapp.net"))
	}
	if s.loadsOf("a@s.whatsapp.net") != 0 {
		t.Error("an unrelated chat was re-read")
	}
}

func TestViewShowsMarkersAndBadges(t *testing.T) {
	s := newFakeStore(
		chat(t, "Ana", "a@s.whatsapp.net", pinned()),
		chat(t, "Beka", "b@s.whatsapp.net", unread(3)),
		chat(t, "Dato", "d@s.whatsapp.net", mutedFor(time.Hour)),
	)
	c := newList(t, s, 34, 10)
	v := c.View()

	for _, want := range []string{"Ana", "Beka", "Dato", "3", "▪", "○"} {
		if !strings.Contains(v, want) {
			t.Errorf("the view is missing %q:\n%s", want, v)
		}
	}
}

func TestViewNeverExceedsItsWidth(t *testing.T) {
	long := strings.Repeat("a very long chat name ", 6)
	s := newFakeStore(chat(t, long, "a@s.whatsapp.net", unread(1234)))
	for _, w := range []int{16, 24, 34, 60} {
		c := NewChatList(s, plainStyles(t), w, 6)
		c.Load(context.Background())
		for _, line := range strings.Split(c.View(), "\n") {
			if render.VisibleWidth(line) > w {
				t.Errorf("width %d: line is %d cells: %q", w, render.VisibleWidth(line), line)
			}
		}
	}
}

func TestViewHasOneRowPerVisibleLine(t *testing.T) {
	s := newFakeStore()
	for i := 0; i < 20; i++ {
		s.setChat(chat(t, string(rune('A'+i)), string(rune('a'+i))+"@s.whatsapp.net"))
	}
	c := newList(t, s, 34, 8)
	lines := strings.Split(c.View(), "\n")
	if len(lines) != 8 {
		t.Errorf("the pane rendered %d lines in a height of 8", len(lines))
	}
}

func TestScrollingKeepsTheCursorVisible(t *testing.T) {
	s := newFakeStore()
	for i := 0; i < 40; i++ {
		s.setChat(chat(t, string(rune('A'+i%26))+string(rune('0'+i/26)),
			string(rune('a'+i%26))+string(rune('0'+i/26))+"@s.whatsapp.net"))
	}
	c := newList(t, s, 34, 10)
	c.SetScrolloff(2)

	c.Bottom()
	sel, _ := c.Selected()
	if !strings.Contains(c.View(), sel.Name) {
		t.Errorf("the selected chat %q scrolled off the pane:\n%s", sel.Name, c.View())
	}
	c.Top()
	sel, _ = c.Selected()
	if !strings.Contains(c.View(), sel.Name) {
		t.Errorf("after gg the selection is off screen:\n%s", c.View())
	}
}

func TestHalfPageMovesAboutHalfTheHeight(t *testing.T) {
	s := newFakeStore()
	for i := 0; i < 30; i++ {
		s.setChat(chat(t, string(rune('A'+i%26))+string(rune('0'+i/26)),
			string(rune('a'+i%26))+string(rune('0'+i/26))+"@s.whatsapp.net"))
	}
	c := newList(t, s, 34, 11)
	before := c.Index()
	c.HalfPage(1)
	if moved := c.Index() - before; moved < 3 || moved > 7 {
		t.Errorf("ctrl-d moved %d rows in a height of 11", moved)
	}
}

func TestRelativeStamp(t *testing.T) {
	now := time.Date(2026, 9, 8, 15, 0, 0, 0, time.UTC)
	cases := []struct {
		when time.Time
		want string
	}{
		{time.Date(2026, 9, 8, 9, 30, 0, 0, time.UTC), "09:30"},
		{time.Date(2026, 9, 6, 9, 30, 0, 0, time.UTC), "Sun"},
		{time.Date(2026, 8, 1, 9, 30, 0, 0, time.UTC), "01/08"},
	}
	for _, c := range cases {
		if got := relativeStamp(c.when, now); got != c.want {
			t.Errorf("relativeStamp(%v) = %q, want %q", c.when, got, c.want)
		}
	}
}
