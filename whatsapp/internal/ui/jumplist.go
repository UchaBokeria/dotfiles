package ui

import "github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"

// maxJumps bounds the jumplist. Vim's default is a hundred, and there is no
// reason to differ.
const maxJumps = 100

// Jump is a remembered position.
type Jump struct {
	Chat      domain.JID
	MessageID string
}

// Jumplist is ctrl-o and ctrl-i.
//
// It spans chats, which is the point: with a hundred conversations, jumping
// back to where you were is more often "the other chat" than "further up this
// one".
type Jumplist struct {
	entries []Jump
	// pos is where in the list ctrl-o/ctrl-i currently sit. It equals
	// len(entries) when no traversal is in progress.
	pos int
}

// Push records a position. A repeat of the current entry is ignored, and a new
// push after traversing truncates the forward history, as in vim.
func (j *Jumplist) Push(chat domain.JID, messageID string) {
	if chat.IsZero() {
		return
	}
	e := Jump{Chat: chat, MessageID: messageID}

	if j.pos < len(j.entries) {
		j.entries = j.entries[:j.pos]
	}
	if n := len(j.entries); n > 0 && j.entries[n-1] == e {
		j.pos = n
		return
	}
	j.entries = append(j.entries, e)
	if len(j.entries) > maxJumps {
		j.entries = j.entries[len(j.entries)-maxJumps:]
	}
	j.pos = len(j.entries)
}

// Back steps to an older position.
func (j *Jumplist) Back() (Jump, bool) {
	if j.pos == 0 {
		return Jump{}, false
	}
	j.pos--
	return j.entries[j.pos], true
}

// Forward steps to a newer position.
func (j *Jumplist) Forward() (Jump, bool) {
	if j.pos+1 >= len(j.entries) {
		return Jump{}, false
	}
	j.pos++
	return j.entries[j.pos], true
}

// Len is how many positions are remembered.
func (j *Jumplist) Len() int { return len(j.entries) }
