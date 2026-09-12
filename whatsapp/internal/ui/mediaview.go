package ui

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
)

// mediaView adapts the media package to what the bubble renderer asks for.
//
// The renderer knows nothing about images: it asks for rows of terminal text
// and places them. That keeps the golden layout tests free of photographs and
// lets previews be turned off without touching the layout at all.
type mediaView struct {
	r       *media.Renderer
	cache   *media.Cache
	enabled bool
	// autoMax is the largest attachment fetched without being asked. Zero
	// turns automatic downloading off.
	autoMax int64
	fetch   *fetcher
	// gfx draws real pixels where the terminal can. Nil, or disabled, falls
	// back to half blocks.
	gfx *graphics
}

// localPath is where the file actually is: the store's own path when wacli
// recorded a download, otherwise wa's cache, because a lock-free download is
// deliberately not recorded.
func (v *mediaView) localPath(m domain.Message) (string, bool) {
	if m.Media == nil {
		return "", false
	}
	if m.Media.Downloaded() {
		if _, err := os.Stat(m.Media.LocalPath); err == nil {
			return m.Media.LocalPath, true
		}
	}
	if v == nil || v.cache == nil {
		return "", false
	}
	return v.cache.Path(m.ID)
}

// PreviewLines draws an attachment, or returns nothing when there is nothing
// to draw. A missing file is not an error here: most media is never
// downloaded, and the chip beneath already says so.
func (v *mediaView) PreviewLines(m domain.Message, cols, rows int) ([]string, string) {
	if v == nil || !v.enabled || v.r == nil || m.Media == nil {
		return nil, ""
	}
	kind := media.Classify(m.Media.Type, m.Media.MimeType, m.Media.Filename)
	if !kind.Previewable() {
		return nil, ""
	}
	path, ok := v.localPath(m)
	if !ok {
		v.wantAuto(m)
		return nil, ""
	}
	// Pixels where the terminal can draw them. Half blocks are a good enough
	// likeness of a screenshot and a poor one of a face.
	if v.gfx.Enabled() && graphicsKind(kind) {
		if lines := v.gfx.Lines(path, cols, rows); len(lines) > 0 {
			return lines, dimensionCaption(path)
		}
	}

	p := v.r.Preview(path, kind, cols, rows)
	return p.Lines, p.Caption
}

// graphicsKind reports whether a kind is a still picture the terminal can
// draw. Video and documents keep their existing treatment: a video preview is
// an extracted frame, which arrives as a file of its own, and a document
// preview is text.
func graphicsKind(k media.Kind) bool {
	switch k {
	case media.KindImage, media.KindSticker:
		return true
	}
	return false
}

func dimensionCaption(path string) string {
	if w, h, err := media.Dimensions(path); err == nil {
		return fmt.Sprintf("%d×%d", w, h)
	}
	return ""
}

// wantAuto asks for a small attachment to be downloaded in the background.
//
// The size limit is the whole safety mechanism: a photograph is a few hundred
// kilobytes and worth fetching unasked, a video is not, and neither is the
// forty-megabyte zip somebody attached to a work chat. A file whose size the
// store does not know is left alone rather than guessed at.
func (v *mediaView) wantAuto(m domain.Message) {
	if v.autoMax <= 0 || v.fetch == nil {
		return
	}
	if m.Media.Length <= 0 || m.Media.Length > v.autoMax {
		return
	}
	if err := v.cache.Ensure(); err != nil {
		return
	}
	v.fetch.Want(m)
}

// mediaKind classifies a message's attachment.
func mediaKind(m domain.Message) media.Kind {
	if m.Media == nil {
		return media.KindUnknown
	}
	return media.Classify(m.Media.Type, m.Media.MimeType, m.Media.Filename)
}

// openMedia does the right thing for the kind: play audio and video, hand
// everything else to the desktop.
func (a *App) openMedia(m domain.Message) error {
	if m.Media == nil || m.Media.Type == "" {
		return fmt.Errorf("this message has no media")
	}
	path, ok := a.media.localPath(m)
	if !ok {
		if err := a.downloadMedia(m); err != nil {
			return err
		}
		if path, ok = a.media.localPath(m); !ok {
			return fmt.Errorf("downloaded, but no local file appeared")
		}
	}

	kind := mediaKind(m)
	if media.Playable(kind) {
		if name, args, ok := media.Player(kind); ok {
			return a.spawn(name, append(args, path)...)
		}
	}
	return a.openExternally(path)
}

