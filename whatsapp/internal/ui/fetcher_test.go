package ui

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/media"
)

type fakeDownloader struct {
	mu    sync.Mutex
	calls [][]string
	err   error
	// gate blocks each call until it is read from, so a test can hold the
	// worker still and watch the queue fill.
	gate chan struct{}
}

func (f *fakeDownloader) Raw(ctx context.Context, args ...string) ([]byte, error) {
	if f.gate != nil {
		<-f.gate
	}
	f.mu.Lock()
	f.calls = append(f.calls, args)
	err := f.err
	f.mu.Unlock()
	return nil, err
}

func (f *fakeDownloader) count() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return len(f.calls)
}

// testCache stands in for the media cache: it records the arguments a fetch
// would have run and reports a file, without touching the disk.
type testCache struct{}

func (testCache) Fetch(chatJID, msgID string, run func(args []string) error) (string, error) {
	if err := run([]string{"media", "download", "--chat", chatJID, "--id", msgID}); err != nil {
		return "", err
	}
	return "/tmp/message-" + msgID, nil
}

func mediaMessage(id string, length int64) domain.Message {
	jid, err := domain.ParseJID("995000000000@s.whatsapp.net")
	if err != nil {
		panic(err)
	}
	return domain.Message{
		ID:      id,
		ChatJID: jid,
		Media:   &domain.MediaRef{Type: "image", MimeType: "image/jpeg", Length: length},
	}
}

func waitFor(t *testing.T, f *fetcher, n int) {
	t.Helper()
	deadline := time.After(2 * time.Second)
	for i := 0; i < n; i++ {
		select {
		case <-f.Done():
		case <-deadline:
			t.Fatalf("only %d of %d downloads finished", i, n)
		}
	}
}

func TestFetcherDownloadsOnce(t *testing.T) {
	dl := &fakeDownloader{}
	f := newFetcher(dl, testCache{})
	defer f.Close()

	m := mediaMessage("ABC", 1000)
	f.Want(m)
	f.Want(m)
	f.Want(m)
	waitFor(t, f, 1)

	// Give any duplicate a chance to arrive before counting.
	time.Sleep(50 * time.Millisecond)
	if n := dl.count(); n != 1 {
		t.Errorf("downloaded %d times, want 1", n)
	}
}

func TestFetcherPassesTheRightArguments(t *testing.T) {
	dl := &fakeDownloader{}
	f := newFetcher(dl, testCache{})
	defer f.Close()

	f.Want(mediaMessage("XYZ", 1000))
	waitFor(t, f, 1)

	dl.mu.Lock()
	got := dl.calls[0]
	dl.mu.Unlock()

	want := []string{"media", "download", "--chat", "995000000000@s.whatsapp.net", "--id", "XYZ"}
	if len(got) != len(want) {
		t.Fatalf("args = %v", got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("args = %v, want %v", got, want)
		}
	}
}

func TestFetcherRetriesAfterAFailure(t *testing.T) {
	// A network blip must not leave a message without a preview until the
	// program is restarted.
	dl := &fakeDownloader{err: errors.New("no network")}
	f := newFetcher(dl, testCache{})
	defer f.Close()

	f.Want(mediaMessage("ABC", 1000))
	waitFor(t, f, 1)

	// The real cooldown is a minute; reach in rather than wait for it.
	f.mu.Lock()
	delete(f.seen, "ABC")
	f.mu.Unlock()

	dl.mu.Lock()
	dl.err = nil
	dl.mu.Unlock()

	f.Want(mediaMessage("ABC", 1000))
	waitFor(t, f, 1)

	if n := dl.count(); n != 2 {
		t.Errorf("tried %d times, want 2", n)
	}
}

func TestFetcherKeepsASuccessfulMessageOutOfTheQueue(t *testing.T) {
	dl := &fakeDownloader{}
	f := newFetcher(dl, testCache{})
	defer f.Close()

	f.Want(mediaMessage("ABC", 1000))
	waitFor(t, f, 1)

	// A success is remembered, so redrawing the same message asks for nothing.
	f.Want(mediaMessage("ABC", 1000))
	time.Sleep(50 * time.Millisecond)
	if n := dl.count(); n != 1 {
		t.Errorf("downloaded %d times, want 1", n)
	}
}

