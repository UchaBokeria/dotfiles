package ui

import (
	"context"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
)

func writeTestPNG(t *testing.T, dir string) string {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 60, 40))
	for y := 0; y < 40; y++ {
		for x := 0; x < 60; x++ {
			img.Set(x, y, color.RGBA{R: uint8(x * 4), G: uint8(y * 6), B: 200, A: 255})
		}
	}
	path := filepath.Join(dir, "photo.png")
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

// withMedia seeds the open chat with one downloaded image.
func withImage(t *testing.T, a *testApp) domain.Message {
	t.Helper()
	path := writeTestPNG(t, a.dir)
	m := domain.Message{
		RowID: 99, ID: "IMG1", ChatJID: jid(t, "a@s.whatsapp.net"),
		TS: time.Date(2026, 9, 8, 10, 0, 0, 0, time.UTC),
		Media: &domain.MediaRef{
			Type: "image", MimeType: "image/png", Filename: "photo.png",
			LocalPath: path, Length: 1234, DownloadedAt: time.Now(),
		},
	}
	a.store.messages["a@s.whatsapp.net"] = append(a.store.messages["a@s.whatsapp.net"], m)
	if err := a.pane.Open(context.Background(), a.pane.Chat()); err != nil {
		t.Fatal(err)
	}
	return m
}

func TestDownloadedImageIsPreviewedInline(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	withImage(t, a)

	view := a.pane.View()
	if !strings.Contains(view, "▀") {
		t.Errorf("no half-block image rows in the conversation:\n%s", view)
	}
}

func TestPreviewCanBeTurnedOff(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	withImage(t, a)

	if !strings.Contains(a.pane.View(), "▀") {
		t.Fatal("no preview to turn off")
	}
	if err := a.RunCommand(":preview"); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(a.pane.View(), "▀") {
		t.Error("the preview survived :preview")
	}
	if !strings.Contains(a.pane.View(), "photo.png") {
		t.Error("with previews off the filename chip should still be there")
	}
}

func TestUndownloadedMediaShowsAChipAndNoPreview(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)

	a.store.messages["a@s.whatsapp.net"] = append(a.store.messages["a@s.whatsapp.net"],
		domain.Message{
			RowID: 98, ID: "IMG2", ChatJID: jid(t, "a@s.whatsapp.net"),
			TS:    time.Date(2026, 9, 8, 10, 0, 0, 0, time.UTC),
			Media: &domain.MediaRef{Type: "image", Filename: "not-here.jpg", Length: 2048},
		})
	a.pane.Open(context.Background(), a.pane.Chat())

	view := a.pane.View()
	if strings.Contains(view, "▀") {
		t.Error("something was drawn for a file that was never downloaded")
	}
	if !strings.Contains(view, "not-here.jpg") {
		t.Errorf("the chip naming the file is missing:\n%s", view)
	}
}

func TestPreviewDoesNotOverflowTheBubble(t *testing.T) {
	a := newTestApp(t)
	for _, w := range []int{60, 80, 120} {
		a.resize(w, 30)
		withImage(t, a)
		for _, line := range strings.Split(a.pane.View(), "\n") {
			if got := visibleCells(line); got > w {
				t.Errorf("width %d: a row is %d cells: %q", w, got, line)
			}
		}
	}
}

// visibleCells counts drawn cells, treating a half block as one.
func visibleCells(s string) int {
	stripped := stripANSI(s)
	return len([]rune(stripped))
}

func TestMediaSummaryCountsWhatIsThere(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)
	withImage(t, a)

	body := strings.Join(a.mediaSummary(), "\n")
	if !strings.Contains(body, "image") {
		t.Errorf("the summary does not mention the image:\n%s", body)
	}
}

func TestMediaSummaryOnAChatWithNone(t *testing.T) {
	a := newTestApp(t)
	body := strings.Join(a.mediaSummary(), "\n")
	if !strings.Contains(body, "no attachments") {
		t.Errorf("summary = %q", body)
	}
}

func TestOpenMediaRefusesAMessageWithout(t *testing.T) {
	a := newTestApp(t)
	m, ok := a.pane.Selected()
	if !ok {
		t.Fatal("no message")
	}
	if err := a.openMedia(m); err == nil {
		t.Error("opening a text message as media must be refused")
	}
}

func TestMediaKindClassification(t *testing.T) {
	m := domain.Message{Media: &domain.MediaRef{Type: "audio", MimeType: "audio/ogg; codecs=opus"}}
	if got := mediaKind(m); got != media.KindVoice {
		t.Errorf("mediaKind = %v, want a voice note", got)
	}
	if got := mediaKind(domain.Message{}); got != media.KindUnknown {
		t.Errorf("a message with no media = %v", got)
	}
}

func TestReactionsRenderAsAChipNotABubble(t *testing.T) {
	a := newTestApp(t)
	a.resize(100, 30)

	msgs := a.store.messages["a@s.whatsapp.net"]
	target := msgs[len(msgs)-1]
	target.Reactions = []domain.Reaction{{Emoji: "🔥", FromMe: true}}
	msgs[len(msgs)-1] = target
	a.store.messages["a@s.whatsapp.net"] = msgs
	a.pane.Open(context.Background(), a.pane.Chat())

	view := a.pane.View()
	if !strings.Contains(view, "🔥") {
		t.Errorf("the reaction chip is missing:\n%s", view)
	}
	if strings.Contains(view, "Reacted") {
		t.Error("a reaction was drawn as a message of its own")
	}
}

func TestPreviewUsesWasOwnCacheWhenTheStoreHasNoPath(t *testing.T) {
	// A lock-free download is deliberately not recorded by wacli, so the
	// store's local_path stays empty and wa has to remember the file itself.
	a := newTestApp(t)
	a.resize(100, 30)

	cacheDir := filepath.Join(a.dir, "cache", "media")
	os.MkdirAll(cacheDir, 0o700)

	msgs := a.store.messages["a@s.whatsapp.net"]
	target := msgs[len(msgs)-1]
	target.Media = &domain.MediaRef{Type: "image", MimeType: "image/png", Filename: "x.png"}
	msgs[len(msgs)-1] = target
	a.store.messages["a@s.whatsapp.net"] = msgs
	a.pane.Open(context.Background(), a.pane.Chat())

	if strings.Contains(a.pane.View(), "▀") {
		t.Fatal("something was previewed before anything was downloaded")
	}

	// Put a real image where the cache would have written it.
	src := writeTestPNG(t, a.dir)
	body, err := os.ReadFile(src)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(cacheDir, "message-"+target.ID+".png"), body, 0o600); err != nil {
		t.Fatal(err)
	}
	a.media.cache = media.NewCache(cacheDir)
	a.pane.Invalidate()

	if !strings.Contains(a.pane.View(), "▀") {
		t.Errorf("the cached download was not previewed:\n%s", a.pane.View())
	}
}
