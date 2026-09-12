package ui

import "fmt"

// Clipboard is the system clipboard, as the interface needs it.
//
// An interface rather than the concrete type so tests can assert on what was
// copied without touching the real clipboard, and so a build with no clipboard
// at all still compiles.
type Clipboard interface {
	Write(text string) error
	Read() (string, error)
}

// noClipboard stands in when none was supplied. It refuses rather than
// pretending, so the status line can say the copy did not happen.
type noClipboard struct{}

func (noClipboard) Write(string) error { return fmt.Errorf("no clipboard configured") }
func (noClipboard) Read() (string, error) {
	return "", fmt.Errorf("no clipboard configured")
}
