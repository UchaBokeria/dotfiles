package clipboard

import (
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

func TestSyncFileKeepsConcurrentWritesWhole(t *testing.T) {
	// The renderer and the clipboard write at once. Each write has to arrive
	// in one piece or an escape sequence is cut in half on screen.
	f, err := os.Create(filepath.Join(t.TempDir(), "tty"))
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	s := NewSyncFile(f)

	var wg sync.WaitGroup
	chunkA := "\x1b]52;c;" + strings.Repeat("A", 4000) + "\x07"
	chunkB := "\x1b[H" + strings.Repeat("B", 4000) + "\x1b[0m"
	for i := 0; i < 50; i++ {
		wg.Add(2)
		go func() { defer wg.Done(); s.Write([]byte(chunkA)) }()
		go func() { defer wg.Done(); s.Write([]byte(chunkB)) }()
	}
	wg.Wait()

	body, _ := os.ReadFile(f.Name())
	text := string(body)
	for len(text) > 0 {
		switch {
		case strings.HasPrefix(text, chunkA):
			text = text[len(chunkA):]
		case strings.HasPrefix(text, chunkB):
			text = text[len(chunkB):]
		default:
			t.Fatalf("interleaved write found at byte %d", len(body)-len(text))
		}
	}
}
