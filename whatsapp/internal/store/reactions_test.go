package store

import (
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

func msg(id, text string) domain.Message {
	return domain.Message{ID: id, Text: text, TS: time.Unix(1000, 0)}
}

func reaction(id, target, emoji string, fromMe bool) domain.Message {
	m := domain.Message{
		ID: id, ReactionTo: target, ReactionEmoji: emoji,
		FromMe: fromMe, TS: time.Unix(2000, 0),
		Text: "Reacted " + emoji + " to message",
	}
	m.SenderJID, _ = domain.ParseJID("someone@s.whatsapp.net")
	if fromMe {
		m.SenderJID, _ = domain.ParseJID("me@s.whatsapp.net")
	}
	return m
}

func TestReactionsAreRemovedFromTheStream(t *testing.T) {
	// A reaction rendered as a message is a bubble that covers the
	// conversation and says "Reacted 👍 to message".
	got := foldReactions([]domain.Message{
		msg("M1", "hello"),
		reaction("R1", "M1", "👍", true),
	})
	if len(got) != 1 {
		t.Fatalf("got %d messages, want the reaction folded away: %+v", len(got), got)
	}
	if got[0].ID != "M1" {
		t.Errorf("the surviving message is %q", got[0].ID)
	}
}

func TestReactionsAttachToTheirTarget(t *testing.T) {
	got := foldReactions([]domain.Message{
		msg("M1", "hello"),
		msg("M2", "world"),
		reaction("R1", "M2", "❤️", false),
	})
	if len(got[0].Reactions) != 0 {
		t.Error("the reaction landed on the wrong message")
	}
	if len(got[1].Reactions) != 1 || got[1].Reactions[0].Emoji != "❤️" {
		t.Errorf("M2 reactions = %+v", got[1].Reactions)
	}
}

func TestASecondReactionFromTheSamePersonReplacesTheFirst(t *testing.T) {
	got := foldReactions([]domain.Message{
		msg("M1", "hello"),
		reaction("R1", "M1", "👍", true),
		reaction("R2", "M1", "❤️", true),
	})
	if len(got[0].Reactions) != 1 {
		t.Fatalf("reactions = %+v, want one - changing your reaction is not adding one", got[0].Reactions)
	}
	if got[0].Reactions[0].Emoji != "❤️" {
		t.Errorf("kept %q, want the newer one", got[0].Reactions[0].Emoji)
	}
}

func TestAnEmptyEmojiRemovesTheReaction(t *testing.T) {
	got := foldReactions([]domain.Message{
		msg("M1", "hello"),
		reaction("R1", "M1", "👍", true),
		reaction("R2", "M1", "", true),
	})
	if len(got[0].Reactions) != 0 {
		t.Errorf("reactions = %+v, want none after un-reacting", got[0].Reactions)
	}
}

func TestDifferentPeopleBothCount(t *testing.T) {
	mine := reaction("R1", "M1", "👍", true)
	theirs := reaction("R2", "M1", "👍", false)
	got := foldReactions([]domain.Message{msg("M1", "hello"), mine, theirs})

	if len(got[0].Reactions) != 2 {
		t.Fatalf("reactions = %+v, want one each", got[0].Reactions)
	}
	if summary := got[0].ReactionSummary(); len(summary) != 1 || summary[0] != "👍2" {
		t.Errorf("summary = %v, want a single chip with a count", summary)
	}
}

func TestAReactionToAMessageOutsideTheWindowIsDropped(t *testing.T) {
	// Its target is further back than the loaded page. Showing it alone is
	// exactly the bug this folding exists to fix.
	got := foldReactions([]domain.Message{
		msg("M1", "hello"),
		reaction("R1", "M-older", "👍", false),
	})
	if len(got) != 1 {
		t.Errorf("got %+v, want the orphan reaction dropped", got)
	}
}

func TestMyReaction(t *testing.T) {
	got := foldReactions([]domain.Message{
		msg("M1", "hello"),
		reaction("R1", "M1", "👍", false),
		reaction("R2", "M1", "🔥", true),
	})
	if got[0].MyReaction() != "🔥" {
		t.Errorf("MyReaction = %q, want mine and not theirs", got[0].MyReaction())
	}
}

func TestOrderIsPreserved(t *testing.T) {
	got := foldReactions([]domain.Message{
		msg("M1", "one"), msg("M2", "two"), reaction("R1", "M1", "👍", true), msg("M3", "three"),
	})
	want := []string{"M1", "M2", "M3"}
	for i, w := range want {
		if got[i].ID != w {
			t.Fatalf("order = %v", messageIDs(got))
		}
	}
}

func messageIDs(ms []domain.Message) []string {
	out := make([]string, 0, len(ms))
	for _, m := range ms {
		out = append(out, m.ID)
	}
	return out
}
