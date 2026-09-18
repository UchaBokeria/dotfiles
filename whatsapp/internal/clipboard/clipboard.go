// Package clipboard puts text on the system clipboard.
//
// Three mechanisms, tried in order, because no single one works everywhere:
//
//   - a helper binary (wl-copy, xclip, xsel) when the session has one. This is
//     the only mechanism that reliably survives tmux, which by default has
//     allow-passthrough off and will swallow an escape sequence aimed at the
//     terminal underneath it.
//   - OSC 52, written to the terminal. Works over SSH and in a bare terminal
//     with no helper installed, which is the case wa cannot otherwise serve.
//   - nothing, reported as an error rather than silently dropped, so the
//     interface can say the copy did not happen.
package clipboard

import (
	"encoding/base64"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"sync"
)

// helper is an external clipboard program.
type helper struct {
	name string
	args []string
	// read holds the arguments for reading back, empty when it cannot.
	read []string
}

// helpers in preference order. wl-copy first: this is a Wayland rice.
var helpers = []helper{
	{name: "wl-copy", args: nil, read: []string{"--no-newline"}},
	{name: "xclip", args: []string{"-selection", "clipboard"}, read: []string{"-selection", "clipboard", "-o"}},
	{name: "xsel", args: []string{"--clipboard", "--input"}, read: []string{"--clipboard", "--output"}},
	{name: "pbcopy", args: nil},
}

// Clipboard writes and reads the system clipboard.
type Clipboard struct {
	once    sync.Once
	found   *helper
	out     io.Writer
	tmux    bool
	lastErr error
}

// New returns a clipboard writing OSC 52 to out when no helper is available.
// Pass os.Stdout in production.
func New(out io.Writer) *Clipboard {
	return &Clipboard{out: out, tmux: os.Getenv("TMUX") != ""}
}

func (c *Clipboard) detect() {
	c.once.Do(func() {
		for i := range helpers {
			if _, err := exec.LookPath(helpers[i].name); err == nil {
				c.found = &helpers[i]
				return
			}
		}
	})
}

// Write puts text on the clipboard.
func (c *Clipboard) Write(text string) error {
	if text == "" {
		return nil
	}
	c.detect()

	if c.found != nil {
		cmd := exec.Command(c.found.name, c.found.args...)
		cmd.Stdin = strings.NewReader(text)
		if err := cmd.Run(); err == nil {
			return nil
		} else {
			c.lastErr = err
		}
	}

	if c.out == nil {
		return fmt.Errorf("no clipboard: install wl-copy or xclip")
	}
	if _, err := io.WriteString(c.out, c.osc52(text)); err != nil {
		return err
	}
	return nil
}

// osc52 builds the escape sequence, wrapped for tmux when running inside it.
//
// Without the wrapper tmux consumes the sequence itself instead of forwarding
// it, so the copy silently does nothing. The wrapper only helps when tmux has
// allow-passthrough on; when it does not, the helper binary above is the only
// thing that works, which is why it is tried first.
func (c *Clipboard) osc52(text string) string {
	payload := base64.StdEncoding.EncodeToString([]byte(text))
	seq := "\x1b]52;c;" + payload + "\x07"
	if !c.tmux || tmuxForwardsClipboard() {
		// tmux with set-clipboard on takes the sequence itself, copies into
		// its own buffer and passes it outwards. Wrapping it in passthrough
		// there would skip tmux's buffer and need allow-passthrough besides.
		return seq
	}
	return "\x1bPtmux;" + strings.ReplaceAll(seq, "\x1b", "\x1b\x1b") + "\x1b\\"
}

// tmuxForwardsClipboard reports whether tmux will carry an OSC 52 outwards on
// its own. Asked once: it is a subprocess, and copying happens on a keystroke.
var tmuxForwardsClipboard = sync.OnceValue(func() bool {
	out, err := exec.Command("tmux", "show", "-gv", "set-clipboard").Output()
	if err != nil {
		return false
	}
	switch strings.TrimSpace(string(out)) {
	case "on", "external":
		return true
	}
	return false
})

// Escape returns the sequence that copies text through the terminal, and
// whether that is the mechanism in use.
//
// Kept for tests and for callers that want to know which mechanism a copy will
// take. The sequence itself goes out through Write, on the shared terminal
// writer: emitting it as part of a frame instead loses every copy the renderer
// decides is a repeat of the frame already on screen.
func (c *Clipboard) Escape(text string) (string, bool) {
	if text == "" {
		return "", false
	}
	c.detect()
	if c.found != nil {
		return "", false
	}
	return c.osc52(text), true
}

// Read returns the clipboard's contents. OSC 52 cannot read, so without a
// helper this reports an error rather than an empty string, which the caller
// would otherwise paste as nothing.
func (c *Clipboard) Read() (string, error) {
	c.detect()
	if c.found == nil || len(c.found.read) == 0 {
		return "", fmt.Errorf("cannot read the clipboard without wl-paste, xclip or xsel")
	}
	name := c.found.name
	if name == "wl-copy" {
		name = "wl-paste"
	}
	out, err := exec.Command(name, c.found.read...).Output()
	if err != nil {
		return "", err
	}
	return string(out), nil
}

// Available reports which mechanism will be used, for wa doctor.
func (c *Clipboard) Available() string {
	c.detect()
	if c.found != nil {
		return c.found.name
	}
	if c.tmux {
		return "OSC 52 through tmux (needs `set -g allow-passthrough on`)"
	}
	return "OSC 52"
}
