package ui

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
)

// The file browser.
//
// ":attach <path>" is the right tool when you know the path. When you do not,
// typing one blind is the worst way to find a file, so this walks directories
// in the picker that is already used for chats and reactions: a directory
// opens, a file attaches.

// attachDirKey is where the browser opens next time, so a second attachment
// from the same folder does not start again from home.
func (a *App) attachDir() string {
	if a.lastAttachDir != "" {
		if fi, err := os.Stat(a.lastAttachDir); err == nil && fi.IsDir() {
			return a.lastAttachDir
		}
	}
	if home, err := os.UserHomeDir(); err == nil {
		return home
	}
	return "."
}

// openFileBrowser shows a directory, and keeps showing directories until
// something that is not one is chosen.
func (a *App) openFileBrowser(dir string) error {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return err
	}

	// Directories first, then files, each alphabetically: the order a file
	// manager uses, and the one the hand expects when scrolling. Hidden
	// entries sink to the bottom of their group - a home directory holds forty
	// dot-directories and none of them is what you came to attach - and the
	// picker's filter still finds them by name.
	sort.Slice(entries, func(i, j int) bool {
		a, b := entries[i], entries[j]
		if a.IsDir() != b.IsDir() {
			return a.IsDir()
		}
		if ah, bh := hidden(a.Name()), hidden(b.Name()); ah != bh {
			return bh
		}
		return strings.ToLower(a.Name()) < strings.ToLower(b.Name())
	})

	items := make([]PickerItem, 0, len(entries)+1)
	if parent := filepath.Dir(dir); parent != dir {
		items = append(items, PickerItem{Label: "../", Value: parent})
	}
	for _, e := range entries {
		name := e.Name()
		full := filepath.Join(dir, name)
		if e.IsDir() {
			items = append(items, PickerItem{Label: name + "/", Value: full})
			continue
		}
		detail := ""
		if fi, err := e.Info(); err == nil {
			detail = media.HumanSize(fi.Size())
		}
		items = append(items, PickerItem{Label: name, Value: full, Detail: detail})
	}

	a.lastAttachDir = dir
	a.picker.Open("attach — "+shortenPath(dir), items, func(it PickerItem) error {
		fi, err := os.Stat(it.Value)
		if err != nil {
			return err
		}
		if fi.IsDir() {
			// Straight back into the picker, one level along. Closing and
			// reopening is what makes walking a tree feel like walking.
			return a.openFileBrowser(it.Value)
		}
		a.composer.Attach(it.Value)
		a.setFocus(FocusComposer)
		a.setStatus("attached " + filepath.Base(it.Value) + "; press enter to send")
		return nil
	})
	return nil
}

// hidden is the unix rule, which is the only rule here.
func hidden(name string) bool { return strings.HasPrefix(name, ".") }

// shortenPath writes a path the way a shell prompt does.
func shortenPath(p string) string {
	if home, err := os.UserHomeDir(); err == nil && strings.HasPrefix(p, home) {
		return "~" + strings.TrimPrefix(p, home)
	}
	return p
}
