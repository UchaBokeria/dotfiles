package ui

import (
	"context"
	"sync"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// fetchQueue is how many messages may be waiting to download. It is small on
// purpose: the queue is fed while drawing, so a long scroll would otherwise
// enqueue hundreds of attachments the moment they flick past, and finish
// downloading them long after the user has gone somewhere else.
const fetchQueue = 32

// retryDelay is how long a failed download is left alone before the message
// may be queued again.
const retryDelay = 60 * time.Second

// downloader is what the fetcher needs from the wacli client.
type downloader interface {
	Raw(ctx context.Context, args ...string) ([]byte, error)
}

// filer downloads an attachment and files it where wa can find it again.
type filer interface {
	Fetch(chatJID, msgID string, run func(args []string) error) (string, error)
}

// fetcher downloads small attachments in the background, so a conversation of
// photographs shows photographs rather than a column of filenames.
//
// It runs one download at a time. Attachments are small by definition here -
// anything over the configured limit is left for <leader>d - and a single
// worker keeps the network and the terminal both calm while scrolling.
type fetcher struct {
	client downloader
	cache  filer
	// done is closed-over by the app: one value per completed download, so the
	// pane can be invalidated and the preview drawn.
	done chan struct{}

	queue chan job

	mu   sync.Mutex
	seen map[string]bool

	start sync.Once
	stop  chan struct{}
}

type job struct {
	chatJID string
	msgID   string
}

func newFetcher(client downloader, cache filer) *fetcher {
	return &fetcher{
		client: client,
		cache:  cache,
		done:   make(chan struct{}, fetchQueue),
		queue:  make(chan job, fetchQueue),
		seen:   map[string]bool{},
		stop:   make(chan struct{}),
	}
}

// Done fires once per finished download, successful or not: either way the
// pane should look again, because a failure must not leave a message waiting
// for a preview that is never coming.
func (f *fetcher) Done() <-chan struct{} { return f.done }

// Want queues a message's attachment, unless it is already queued, already
// tried, or the queue is full.
//
// It is called from the draw path and never blocks. Dropping a request when
// the queue is full is correct rather than merely convenient: the message will
// be drawn again on the next frame, and asked for again then.
func (f *fetcher) Want(m domain.Message) {
	if f == nil || f.client == nil || m.Media == nil || m.ID == "" {
		return
	}

	f.mu.Lock()
	if f.seen[m.ID] {
		f.mu.Unlock()
		return
	}
	f.seen[m.ID] = true
	f.mu.Unlock()

	select {
	case f.queue <- job{chatJID: m.StoreJID().String(), msgID: m.ID}:
		f.start.Do(func() { go f.run() })
	default:
		// The queue is full. Forget it so a later frame can ask again.
		f.mu.Lock()
		delete(f.seen, m.ID)
		f.mu.Unlock()
	}
}

// Close stops the worker.
func (f *fetcher) Close() {
	if f == nil {
		return
	}
	select {
	case <-f.stop:
	default:
		close(f.stop)
	}
}

func (f *fetcher) run() {
	for {
		select {
		case <-f.stop:
			return
		case j := <-f.queue:
			f.fetch(j)
		}
	}
}

func (f *fetcher) fetch(j job) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	// The error goes nowhere visible: an attachment nobody asked for failing
	// to download is not worth a line on the status bar, and the chip beneath
	// it already says the file is not here. It does decide whether to try
	// again, though - a message left marked as seen after a network blip
	// would never get its preview until the program was restarted.
	_, err := f.cache.Fetch(j.chatJID, j.msgID, func(args []string) error {
		_, err := f.client.Raw(ctx, args...)
		return err
	})
	if err != nil {
		f.retryAfter(j.msgID, retryDelay)
	}

	select {
	case f.done <- struct{}{}:
	default:
	}
}

// retryAfter lets a failed message be queued again once the delay is up. The
// delay is what stops a permanently unavailable attachment - one WhatsApp no
// longer holds - from being retried on every frame it is drawn on.
func (f *fetcher) retryAfter(msgID string, d time.Duration) {
	time.AfterFunc(d, func() {
		f.mu.Lock()
		delete(f.seen, msgID)
		f.mu.Unlock()
	})
}
