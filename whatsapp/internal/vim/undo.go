package vim

// Undo is a linear undo stack over a buffer.
//
// Deliberately linear rather than a branching tree. A tree earns its keep in a
// file you revisit; a chat draft is written once and sent, and the branches
// would be a feature nobody could see the point of.
type Undo struct {
	b       *Buffer
	past    []Snapshot
	future  []Snapshot
	current Snapshot
}

// NewUndo starts tracking a buffer.
func NewUndo(b *Buffer) *Undo {
	return &Undo{b: b, current: b.Snapshot()}
}

// Checkpoint records the buffer's state as an undo point. Call it before a
// change, not after: undoing should land on what was there beforehand.
func (u *Undo) Checkpoint() {
	snap := u.b.Snapshot()
	if snap.text() == u.current.text() {
		return // nothing changed since the last checkpoint
	}
	u.past = append(u.past, u.current)
	u.current = snap
	// A new edit abandons the redo branch, as in vim.
	u.future = nil
}

// Undo steps back. It reports whether anything happened.
func (u *Undo) Undo() bool {
	// Fold in any change made since the last checkpoint, so `u` after typing
	// undoes the typing rather than doing nothing.
	if snap := u.b.Snapshot(); snap.text() != u.current.text() {
		u.past = append(u.past, u.current)
		u.current = snap
		u.future = nil
	}
	if len(u.past) == 0 {
		return false
	}
	last := u.past[len(u.past)-1]
	u.past = u.past[:len(u.past)-1]
	u.future = append(u.future, u.current)
	u.current = last
	u.b.Restore(last)
	return true
}

// Redo steps forward. It reports whether anything happened.
func (u *Undo) Redo() bool {
	if len(u.future) == 0 {
		return false
	}
	next := u.future[len(u.future)-1]
	u.future = u.future[:len(u.future)-1]
	u.past = append(u.past, u.current)
	u.current = next
	u.b.Restore(next)
	return true
}

// Depth is how many undo steps are available, for :undolist.
func (u *Undo) Depth() int { return len(u.past) }
