package clipboard

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// Image support.
//
// Reading a picture off the clipboard is a different question from reading
// text: the clipboard holds several representations at once, and asking for
// the wrong one gets you the file's name, or a URL, or nothing. So the offered
// types are listed first and the best picture among them is asked for by name.
//
// Only the Wayland and X11 helpers can do this. OSC 52 carries text and
// nothing else, so a session with no helper cannot paste a picture at all -
// which is worth saying plainly rather than pasting an empty file.

// imageReader lists and fetches clipboard types.
type imageReader struct {
	bin  string
	list []string
	// get takes the mime type as its final argument.
	get []string
}

var imageReaders = []imageReader{
	{bin: "wl-paste", list: []string{"--list-types"}, get: []string{"--no-newline", "--type"}},
	{bin: "xclip", list: []string{"-selection", "clipboard", "-t", "TARGETS", "-o"},
		get: []string{"-selection", "clipboard", "-o", "-t"}},
}

// imageTypes are the picture formats worth asking for, best first. PNG leads
// because a screenshot tool puts one there and it is lossless.
var imageTypes = []string{"image/png", "image/jpeg", "image/webp", "image/gif", "image/bmp"}

// HasImage reports the mime type of a picture on the clipboard, if there is
// one.
func (c *Clipboard) HasImage() (string, bool) {
	r, ok := c.imageReader()
	if !ok {
		return "", false
	}
	offered, err := run(r.bin, r.list...)
	if err != nil {
		return "", false
	}
	have := strings.Fields(strings.ToLower(string(offered)))
	for _, want := range imageTypes {
		for _, got := range have {
			if got == want {
				return want, true
			}
		}
	}
	return "", false
}

// ReadImage writes the clipboard's picture into dir and returns the path.
//
// It is written to a file rather than returned as bytes because the only thing
// wa does with it is hand the path to wacli, and a picture large enough to be
// worth sending is large enough not to want a copy of in memory.
func (c *Clipboard) ReadImage(dir string) (string, error) {
	mime, ok := c.HasImage()
	if !ok {
		if _, canRead := c.imageReader(); !canRead {
			return "", fmt.Errorf("no clipboard helper that can read a picture (install wl-clipboard or xclip)")
		}
		return "", fmt.Errorf("no picture on the clipboard")
	}
	r, _ := c.imageReader()

	data, err := run(r.bin, append(append([]string{}, r.get...), mime)...)
	if err != nil {
		return "", fmt.Errorf("reading the clipboard: %w", err)
	}
	if len(data) == 0 {
		return "", fmt.Errorf("the clipboard offered a %s and then gave nothing", mime)
	}

	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", err
	}
	name := fmt.Sprintf("pasted-%d%s", time.Now().UnixNano(), extensionFor(mime))
	path := filepath.Join(dir, name)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		return "", err
	}
	return path, nil
}

// imageReader picks the helper that can read typed clipboard content.
func (c *Clipboard) imageReader() (imageReader, bool) {
	for _, r := range imageReaders {
		if _, err := exec.LookPath(r.bin); err == nil {
			return r, true
		}
	}
	return imageReader{}, false
}

func extensionFor(mime string) string {
	switch mime {
	case "image/jpeg":
		return ".jpg"
	case "image/webp":
		return ".webp"
	case "image/gif":
		return ".gif"
	case "image/bmp":
		return ".bmp"
	default:
		return ".png"
	}
}

// run executes a helper and returns what it wrote.
func run(bin string, args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	return exec.CommandContext(ctx, bin, args...).Output()
}
