package store

import (
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// retryWindow is how long after an undecodable message the same sender's real
// one may follow and still be that message's retry.
const retryWindow = 60 * time.Second

// dropRetryPlaceholders removes the "(message)" stubs WhatsApp leaves when a
// message fails to decrypt on first delivery.
//
// The sender's device re-sends it a few seconds later and the real text
// arrives as a second row (seen: 12:28:53 stub, 12:29:10 text; 12:48:40 stub,
// 12:48:44 text). Drawn as they are, every such message showed a grey
// "a message wa cannot show" bubble above the message it was a stub for. A
// stub with no successor from the same sender is kept: that is a genuinely
// undecodable message and the bubble is the honest answer.
func dropRetryPlaceholders(msgs []domain.Message) []domain.Message {
	out := msgs[:0:0]
	for _, m := range msgs {
		if isStub(m) && hasRetry(msgs, m) {
			continue
		}
		out = append(out, m)
	}
	return out
}

func isStub(m domain.Message) bool {
	return m.Unsupported && m.Media == nil && m.Text == ""
}

func hasRetry(msgs []domain.Message, stub domain.Message) bool {
	for _, n := range msgs {
		if isStub(n) || n.FromMe != stub.FromMe || n.SenderJID != stub.SenderJID {
			continue
		}
		if d := n.TS.Sub(stub.TS); d >= 0 && d <= retryWindow {
			return true
		}
	}
	return false
}
