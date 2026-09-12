package media

import (
	"errors"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestClassify(t *testing.T) {
	cases := []struct {
		mediaType, mime, name string
		want                  Kind
	}{
		{"image", "image/jpeg", "a.jpg", KindImage},
		{"video", "video/mp4", "a.mp4", KindVideo},
		// WhatsApp sends a GIF as an mp4; the media type is what separates it.
		{"gif", "video/mp4", "a.mp4", KindGIF},
		// A voice note is ogg/opus; music sent as a file is not.
		{"audio", "audio/ogg; codecs=opus", "a.ogg", KindVoice},
		{"audio", "audio/mpeg", "song.mp3", KindAudio},
		{"document", "application/pdf", "a.pdf", KindDocument},
		// A picture attached as a file is still a picture.
		{"document", "image/png", "shot.png", KindImage},
		{"document", "text/plain", "notes.txt", KindDocument},
		{"", "", "a.jpg", KindImage},
		{"", "", "unknown.xyz", KindUnknown},
	}
	for _, c := range cases {
		if got := Classify(c.mediaType, c.mime, c.name); got != c.want {
			t.Errorf("Classify(%q, %q, %q) = %v, want %v",
				c.mediaType, c.mime, c.name, got, c.want)
		}
	}
}

func TestHumanSize(t *testing.T) {
	for _, c := range []struct {
		in   int64
		want string
	}{{512, "512B"}, {2048, "2.0KB"}, {1258291, "1.2MB"}} {
		if got := HumanSize(c.in); got != c.want {
			t.Errorf("HumanSize(%d) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestHumanDuration(t *testing.T) {
	for _, c := range []struct {
		in   float64
		want string
	}{{0, ""}, {5, "0:05"}, {65, "1:05"}, {3725, "1:02:05"}} {
		if got := HumanDuration(c.in); got != c.want {
			t.Errorf("HumanDuration(%v) = %q, want %q", c.in, got, c.want)
		}
	}
}

// writePNG makes a test image of a solid colour with a distinct top half.
func writePNG(t *testing.T, w, h int) string {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			if y < h/2 {
				img.Set(x, y, color.RGBA{R: 255, A: 255})
			} else {
				img.Set(x, y, color.RGBA{B: 255, A: 255})
			}
		}
	}
	path := filepath.Join(t.TempDir(), "test.png")
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := png.Encode(f, img); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestThumbnailFitsTheBox(t *testing.T) {
	path := writePNG(t, 100, 100)
	lines, err := Thumbnail(path, 20, 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(lines) == 0 {
		t.Fatal("no rows rendered")
	}
	if len(lines) > 10 {
		t.Errorf("rendered %d rows into a 10-row box", len(lines))
	}
	for _, l := range lines {
		if n := strings.Count(l, upperHalf); n > 20 {
			t.Errorf("a row carries %d cells in a 20-column box", n)
		}
	}
}

func TestThumbnailKeepsTheAspectRatio(t *testing.T) {
	// A wide image should not fill a square box top to bottom.
	path := writePNG(t, 200, 50)
	lines, err := Thumbnail(path, 40, 20)
	if err != nil {
		t.Fatal(err)
	}
	// 200x50 into 40 columns is 40x10 pixels, which is five rows of cells.
	if len(lines) > 8 {
		t.Errorf("a 4:1 image rendered %d rows; the aspect ratio was not kept", len(lines))
	}
}

func TestThumbnailCarriesColour(t *testing.T) {
	path := writePNG(t, 40, 40)
	lines, _ := Thumbnail(path, 20, 10)
	joined := strings.Join(lines, "\n")

	if !strings.Contains(joined, "\x1b[38;2;") || !strings.Contains(joined, "\x1b[48;2;") {
		t.Error("no 24-bit colour in the render")
	}
	if !strings.Contains(joined, upperHalf) {
		t.Error("no half-block characters in the render")
	}
	// The top half is red, so a red foreground must appear.
	if !strings.Contains(joined, "\x1b[38;2;255;0;0m") {
		t.Errorf("the red half is missing:\n%q", lines[0])
	}
}

func TestThumbnailResetsColourAtTheEndOfEachRow(t *testing.T) {
	// Without a reset the last cell's background bleeds across the rest of
	// the terminal row.
	path := writePNG(t, 20, 20)
	lines, _ := Thumbnail(path, 10, 5)
	for i, l := range lines {
		if !strings.HasSuffix(l, "\x1b[0m") {
			t.Errorf("row %d does not reset colour: %q", i, l)
		}
	}
}

func TestThumbnailOfAMissingFile(t *testing.T) {
	if _, err := Thumbnail(filepath.Join(t.TempDir(), "nope.png"), 10, 5); err == nil {
		t.Error("a missing file must be an error")
	}
}

func TestThumbnailOfSomethingThatIsNotAnImage(t *testing.T) {
	path := filepath.Join(t.TempDir(), "not.png")
	os.WriteFile(path, []byte("this is not a png"), 0o644)
	if _, err := Thumbnail(path, 10, 5); err == nil {
		t.Error("a non-image must be an error rather than garbage")
	}
}

func TestThumbnailInNoSpace(t *testing.T) {
	path := writePNG(t, 40, 40)
	if _, err := Thumbnail(path, 0, 5); err == nil {
		t.Error("a zero-width box must be refused")
	}
}

func TestRendererCachesByFileAndSize(t *testing.T) {
	path := writePNG(t, 40, 40)
	r := NewRenderer(Options{})

	a := r.Preview(path, KindImage, 20, 10)
	b := r.Preview(path, KindImage, 20, 10)
	if !a.Ok() || !b.Ok() {
		t.Fatal("no preview produced")
	}
	if &a.Lines[0] != &b.Lines[0] {
		t.Error("a repeated preview was rendered again instead of cached")
	}
	// A different size is a different render.
	c := r.Preview(path, KindImage, 30, 10)
	if len(c.Lines) > 0 && &c.Lines[0] == &a.Lines[0] {
		t.Error("a different width reused the cached render")
	}
}

func TestPreviewOfSomethingNotDownloaded(t *testing.T) {
	r := NewRenderer(Options{})
	p := r.Preview("", KindImage, 20, 10)
	if p.Ok() {
		t.Error("an absent file produced a preview")
	}
	if p.Err == nil {
		t.Error("an absent file must say why there is nothing to show")
	}
}

func TestDocumentPreviewShowsText(t *testing.T) {
	path := filepath.Join(t.TempDir(), "notes.md")
	os.WriteFile(path, []byte("# Title\n\nfirst line\nsecond line\n"), 0o644)

	r := NewRenderer(Options{TextLines: 3})
	p := r.Preview(path, KindDocument, 40, 6)
	if !p.Ok() {
		t.Fatalf("no preview for a text document: %+v", p)
	}
	if len(p.Lines) > 3 {
		t.Errorf("showed %d lines, want at most 3", len(p.Lines))
	}
	if p.Lines[0] != "# Title" {
		t.Errorf("first line = %q", p.Lines[0])
	}
}

func TestDocumentPreviewSkipsBinary(t *testing.T) {
	// A PDF has nothing readable to show; a wall of mojibake is worse than a
	// filename.
	path := filepath.Join(t.TempDir(), "a.pdf")
	os.WriteFile(path, append([]byte("%PDF-1.7\n"), make([]byte, 200)...), 0o644)

	r := NewRenderer(Options{})
	if p := r.Preview(path, KindDocument, 40, 6); p.Ok() {
		t.Errorf("a binary document produced text: %q", p.Lines)
	}
}

func TestDocumentPreviewTruncatesLongLines(t *testing.T) {
	path := filepath.Join(t.TempDir(), "wide.txt")
	os.WriteFile(path, []byte(strings.Repeat("x", 400)+"\n"), 0o644)

	r := NewRenderer(Options{})
	p := r.Preview(path, KindDocument, 30, 4)
	if !p.Ok() {
		t.Fatal("no preview")
	}
	if n := len([]rune(p.Lines[0])); n > 30 {
		t.Errorf("line is %d runes wide in a 30-column box", n)
	}
}

func TestLooksLikeText(t *testing.T) {
	if !looksLikeText([]byte("hello\nworld\n")) {
		t.Error("plain text was rejected")
	}
	if looksLikeText([]byte{0x00, 0x01, 0x02}) {
		t.Error("a NUL byte was accepted as text")
	}
	if looksLikeText(nil) {
		t.Error("nothing is not text")
	}
}

func TestKindIcons(t *testing.T) {
	for _, k := range []Kind{KindImage, KindVideo, KindAudio, KindVoice, KindDocument, KindSticker, KindGIF} {
		if k.Icon() == "" || k.String() == "" {
			t.Errorf("kind %d has no icon or name", k)
		}
	}
}

func TestPreviewable(t *testing.T) {
	if !KindImage.Previewable() {
		t.Error("images are previewable")
	}
	if !KindVoice.Previewable() {
		t.Error("a voice note draws a waveform")
	}
	if KindUnknown.Previewable() {
		t.Error("nothing is known about an unknown attachment")
	}
}

func TestRenderedRowsAreDrawable(t *testing.T) {
	path := writePNG(t, 30, 30)
	lines, _ := Thumbnail(path, 12, 6)
	for _, l := range lines {
		if printableRunes(l) == 0 {
			t.Errorf("a row has nothing printable: %q", l)
		}
	}
}

// --- the download cache ------------------------------------------------------

func TestCacheFindsAFileByMessageID(t *testing.T) {
	// wacli names the file message-<id>.<ext> and picks the extension from the
	// mime type, so the lookup cannot assume one.
	dir := t.TempDir()
	c := NewCache(dir)

	if _, ok := c.Path("M1"); ok {
		t.Error("an empty cache reported a file")
	}
	path := filepath.Join(dir, "message-M1.jfif")
	os.WriteFile(path, []byte("data"), 0o600)

	got, ok := c.Path("M1")
	if !ok || got != path {
		t.Errorf("Path = %q, %v", got, ok)
	}
}

func TestCacheIgnoresAnEmptyFile(t *testing.T) {
	// A download interrupted halfway leaves a zero-length file; treating that
	// as present would show a broken preview forever.
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "message-M1.jpg"), nil, 0o600)
	if _, ok := NewCache(dir).Path("M1"); ok {
		t.Error("a zero-length file was reported as downloaded")
	}
}

func TestDownloadArgsAvoidTheStoreLock(t *testing.T) {
	// The whole point: wacli's own error says --read-only with --output takes
	// no lock, which is what lets a download happen while sync is running.
	args := NewCache("/tmp/wa/media").DownloadArgs("a@s.whatsapp.net", "M1")
	joined := strings.Join(args, " ")

	for _, want := range []string{
		"media download", "--chat a@s.whatsapp.net", "--id M1",
		"--read-only", "--output /tmp/wa/media",
	} {
		if !strings.Contains(joined, want) {
			t.Errorf("args are missing %q: %s", want, joined)
		}
	}
}

func TestCacheSizeAndClear(t *testing.T) {
	dir := t.TempDir()
	c := NewCache(dir)
	os.WriteFile(filepath.Join(dir, "message-M1.jpg"), make([]byte, 100), 0o600)
	os.WriteFile(filepath.Join(dir, "message-M2.png"), make([]byte, 200), 0o600)
	// Something else in the directory must not be counted or deleted.
	os.WriteFile(filepath.Join(dir, "notes.txt"), make([]byte, 50), 0o600)

	bytes, files := c.Size()
	if bytes != 300 || files != 2 {
		t.Errorf("Size = %d bytes in %d files, want 300 in 2", bytes, files)
	}
	n, err := c.Clear()
	if err != nil || n != 2 {
		t.Fatalf("Clear = %d, %v", n, err)
	}
	if _, err := os.Stat(filepath.Join(dir, "notes.txt")); err != nil {
		t.Error("Clear removed a file that was not its own")
	}
}

func TestCacheRemove(t *testing.T) {
	dir := t.TempDir()
	c := NewCache(dir)
	os.WriteFile(filepath.Join(dir, "message-M1.jpg"), []byte("x"), 0o600)

	if err := c.Remove("M1"); err != nil {
		t.Fatal(err)
	}
	if _, ok := c.Path("M1"); ok {
		t.Error("the file survived Remove")
	}
	if err := c.Remove("absent"); err != nil {
		t.Errorf("removing something absent should not fail: %v", err)
	}
}

func TestFetchNamesTheFileAfterTheMessage(t *testing.T) {
	// wacli names a download after the attachment, not after the message: a
	// photograph called "holiday.jpg" is written as "holiday.jpg". wa looks a
	// file up by message id, so a download that landed under its own name was
	// a download wa could not find - it fetched the file, drew a filename
	// chip, and fetched it again next time.
	c := NewCache(t.TempDir())

	got, err := c.Fetch("chat@s.whatsapp.net", "ABC", func(args []string) error {
		return writeInto(args, "holiday.jpg", "pretend jpeg")
	})
	if err != nil {
		t.Fatal(err)
	}
	if filepath.Base(got) != "message-ABC.jpg" {
		t.Errorf("filed as %q", filepath.Base(got))
	}
	found, ok := c.Path("ABC")
	if !ok || found != got {
		t.Errorf("Path found %q, %v", found, ok)
	}
}

func TestFetchCleansUpAfterItself(t *testing.T) {
	dir := t.TempDir()
	c := NewCache(dir)

	if _, err := c.Fetch("chat", "ABC", func(args []string) error {
		return writeInto(args, "x.png", "png")
	}); err != nil {
		t.Fatal(err)
	}
	entries, _ := os.ReadDir(dir)
	for _, e := range entries {
		if e.IsDir() {
			t.Errorf("left %q behind", e.Name())
		}
	}
}

func TestFetchReportsAFailedDownload(t *testing.T) {
	c := NewCache(t.TempDir())
	_, err := c.Fetch("chat", "ABC", func([]string) error {
		return errors.New("no network")
	})
	if err == nil || !strings.Contains(err.Error(), "no network") {
		t.Errorf("err = %v", err)
	}
	if _, ok := c.Path("ABC"); ok {
		t.Error("a failed download was filed anyway")
	}
}

func TestFetchReportsADownloadThatWroteNothing(t *testing.T) {
	c := NewCache(t.TempDir())
	if _, err := c.Fetch("chat", "ABC", func([]string) error { return nil }); err == nil {
		t.Error("a download that produced no file was accepted")
	}
}

func TestFetchIgnoresAnInterruptedEarlierAttempt(t *testing.T) {
	// A directory left behind by a download that was killed would make the
	// next one ambiguous: two files, and no way to know which is the answer.
	dir := t.TempDir()
	c := NewCache(dir)

	stale := c.stagingDir("ABC")
	os.MkdirAll(stale, 0o700)
	os.WriteFile(filepath.Join(stale, "half.jpg"), []byte("truncated"), 0o600)

	got, err := c.Fetch("chat", "ABC", func(args []string) error {
		return writeInto(args, "real.png", "png")
	})
	if err != nil {
		t.Fatal(err)
	}
	if filepath.Ext(got) != ".png" {
		t.Errorf("adopted %q, which is the interrupted attempt", got)
	}
}

// writeInto puts a file where the download arguments say to.
func writeInto(args []string, name, body string) error {
	for i, a := range args {
		if a != "--output" || i+1 >= len(args) {
			continue
		}
		dir := args[i+1]
		if err := os.MkdirAll(dir, 0o700); err != nil {
			return err
		}
		return os.WriteFile(filepath.Join(dir, name), []byte(body), 0o600)
	}
	return errors.New("no --output in the arguments")
}

func TestFetchGivesAnExtensionlessDownloadOne(t *testing.T) {
	// The cache finds a file again by globbing "message-<id>.*". A download
	// named without an extension would be filed where nothing looks for it -
	// the same invisible download that made an attachment fetch on every
	// redraw and never appear.
	c := NewCache(t.TempDir())

	got, err := c.Fetch("chat", "ABC", func(args []string) error {
		return writeInto(args, "invoice", "data")
	})
	if err != nil {
		t.Fatal(err)
	}
	if filepath.Ext(got) == "" {
		t.Errorf("filed as %q, which Path cannot match", filepath.Base(got))
	}
	if _, ok := c.Path("ABC"); !ok {
		t.Error("the cache cannot find what it just filed")
	}
}

func TestFetchKeepsASpaceInAName(t *testing.T) {
	// wacli names a download after the attachment, and attachments have
	// spaces in their names: "Email Notifications.pdf".
	c := NewCache(t.TempDir())

	got, err := c.Fetch("chat", "ABC", func(args []string) error {
		return writeInto(args, "Email Notifications.pdf", "%PDF-1.4")
	})
	if err != nil {
		t.Fatal(err)
	}
	if filepath.Base(got) != "message-ABC.pdf" {
		t.Errorf("filed as %q", filepath.Base(got))
	}
}
