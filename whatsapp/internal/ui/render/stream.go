package render

import (
	"time"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
)

// Line is one rendered terminal row, tagged with what produced it so the pane
// can map a screen row back to a message.
type Line struct {
	Text string
	// MessageIndex is the message this row belongs to, or -1 for a separator.
	MessageIndex int
	IsSeparator  bool
}

// Stream renders a conversation: day separators, then each message's bubble,
// with a blank row between messages so the boxes do not run together.
//
// Messages must be oldest first.
func Stream(msgs []domain.Message, o Options, daySeparatorLayout string) []Line {
	var (
		out     []Line
		lastDay time.Time
		haveDay bool
	)
	for i, m := range msgs {
		day := startOfDay(m.TS)
		if !haveDay || !day.Equal(lastDay) {
			out = append(out, Line{
				Text:         DaySeparator(m.TS, o, daySeparatorLayout),
				MessageIndex: -1,
				IsSeparator:  true,
			})
			lastDay, haveDay = day, true
		}

		for _, l := range Bubble(m, o) {
			out = append(out, Line{Text: l, MessageIndex: i})
		}
		if i < len(msgs)-1 {
			out = append(out, Line{Text: "", MessageIndex: i})
		}
	}
	return out
}

func startOfDay(t time.Time) time.Time {
	y, m, d := t.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, t.Location())
}

// FirstRowOf finds the first screen row belonging to a message.
func FirstRowOf(lines []Line, index int) int {
	for i, l := range lines {
		if !l.IsSeparator && l.MessageIndex == index {
			return i
		}
	}
	return -1
}

// LastRowOf finds the last screen row belonging to a message.
func LastRowOf(lines []Line, index int) int {
	last := -1
	for i, l := range lines {
		if !l.IsSeparator && l.MessageIndex == index {
			last = i
		}
	}
	return last
}