// spawn starts a program without waiting for it, so a video player does not
// freeze the interface until it is closed.
func (a *App) spawn(name string, args ...string) error {
	if _, err := exec.LookPath(name); err != nil {
		return fmt.Errorf("%s is not installed", name)
	}
	cmd := exec.Command(name, args...)
	if err := cmd.Start(); err != nil {
		return err
	}
	go cmd.Wait()

	a.setStatus("opened in " + name)
	return nil
}

// downloadAllInChat fetches every attachment in the open conversation.
//
// One lock handover for the lot: doing them one at a time would stop and start
// the sync process for each file, which takes longer than the downloads.
func (a *App) downloadAllInChat() error {
	if a.pane.Chat().JID.IsZero() {
		return fmt.Errorf("no chat is open")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}

	var pending []domain.Message
	for _, m := range a.pane.Messages() {
		if !m.HasMedia() {
			continue
		}
		if _, have := a.media.localPath(m); !have {
			pending = append(pending, m)
		}
	}
	if len(pending) == 0 {
		a.setStatus("everything here is already downloaded")
		return nil
	}
	if err := a.media.cache.Ensure(); err != nil {
		return err
	}

	a.setStatus(fmt.Sprintf("downloading %d…", len(pending)))

	client := a.deps.Client
	cache := a.media.cache
	type job struct{ chat, id string }
	jobs := make([]job, 0, len(pending))
	for _, m := range pending {
		jobs = append(jobs, job{chat: m.StoreJID().String(), id: m.ID})
	}

	// In the background, and no lock is taken, so these go back to back
	// rather than one sync handover at a time. Waiting for a chat's worth of
	// attachments on the interface's own goroutine froze it for minutes.
	a.queue(func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
		defer cancel()

		var failed []string
		for _, j := range jobs {
			if ctx.Err() != nil {
				break
			}
			_, err := cache.Fetch(j.chat, j.id, func(args []string) error {
				_, err := client.Raw(ctx, args...)
				return err
			})
			if err != nil {
				failed = append(failed, j.id+": "+err.Error())
			}
		}

		switch {
		case len(failed) == len(jobs):
			return statusMsg{
				text:  fmt.Sprintf("none of the %d downloads succeeded (see :log)", len(jobs)),
				isErr: true,
			}
		case len(failed) > 0:
			return downloadedMsg{
				what:   fmt.Sprintf("downloaded %d of %d", len(jobs)-len(failed), len(jobs)),
				failed: failed,
			}
		default:
			return downloadedMsg{what: fmt.Sprintf("downloaded %d", len(jobs))}
		}
	})
	return nil
}

// mediaSummary describes what is in the open chat, for :media.
func (a *App) mediaSummary() []string {
	counts := map[media.Kind][2]int{} // total, downloaded
	for _, m := range a.pane.Messages() {
		if !m.HasMedia() {
			continue
		}
		k := mediaKind(m)
		c := counts[k]
		c[0]++
		if _, have := a.media.localPath(m); have {
			c[1]++
		}
		counts[k] = c
	}
	if len(counts) == 0 {
		return []string{"", "  no attachments in the loaded messages"}
	}

	out := []string{"", "  kind        here  downloaded"}
	for _, k := range []media.Kind{
		media.KindImage, media.KindVideo, media.KindGIF,
		media.KindAudio, media.KindVoice, media.KindSticker, media.KindDocument,
	} {
		c, ok := counts[k]
		if !ok {
			continue
		}
		out = append(out, fmt.Sprintf("  %-10s %5d  %10d", k, c[0], c[1]))
	}
	bytes, files := a.media.cache.Size()
	out = append(out, "",
		fmt.Sprintf("  cache       %s in %d files", media.HumanSize(bytes), files),
		"  "+a.media.cache.Dir(),
		"",
		"  <leader>d   download the selected message's media",
		"  <leader>D   download everything in this chat",
		"  <leader>o   open it in the desktop, or play it")
	return out
}

// PreviewsSupported reports whether inline previews will show anything, for
// wa doctor.
//
// Half blocks need only 24-bit colour, so the answer is yes almost everywhere
// - including inside tmux, where kitty's graphics protocol would need
// allow-passthrough turned on.
func PreviewsSupported() (bool, string) {
	if strings.Contains(strings.ToLower(os.Getenv("TERM")), "dumb") {
		return false, "the terminal reports itself as dumb"
	}
	if g := media.GraphicsFromEnv(); g.Enabled {
		return true, g.Reason
	}
	return true, "half blocks with 24-bit colour"
}
