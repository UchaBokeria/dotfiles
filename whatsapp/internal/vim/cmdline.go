package vim

import (
	"fmt"
	"sort"
	"strings"
)

// Command is a parsed : command.
type Command struct {
	// Name is the verb, without the leading colon or the trailing bang.
	Name string
	// Bang is the trailing "!", which by convention means "and persist" or
	// "and force".
	Bang bool
	Args []string
	// Raw is everything after the name, unsplit, for commands that take a
	// sentence rather than arguments - :grep and :send both do.
	Raw string
}

// ParseCommand reads a command line. A leading colon is optional so that the
// same parser serves both the prompt and a scripted command.
func ParseCommand(line string) (Command, error) {
	line = strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(line), ":"))
	if line == "" {
		return Command{}, fmt.Errorf("empty command")
	}

	name := line
	rest := ""
	if i := strings.IndexAny(line, " \t"); i >= 0 {
		name, rest = line[:i], strings.TrimSpace(line[i+1:])
	}

	c := Command{Raw: rest}
	if strings.HasSuffix(name, "!") {
		c.Bang = true
		name = strings.TrimSuffix(name, "!")
	}
	if name == "" {
		return Command{}, fmt.Errorf("%q has no command name", line)
	}
	c.Name = name

	args, err := splitArgs(rest)
	if err != nil {
		return Command{}, err
	}
	c.Args = args
	return c, nil
}

// splitArgs splits on whitespace, honouring double quotes so a chat name with
// a space in it can be passed as one argument.
func splitArgs(s string) ([]string, error) {
	var (
		out     []string
		cur     strings.Builder
		inQuote bool
		started bool
	)
	for i := 0; i < len(s); i++ {
		ch := s[i]
		switch {
		case ch == '"':
			inQuote = !inQuote
			started = true
		case ch == '\\' && i+1 < len(s):
			i++
			cur.WriteByte(s[i])
			started = true
		case (ch == ' ' || ch == '\t') && !inQuote:
			if started {
				out = append(out, cur.String())
				cur.Reset()
				started = false
			}
		default:
			cur.WriteByte(ch)
			started = true
		}
	}
	if inQuote {
		return nil, fmt.Errorf("unclosed quote")
	}
	if started {
		out = append(out, cur.String())
	}
	return out, nil
}

// CompleteCommand returns the candidates for a partially typed command line,
// sorted. It completes the command name only; argument completion belongs to
// the command, which knows what its arguments mean.
func CompleteCommand(line string, names []string) []string {
	// Only the left side is trimmed: a trailing space means the name is
	// settled and the user has moved on to the arguments.
	line = strings.TrimPrefix(strings.TrimLeft(line, " \t"), ":")
	if strings.ContainsAny(line, " \t") {
		return nil
	}
	var out []string
	for _, n := range names {
		if strings.HasPrefix(n, line) {
			out = append(out, n)
		}
	}
	sort.Strings(out)
	return out
}

// CompleteArg returns the candidates for the final argument of a command line.
func CompleteArg(line string, candidates []string) []string {
	fields := strings.Fields(line)
	prefix := ""
	if len(fields) > 0 && !strings.HasSuffix(line, " ") {
		prefix = fields[len(fields)-1]
	}
	var out []string
	for _, c := range candidates {
		if strings.HasPrefix(c, prefix) {
			out = append(out, c)
		}
	}
	sort.Strings(out)
	return out
}

// History is the : and / prompt history.
type History struct {
	items []string
	pos   int
	max   int
}

// NewHistory returns a history holding at most max entries.
func NewHistory(max int) *History {
	if max <= 0 {
		max = 200
	}
	return &History{max: max}
}

// Add records a line, skipping blanks and immediate repeats.
func (h *History) Add(line string) {
	line = strings.TrimSpace(line)
	if line == "" {
		h.pos = len(h.items)
		return
	}
	if n := len(h.items); n > 0 && h.items[n-1] == line {
		h.pos = len(h.items)
		return
	}
	h.items = append(h.items, line)
	if len(h.items) > h.max {
		h.items = h.items[len(h.items)-h.max:]
	}
	h.pos = len(h.items)
}

// Prev walks backwards through the history.
func (h *History) Prev() (string, bool) {
	if h.pos == 0 {
		return "", false
	}
	h.pos--
	return h.items[h.pos], true
}

// Next walks forwards, returning an empty string past the newest entry so the
// prompt clears rather than sticking on the last command.
func (h *History) Next() (string, bool) {
	if h.pos >= len(h.items) {
		return "", false
	}
	h.pos++
	if h.pos == len(h.items) {
		return "", true
	}
	return h.items[h.pos], true
}

// Reset puts the cursor back at the newest entry.
func (h *History) Reset() { h.pos = len(h.items) }

// Items lists the history oldest first.
func (h *History) Items() []string { return append([]string{}, h.items...) }
