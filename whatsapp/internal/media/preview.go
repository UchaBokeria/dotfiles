package media

import (
	"bufio"
	"context"
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode"
)

// Preview is what to draw for one attachment.
type Preview struct {
	// Lines are terminal rows: half-block image data, or text.
	Lines []string
	// Caption is the one-line summary under it.
	Caption string
	// Err explains why there is nothing to draw, when there is not.
	Err error
}

// Ok reports whether there is something to show.
func (p Preview) Ok() bool { return len(p.Lines) > 0 }

// Options control how a preview is produced.
type Options struct {
	Cols int
	Rows int
	// CacheDir holds extracted video frames. Empty disables that.
	CacheDir string
	// TextLines caps how much of a text document is shown inline.
	TextLines int
	// FFmpeg names the binary used for video frames; empty means "ffmpeg".
	FFmpeg string
}

func (o Options) ffmpeg() string {
	if o.FFmpeg == "" {
		return "ffmpeg"
	}
	return o.FFmpeg
}

// Renderer produces and caches previews.
//
// Caching matters more than it looks: the message pane re-renders on every
// keystroke, and decoding a three-megapixel photograph each time would make
// scrolling visibly stutter.
type Renderer struct {
	mu    sync.Mutex
	cache map[string]Preview
	opts  Options
}

// NewRenderer returns a renderer.
func NewRenderer(o Options) *Renderer {
	if o.TextLines <= 0 {
		o.TextLines = 6
	}
	return &Renderer{cache: map[string]Preview{}, opts: o}
}

// Preview renders an attachment, reusing an earlier render when the file, the
// size and the shape are unchanged.
func (r *Renderer) Preview(path string, kind Kind, cols, rows int) Preview {
	if path == "" {
		return Preview{Err: fmt.Errorf("not downloaded")}
	}
	fi, err := os.Stat(path)
	if err != nil {
		return Preview{Err: fmt.Errorf("not downloaded")}
	}

	key := fmt.Sprintf("%s|%d|%d|%dx%d", path, fi.Size(), fi.ModTime().UnixNano(), cols, rows)

	r.mu.Lock()
	if p, ok := r.cache[key]; ok {
		r.mu.Unlock()
		return p
	}
	r.mu.Unlock()

	p := r.render(path, kind, cols, rows)

	r.mu.Lock()
	// A bounded cache: the pane only ever shows a screenful.
	if len(r.cache) > 128 {
		r.cache = map[string]Preview{}
	}
	r.cache[key] = p
	r.mu.Unlock()
	return p
}

func (r *Renderer) render(path string, kind Kind, cols, rows int) Preview {
	switch kind {
	case KindImage, KindSticker:
		return r.imagePreview(path, cols, rows)

	case KindVideo, KindGIF:
		return r.videoPreview(path, cols, rows)

	case KindAudio, KindVoice:
		return r.audioPreview(path, cols)

	case KindDocument:
		return r.documentPreview(path, cols)
	}
	return Preview{}
}

// audioPreview draws a waveform with the duration under it.
//
// The waveform is the whole point: a voice note otherwise looks identical to
// every other voice note, and the duration alone does not say whether it is
// speech or a minute of pocket noise. Without ffmpeg there is no way to decode
// opus, and the duration is all there is.
func (r *Renderer) audioPreview(path string, cols int) Preview {
	caption := ""
	if d := probeDuration(path); d > 0 {
		caption = HumanDuration(d)
	}

	ctx, cancel := context.WithTimeout(context.Background(), waveTimeout)
	defer cancel()

	wave, err := Waveform(ctx, r.opts.ffmpeg(), path, cols)
	if err != nil {
		return Preview{Caption: caption, Err: err}
	}
	return Preview{Lines: []string{wave}, Caption: caption}
}

// imagePreview draws a still image, falling back to ffmpeg for the formats Go
// cannot decode.
//
// The fallback is what makes animated stickers work. Go decodes both still
// webp encodings but not the animated one, which is a large share of what a
// sticker actually is; ffmpeg reads it, and one frame of an animation is a
// perfectly good preview. The same route rescues anything else ffmpeg knows
// and the image package does not.
func (r *Renderer) imagePreview(path string, cols, rows int) Preview {
	lines, err := Thumbnail(path, cols, rows)
	if err != nil {
		frame, ferr := r.frame(path)
		if ferr != nil {
			return Preview{Err: err}
		}
		if lines, err = Thumbnail(frame, cols, rows); err != nil {
			return Preview{Err: err}
		}
	}
	caption := ""
	if w, h, err := Dimensions(path); err == nil {
		caption = fmt.Sprintf("%d×%d", w, h)
	}
	return Preview{Lines: lines, Caption: caption}
}

// videoPreview extracts a frame and draws it, so a video reads as a still
// with a play marker rather than as a filename.
func (r *Renderer) videoPreview(path string, cols, rows int) Preview {
	frame, err := r.frame(path)
	if err != nil {
		if d := probeDuration(path); d > 0 {
			return Preview{Caption: HumanDuration(d), Err: err}
		}
		return Preview{Err: err}
	}
	lines, err := Thumbnail(frame, cols, rows)
	if err != nil {
		return Preview{Err: err}
	}
	caption := "▶"
	if d := probeDuration(path); d > 0 {
		caption = "▶ " + HumanDuration(d)
	}
	return Preview{Lines: lines, Caption: caption}
}

