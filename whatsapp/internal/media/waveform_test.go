package media

import (
	"context"
	"math"
	"os/exec"
	"strings"
	"testing"
	"time"
)

func skipWithoutFFmpeg(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("ffmpeg"); err != nil {
		t.Skip("ffmpeg is not installed")
	}
}

func TestWaveformOfAVoiceNote(t *testing.T) {
	skipWithoutFFmpeg(t)

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	const cols = 32
	wave, err := Waveform(ctx, "ffmpeg", "testdata/voice.ogg", cols)
	if err != nil {
		t.Fatal(err)
	}
	if n := len([]rune(wave)); n != cols {
		t.Fatalf("the waveform is %d columns, want %d: %q", n, cols, wave)
	}
	for _, r := range wave {
		if !strings.ContainsRune(string(waveBlocks), r) {
			t.Fatalf("%q is not a bar character", r)
		}
	}
}

func TestWaveformShowsTheSilence(t *testing.T) {
	// The fixture is a tone with a silent gap in the middle. A waveform that
	// did not read the samples - or that normalised against the peak of each
	// column rather than the whole clip - would draw a flat bar.
	skipWithoutFFmpeg(t)

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	wave, err := Waveform(ctx, "ffmpeg", "testdata/voice.ogg", 20)
	if err != nil {
		t.Fatal(err)
	}
	runes := []rune(wave)
	quietest, loudest := 8, 0
	for _, r := range runes {
		i := strings.IndexRune(string(waveBlocks), r)
		if i < quietest {
			quietest = i
		}
		if i > loudest {
			loudest = i
		}
	}
	if loudest-quietest < 3 {
		t.Errorf("the bars barely differ (%d..%d): %q", quietest, loudest, wave)
	}
}

func TestWaveformNeedsRoom(t *testing.T) {
	if _, err := Waveform(context.Background(), "ffmpeg", "testdata/voice.ogg", 2); err == nil {
		t.Error("two columns is not a waveform")
	}
}

func TestWaveformOfSomethingThatIsNotAudio(t *testing.T) {
	skipWithoutFFmpeg(t)

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	if _, err := Waveform(ctx, "ffmpeg", "testdata/sticker-lossy.webp", 20); err == nil {
		t.Error("a picture has no waveform")
	}
}

func TestWaveformWithoutFFmpeg(t *testing.T) {
	_, err := Waveform(context.Background(), "definitely-not-installed-ffmpeg", "testdata/voice.ogg", 20)
	if err == nil {
		t.Fatal("expected an error")
	}
	if !strings.Contains(err.Error(), "ffmpeg") {
		t.Errorf("the error should name what is missing: %v", err)
	}
}

func TestAudioPreviewCarriesTheDuration(t *testing.T) {
	skipWithoutFFmpeg(t)

	r := NewRenderer(Options{Cols: 24, Rows: 4, CacheDir: t.TempDir()})
	p := r.Preview("testdata/voice.ogg", KindVoice, 24, 4)
	if !p.Ok() {
		t.Fatalf("no waveform: %v", p.Err)
	}
	if len(p.Lines) != 1 {
		t.Errorf("a waveform is one row, got %d", len(p.Lines))
	}
	if p.Caption == "" {
		t.Error("no duration")
	}
}

func TestBarsAreFlatForSilence(t *testing.T) {
	// Dividing by a zero peak would produce NaN and an out-of-range index.
	got := bars(make([]int16, 800), 8)
	if got != strings.Repeat(string(waveBlocks[0]), 8) {
		t.Errorf("silence drew %q", got)
	}
}

func TestBarsUseTheFullHeightForAConstantTone(t *testing.T) {
	samples := make([]int16, 800)
	for i := range samples {
		samples[i] = int16(math.MaxInt16 / 2)
	}
	got := bars(samples, 8)
	if got != strings.Repeat(string(waveBlocks[len(waveBlocks)-1]), 8) {
		t.Errorf("a constant tone drew %q", got)
	}
}

func TestBarsHandleFewerSamplesThanColumns(t *testing.T) {
	// A clip of three samples in a forty-column bubble must still produce
	// forty characters rather than panic on an empty slice.
	got := bars([]int16{1, 2, 3}, 40)
	if n := len([]rune(got)); n != 40 {
		t.Errorf("got %d columns, want 40", n)
	}
}
