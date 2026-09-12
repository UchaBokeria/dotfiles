package media

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Cache is where wa keeps attachments it downloaded itself.
//
// wacli's own `media download` takes the store lock, which the background sync
// holds, so it fails for as long as the client is running - and stopping the
// sync for every thumbnail would be absurd. Its error message points at the
// way out:
//
//	to download while sync is running, use --read-only with --output PATH
//	(it takes no store lock, and does not record the download)
//
// That is what wa does. The price is the second half of the sentence: the
// download is not recorded, so the store's local_path stays empty and wa has
// to remember the file itself. This type is that memory.
type Cache struct {
	dir string
}

// NewCache returns a cache rooted at dir.
func NewCache(dir string) *Cache { return &Cache{dir: dir} }

// Dir is where files are written.
func (c *Cache) Dir() string { return c.dir }

// Ensure creates the directory.
func (c *Cache) Ensure() error {
	if c.dir == "" {
		return nil
	}
	return os.MkdirAll(c.dir, 0o700)
}

// Path returns the cached file for a message, if one has been downloaded.
//
// wacli names the file `message-<id>.<ext>` and picks the extension from the
// mime type, so the extension is not known ahead of time and the lookup is by
// prefix.
func (c *Cache) Path(msgID string) (string, bool) {
	if c.dir == "" || msgID == "" {
		return "", false
	}
	matches, err := filepath.Glob(filepath.Join(c.dir, "message-"+msgID+".*"))
	if err != nil || len(matches) == 0 {
		return "", false
	}
	for _, m := range matches {
		if fi, err := os.Stat(m); err == nil && fi.Size() > 0 {
			return m, true
		}
	}
	return "", false
}

// DownloadArgs builds the wacli invocation that fetches an attachment without
// taking the store lock.
//
// The output is a directory of its own, one per message, because wacli names
// the file after the attachment rather than after the message: a photograph
// called "holiday.jpg" is written as "holiday.jpg". wa looks a file up by
// message id, so a download that landed under its own name was a download wa
// could not find - it fetched the file, drew a filename chip, and fetched it
// again next time.
//
// Fetch moves the file out afterwards. A directory per message is what makes
// that unambiguous: whatever is in there is the answer, whatever it is called.
func (c *Cache) DownloadArgs(chatJID, msgID string) []string {
	return []string{
		"media", "download",
		"--chat", chatJID,
		"--id", msgID,
		"--read-only",
		"--output", c.stagingDir(msgID) + string(os.PathSeparator),
	}
}

// stagingDir is where one message's download lands before it is named.
func (c *Cache) stagingDir(msgID string) string {
	return filepath.Join(c.dir, ".staging-"+msgID)
}

// Fetch downloads an attachment and files it under a name wa can find again.
//
// run is given the arguments and is expected to invoke wacli with them; the
// caller owns the context, the timeout and the error reporting.
func (c *Cache) Fetch(chatJID, msgID string, run func(args []string) error) (string, error) {
	if err := c.Ensure(); err != nil {
		return "", err
	}
	staging := c.stagingDir(msgID)
	// A directory left behind by an interrupted download would make the next
	// one ambiguous.
	_ = os.RemoveAll(staging)
	defer os.RemoveAll(staging)

	if err := run(c.DownloadArgs(chatJID, msgID)); err != nil {
		return "", err
	}
	return c.adopt(msgID)
}

// adopt moves the single downloaded file into the cache under the message id.
func (c *Cache) adopt(msgID string) (string, error) {
	entries, err := os.ReadDir(c.stagingDir(msgID))
	if err != nil {
		return "", fmt.Errorf("the download left nothing behind: %w", err)
	}
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		src := filepath.Join(c.stagingDir(msgID), e.Name())
		// An extension of some kind is required, not cosmetic: the cache finds
		// a file again by globbing "message-<id>.*", so a download named
		// without one would be filed where nothing would ever look for it.
		ext := filepath.Ext(e.Name())
		if ext == "" {
			ext = ".bin"
		}
		dst := filepath.Join(c.dir, "message-"+msgID+ext)
		if err := os.Rename(src, dst); err != nil {
			return "", err
		}
		return dst, nil
	}
	return "", fmt.Errorf("the download produced no file")
}

// Remove deletes a cached file.
func (c *Cache) Remove(msgID string) error {
	path, ok := c.Path(msgID)
	if !ok {
		return nil
	}
	return os.Remove(path)
}

// Size reports how much disk the cache is using, and how many files.
func (c *Cache) Size() (bytes int64, files int) {
	if c.dir == "" {
		return 0, 0
	}
	entries, err := os.ReadDir(c.dir)
	if err != nil {
		return 0, 0
	}
	for _, e := range entries {
		if e.IsDir() || !strings.HasPrefix(e.Name(), "message-") {
			continue
		}
		if fi, err := e.Info(); err == nil {
			bytes += fi.Size()
			files++
		}
	}
	return bytes, files
}

// Clear empties the cache, returning how many files were removed.
func (c *Cache) Clear() (int, error) {
	if c.dir == "" {
		return 0, nil
	}
	entries, err := os.ReadDir(c.dir)
	if err != nil {
		return 0, err
	}
	n := 0
	for _, e := range entries {
		if e.IsDir() || !strings.HasPrefix(e.Name(), "message-") {
			continue
		}
		if err := os.Remove(filepath.Join(c.dir, e.Name())); err == nil {
			n++
		}
	}
	return n, nil
}
