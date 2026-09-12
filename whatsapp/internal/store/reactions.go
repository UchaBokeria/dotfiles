package store

import "github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"

// foldReactions removes reaction rows from a conversation and attaches them to
// the messages they react to.
//
// WhatsApp sends a reaction as a message of its own, and wacli stores it that
// way: a row with reaction_to_id set and display_text "Reacted 👍 to message".
// Rendered naively that produces a bubble sitting on top of the conversation
// saying nothing useful, which is exactly what it looked like.
//
// Removing a reaction is also a reaction - one with an empty emoji - so the
// last one from a given person wins rather than accumulating.
func foldReactions(msgs []domain.Message) []domain.Message {
	// Where each message ended up, so a reaction can find its target.
	at := make(map[string]int, len(msgs))
	out := make([]domain.Message, 0, len(msgs))

	for _, m := range msgs {
		if m.IsReaction() {
			continue
		}
		at[m.ID] = len(out)
		out = append(out, m)
	}

	for _, m := range msgs {
		if !m.IsReaction() {
			continue
		}
		i, ok := at[m.ReactionTo]
		if !ok {
			// The target is outside the loaded window. Dropping it is right:
			// the reaction is meaningless without the message it is on, and
			// showing it alone is what the bug looked like.
			continue
		}
		out[i].Reactions = ApplyReaction(out[i].Reactions, domain.Reaction{
			Emoji:  m.ReactionEmoji,
			By:     m.SenderJID,
			ByName: m.SenderName,
			FromMe: m.FromMe,
			At:     m.TS,
		})
	}
	return out
}

// ApplyReaction replaces whatever this person had reacted with before. An
// empty emoji removes their reaction entirely, which is how WhatsApp spells
// "un-react".
//
// Exported because the interface applies a reaction the moment it is sent,
// rather than waiting for the sync process to write the row.
func ApplyReaction(existing []domain.Reaction, r domain.Reaction) []domain.Reaction {
	key := r.By.String()
	if r.FromMe {
		key = "\x00me"
	}

	out := existing[:0]
	for _, e := range existing {
		k := e.By.String()
		if e.FromMe {
			k = "\x00me"
		}
		if k == key {
			continue
		}
		out = append(out, e)
	}
	if r.Emoji == "" {
		return out
	}
	return append(out, r)
}
