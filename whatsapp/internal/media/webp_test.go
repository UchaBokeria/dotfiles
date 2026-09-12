package media

import (
	"os/exec"
	"strings"
	"testing"
)

// WhatsApp stickers are webp, and the standard library decodes neither of its
// two encodings. The fixtures cover both: lossless (VP8L, what a sticker pack
// usually is) and lossy (VP8, what a re-encoded forward usually is).
func TestThumbnailOfAWebP(t *testing.T) {
	for _, name := range []string{
		"testdata/sticker-lossless.webp",
		"testdata/sticker-lossy.webp",
	} {
		lines, err := Thumbnail(name, 20, 10)
		if err != nil {
			t.Errorf("%s: %v", name, err)
			continue
		}
		if len(lines) == 0 {
			t.Errorf("%s: no rows rendered", name)
			continue
		}
		joined := strings.Join(lines, "\n")
		if !strings.Contains(joined, upperHalf) {
			t.Errorf("%s: no half-block characters", name)
		}
		if !strings.Contains(joined, "\x1b[38;2;") {
			t.Errorf("%s: no colour", name)
		}
	}
}

func TestWebPIsPreviewable(t *testing.T) {
	// The extension route matters as much as the decoder: wacli names a
	// downloaded sticker by mime type, and nothing else tells the renderer to
	// try.
	if got := Classify("", "", "message-ABC.webp"); got != KindImage {
		t.Errorf("a .webp classified as %v", got)
	}
	if got := Classify("sticker", "image/webp", ""); got != KindSticker {
		t.Errorf("a sticker classified as %v", got)
	}
	if !KindSticker.Previewable() {
		t.Error("a sticker must be previewable")
	}
}

func TestPreviewOfAnAnimatedSticker(t *testing.T) {
	// Go decodes neither animated webp nor animated anything, and a large
	// share of WhatsApp stickers are animated. ffmpeg pulls a frame out.
	if _, err := exec.LookPath("ffmpeg"); err != nil {
		t.Skip("ffmpeg is not installed")
	}
	if _, err := Thumbnail("testdata/sticker-animated.webp", 20, 10); err == nil {
		t.Skip("the image package learned animated webp; the fallback is moot")
	}

	r := NewRenderer(Options{Cols: 20, Rows: 10, CacheDir: t.TempDir()})
	p := r.Preview("testdata/sticker-animated.webp", KindSticker, 20, 10)
	if !p.Ok() {
		t.Fatalf("no preview: %v", p.Err)
	}
	if !strings.Contains(strings.Join(p.Lines, "\n"), upperHalf) {
		t.Error("the frame did not render as half blocks")
	}
}

func TestPreviewOfAVideoShorterThanTheSeek(t *testing.T) {
	// The frame extractor seeks a second in to skip the black opening frame.
	// Asked for that on a clip shorter than a second, ffmpeg exits 0 and
	// writes nothing, so a preview that trusted the exit status showed an
	// error where a perfectly extractable frame was available.
	if _, err := exec.LookPath("ffmpeg"); err != nil {
		t.Skip("ffmpeg is not installed")
	}
	r := NewRenderer(Options{Cols: 20, Rows: 10, CacheDir: t.TempDir()})
	p := r.Preview("testdata/short.mp4", KindVideo, 20, 10)
	if !p.Ok() {
		t.Fatalf("no preview for a 0.4s video: %v", p.Err)
	}
	if !strings.HasPrefix(p.Caption, "▶") {
		t.Errorf("caption = %q, want a play marker", p.Caption)
	}
}