// frame pulls a still out of a video with ffmpeg, cached on disk because the
// extraction costs far more than the drawing.
func (r *Renderer) frame(path string) (string, error) {
	if _, err := exec.LookPath(r.opts.ffmpeg()); err != nil {
		return "", fmt.Errorf("ffmpeg is not installed, so videos have no preview")
	}
	dir := r.opts.CacheDir
	if dir == "" {
		dir = filepath.Join(os.TempDir(), "wa-frames")
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", err
	}

	sum := sha1.Sum([]byte(path))
	out := filepath.Join(dir, hex.EncodeToString(sum[:])+".png")
	if fi, err := os.Stat(out); err == nil && fi.Size() > 0 {
		return out, nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// One frame a second in, which skips the black opening frame most videos
	// start with; -y so a half-written file from a previous run is replaced.
	//
	// The seek is only a preference. Asked for a frame past the end of a short
	// clip - or of a two-frame animated sticker - ffmpeg exits successfully
	// having written nothing at all, so the exit status is not enough to go
	// on and the output has to be looked at.
	err := runFFmpegFrame(ctx, r.opts.ffmpeg(), out,
		"-ss", "00:00:01", "-i", path)
	if err != nil {
		err = runFFmpegFrame(ctx, r.opts.ffmpeg(), out, "-i", path)
	}
	if err != nil {
		return "", err
	}
	return out, nil
}

// runFFmpegFrame writes one frame of path to out, and reports an error unless
// a frame actually landed there.
func runFFmpegFrame(ctx context.Context, bin, out string, input ...string) error {
	args := append([]string{"-loglevel", "error", "-y"}, input...)
	args = append(args, "-frames:v", "1", "-vf", "scale=320:-1", out)

	if err := exec.CommandContext(ctx, bin, args...).Run(); err != nil {
		return fmt.Errorf("extracting a frame: %w", err)
	}
	fi, err := os.Stat(out)
	if err != nil || fi.Size() == 0 {
		return fmt.Errorf("extracting a frame: ffmpeg wrote nothing")
	}
	return nil
}

// probeDuration asks ffprobe how long a file is.
func probeDuration(path string) float64 {
	if _, err := exec.LookPath("ffprobe"); err != nil {
		return 0
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	out, err := exec.CommandContext(ctx, "ffprobe",
		"-v", "error", "-show_entries", "format=duration",
		"-of", "json", path).Output()
	if err != nil {
		return 0
	}
	var probe struct {
		Format struct {
			Duration string `json:"duration"`
		} `json:"format"`
	}
	if err := json.Unmarshal(out, &probe); err != nil {
		return 0
	}
	d, err := strconv.ParseFloat(probe.Format.Duration, 64)
	if err != nil {
		return 0
	}
	return d
}

// documentPreview shows the opening lines of anything that is readable text.
//
// A PDF or a zip has nothing useful to show without a converter, so it gets a
// chip instead of a wall of mojibake.
func (r *Renderer) documentPreview(path string, cols int) Preview {
	f, err := os.Open(path)
	if err != nil {
		return Preview{Err: err}
	}
	defer f.Close()

	head := make([]byte, 1024)
	n, _ := f.Read(head)
	if !looksLikeText(head[:n]) {
		return Preview{}
	}
	if _, err := f.Seek(0, 0); err != nil {
		return Preview{Err: err}
	}

	var lines []string
	scan := bufio.NewScanner(f)
	scan.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scan.Scan() && len(lines) < r.opts.TextLines {
		line := strings.ReplaceAll(scan.Text(), "\t", "    ")
		if len([]rune(line)) > cols {
			line = string([]rune(line)[:maxInt(0, cols-1)]) + "…"
		}
		lines = append(lines, line)
	}
	if len(lines) == 0 {
		return Preview{}
	}
	return Preview{Lines: lines, Caption: "text"}
}

// looksLikeText decides whether a file can be shown as text: valid UTF-8 with
// no NUL bytes and few control characters.
func looksLikeText(b []byte) bool {
	if len(b) == 0 {
		return false
	}
	control := 0
	for _, c := range b {
		if c == 0 {
			return false
		}
		if c < 0x09 || (c > 0x0d && c < 0x20) {
			control++
		}
	}
	return control*100/len(b) < 5
}

// Playable reports whether a kind is worth handing to a media player.
func Playable(k Kind) bool {
	switch k {
	case KindVideo, KindGIF, KindAudio, KindVoice:
		return true
	}
	return false
}

// Player picks a command to play a file with, preferring one that can stay in
// the terminal for audio.
func Player(kind Kind) (string, []string, bool) {
	if kind == KindAudio || kind == KindVoice {
		if _, err := exec.LookPath("mpv"); err == nil {
			return "mpv", []string{"--no-video", "--really-quiet"}, true
		}
	}
	if _, err := exec.LookPath("mpv"); err == nil {
		return "mpv", []string{"--really-quiet"}, true
	}
	return "", nil, false
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// printableRunes is used by the tests to check a rendered row carries drawing
// characters rather than raw bytes.
func printableRunes(s string) int {
	n := 0
	for _, r := range s {
		if unicode.IsPrint(r) {
			n++
		}
	}
	return n
}
