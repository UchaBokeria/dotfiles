package media

import (
	"context"
	"encoding/binary"
	"fmt"
	"io"
	"math"
	"os/exec"
	"strings"
	"time"
)

// waveBlocks are the eight heights a bar can be drawn at.
var waveBlocks = []rune{'▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'}

// maxWaveSamples caps what is read from ffmpeg: at 8 kHz mono this is about
// twenty minutes of audio, and a voice note longer than that is not going to
// be read off a bar chart anyway.
const maxWaveSamples = 8000 * 60 * 20

// Waveform draws an audio file as one row of bars.
//
// A voice note is the one attachment with nothing to look at, and a bare
// duration reads the same whether it is speech, silence or a song. The bars
// are drawn from the actual samples rather than faked, so a pause in the
// middle of a message shows up as one.
//
// It needs ffmpeg. Without it there is no way to decode opus in pure Go, and
// the caller falls back to showing only the duration.
func Waveform(ctx context.Context, ffmpegBin, path string, cols int) (string, error) {
	if cols < 4 {
		return "", fmt.Errorf("no room for a waveform")
	}
	if _, err := exec.LookPath(ffmpegBin); err != nil {
		return "", fmt.Errorf("ffmpeg is not installed, so voice notes have no waveform")
	}

	samples, err := decodeSamples(ctx, ffmpegBin, path)
	if err != nil {
		return "", err
	}
	if len(samples) == 0 {
		return "", fmt.Errorf("%s: no audio", path)
	}
	return bars(samples, cols), nil
}

// decodeSamples reads the file as 8 kHz mono signed 16-bit PCM.
//
// Downsampling to 8 kHz is deliberate: the bars average over thousands of
// samples each, so the extra resolution of the original would be thrown away
// immediately and only costs decode time.
func decodeSamples(ctx context.Context, ffmpegBin, path string) ([]int16, error) {
	cmd := exec.CommandContext(ctx, ffmpegBin,
		"-loglevel", "error",
		"-i", path,
		"-ac", "1", "-ar", "8000",
		"-f", "s16le", "-")

	out, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	var stderr strings.Builder
	cmd.Stderr = &stderr

	if err := cmd.Start(); err != nil {
		return nil, err
	}

	samples, readErr := readSamples(out, maxWaveSamples)
	// Draining matters: a file longer than the cap leaves ffmpeg blocked on a
	// full pipe, and Wait would never return.
	_, _ = io.Copy(io.Discard, out)

	if err := cmd.Wait(); err != nil {
		if msg := strings.TrimSpace(stderr.String()); msg != "" {
			return nil, fmt.Errorf("decoding audio: %s", firstLine(msg))
		}
		return nil, fmt.Errorf("decoding audio: %w", err)
	}
	if readErr != nil {
		return nil, readErr
	}
	return samples, nil
}

func readSamples(r io.Reader, limit int) ([]int16, error) {
	buf := make([]byte, 32*1024)
	var samples []int16

	for len(samples) < limit {
		n, err := r.Read(buf)
		for i := 0; i+1 < n; i += 2 {
			samples = append(samples, int16(binary.LittleEndian.Uint16(buf[i:i+2])))
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return samples, err
		}
	}
	return samples, nil
}

// bars turns samples into a row of block characters.
//
// Each column is the root mean square of its slice, not the peak: a peak makes
// every column full height as soon as one click or breath lands in it, which
// draws a solid bar for every recording ever made.
func bars(samples []int16, cols int) string {
	levels := make([]float64, cols)
	peak := 0.0

	for c := 0; c < cols; c++ {
		lo := c * len(samples) / cols
		hi := (c + 1) * len(samples) / cols
		if hi <= lo {
			hi = lo + 1
		}
		if hi > len(samples) {
			hi = len(samples)
		}

		sum := 0.0
		for _, s := range samples[lo:hi] {
			v := float64(s)
			sum += v * v
		}
		rms := math.Sqrt(sum / float64(hi-lo))
		levels[c] = rms
		if rms > peak {
			peak = rms
		}
	}

	var b strings.Builder
	for _, l := range levels {
		// A silent recording would divide by zero, and every column is the
		// shortest bar anyway.
		idx := 0
		if peak > 0 {
			idx = int(l / peak * float64(len(waveBlocks)-1))
		}
		if idx < 0 {
			idx = 0
		}
		if idx >= len(waveBlocks) {
			idx = len(waveBlocks) - 1
		}
		b.WriteRune(waveBlocks[idx])
	}
	return b.String()
}

func firstLine(s string) string {
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		return s[:i]
	}
	return s
}

// waveTimeout bounds decoding, so a corrupt file cannot hang the interface.
const waveTimeout = 15 * time.Second