func TestFetcherDropsRequestsWhenTheQueueIsFull(t *testing.T) {
	// Want is called from the draw path and must never block, however fast a
	// scroll pushes messages past.
	dl := &fakeDownloader{gate: make(chan struct{})}
	f := newFetcher(dl, testCache{})
	defer f.Close()

	done := make(chan struct{})
	go func() {
		for i := 0; i < fetchQueue*4; i++ {
			f.Want(mediaMessage(string(rune('a'+i%26))+itoa(i), 1000))
		}
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("Want blocked")
	}

	// A dropped request must not be remembered, or the message would never be
	// fetched however many times it is drawn.
	f.mu.Lock()
	seen := len(f.seen)
	f.mu.Unlock()
	if seen > fetchQueue+1 {
		t.Errorf("%d messages remembered with a queue of %d", seen, fetchQueue)
	}

	close(dl.gate)
}

func TestFetcherIgnoresAMessageWithNoMedia(t *testing.T) {
	dl := &fakeDownloader{}
	f := newFetcher(dl, testCache{})
	defer f.Close()

	f.Want(domain.Message{ID: "ABC"})
	f.Want(domain.Message{Media: &domain.MediaRef{Type: "image"}})

	time.Sleep(50 * time.Millisecond)
	if n := dl.count(); n != 0 {
		t.Errorf("downloaded %d times, want 0", n)
	}
}

func TestNilFetcherIsSafe(t *testing.T) {
	var f *fetcher
	f.Want(mediaMessage("ABC", 1000))
	f.Close()
}

func newTestMediaView(t *testing.T, dl downloader, autoMax int64) *mediaView {
	t.Helper()
	cache := media.NewCache(t.TempDir())
	v := &mediaView{
		r:       media.NewRenderer(media.Options{CacheDir: t.TempDir()}),
		cache:   cache,
		enabled: true,
		autoMax: autoMax,
	}
	if dl != nil {
		v.fetch = newFetcher(dl, cache)
	}
	return v
}

func TestAutoDownloadSkipsWhatIsTooBig(t *testing.T) {
	// The size limit is the whole safety mechanism: without it, opening a
	// chat full of videos would start downloading all of them.
	dl := &fakeDownloader{}
	v := newTestMediaView(t, dl, 1<<20)
	defer v.fetch.Close()

	v.PreviewLines(mediaMessage("BIG", 40<<20), 40, 10)
	time.Sleep(50 * time.Millisecond)
	if n := dl.count(); n != 0 {
		t.Errorf("a 40MB attachment was fetched under a 1MB limit")
	}
}

func TestAutoDownloadTakesWhatIsSmall(t *testing.T) {
	dl := &fakeDownloader{}
	v := newTestMediaView(t, dl, 1<<20)
	defer v.fetch.Close()

	v.PreviewLines(mediaMessage("SMALL", 200<<10), 40, 10)
	waitFor(t, v.fetch, 1)
	if n := dl.count(); n != 1 {
		t.Errorf("downloaded %d times, want 1", n)
	}
}

func TestAutoDownloadOffByConfiguration(t *testing.T) {
	dl := &fakeDownloader{}
	v := newTestMediaView(t, dl, 0)
	defer v.fetch.Close()

	v.PreviewLines(mediaMessage("SMALL", 200<<10), 40, 10)
	time.Sleep(50 * time.Millisecond)
	if n := dl.count(); n != 0 {
		t.Errorf("auto_download = 0 still fetched %d", n)
	}
}

func TestAutoDownloadSkipsAnUnknownSize(t *testing.T) {
	// A store row with no file_length says nothing about how big the file is,
	// and guessing wrong is how a video gets fetched on a metered connection.
	dl := &fakeDownloader{}
	v := newTestMediaView(t, dl, 1<<20)
	defer v.fetch.Close()

	v.PreviewLines(mediaMessage("UNKNOWN", 0), 40, 10)
	time.Sleep(50 * time.Millisecond)
	if n := dl.count(); n != 0 {
		t.Errorf("an attachment of unknown size was fetched")
	}
}

func TestPreviewsOffDoNotDownload(t *testing.T) {
	dl := &fakeDownloader{}
	v := newTestMediaView(t, dl, 1<<20)
	v.enabled = false
	defer v.fetch.Close()

	v.PreviewLines(mediaMessage("SMALL", 200<<10), 40, 10)
	time.Sleep(50 * time.Millisecond)
	if n := dl.count(); n != 0 {
		t.Errorf("previews are off but %d downloads started", n)
	}
}
