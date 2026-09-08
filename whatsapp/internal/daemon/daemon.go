// Package daemon owns the wacli sync process wa talks to.
//
// Only one process may hold the wacli store lock, and `sync --follow` holds it
// for its whole life. While it runs it accepts delegated sends over a Unix
// socket in the store directory; wa therefore needs exactly one such process
// and must not start a second.
//
// The readiness signal is that socket, not wacli's own "connected" event and
// not the lock file. Measurements in docs/delegation-probe.md: the socket
// appears about a second after the connection, and a send issued in that gap
// fails with "store is locked". Nothing here polls `wacli doctor` either -
// doctor takes the store lock itself, and a poll loop against it starves the
// starting sync process out of ever acquiring it.
package daemon

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"syscall"
	"time"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/config"
)

// SendSocket is the delegation socket wacli's follow-mode sync creates.
const SendSocket = ".send.sock"

// Mode is how wa is getting its live updates.
type Mode int

const (
	// ModeSpawned means wa started the sync process and will reap it.
	ModeSpawned Mode = iota
	// ModeAdopted means a sync process wa started earlier is still running and
	// its webhook details were recovered from the state file.
	ModeAdopted
	// ModePolling means a sync process is running that wa did not start, so
	// its webhook cannot be received and the store is polled instead.
	ModePolling
	// ModeNone means no sync process is running and wa was told not to start
	// one. Nothing will arrive until something else syncs.
	ModeNone
)

func (m Mode) String() string {
	switch m {
	case ModeSpawned:
		return "running"
	case ModeAdopted:
		return "attached"
	case ModePolling:
		return "polling"
	default:
		return "off"
	}
}

// Options configure Start.
type Options struct {
	StoreDir  string
	StatePath string
	Cfg       config.Sync
	Port      int
	Secret    string

	// Bin is the wacli binary to spawn.
	Bin string

	// spawn is a test seam. Production leaves it nil and gets exec.Command.
	spawn func(name string, args ...string) *exec.Cmd
	// now is a test seam for the readiness deadline.
	clock func() time.Time
}

// Daemon supervises the sync process.
type Daemon struct {
	opts Options

	mu       sync.Mutex
	mode     Mode
	port     int
	secret   string
	cmd      *exec.Cmd
	status   string
	lastErr  error
	stopping bool

	done chan struct{}
}

// Start attaches to a running sync process or starts one.
func Start(ctx context.Context, opts Options) (*Daemon, error) {
	if opts.Bin == "" {
		opts.Bin = "wacli"
	}
	if opts.spawn == nil {
		opts.spawn = exec.Command
	}
	if opts.clock == nil {
		opts.clock = time.Now
	}

	d := &Daemon{opts: opts, done: make(chan struct{})}

	if SocketPresent(opts.StoreDir) {
		// Something already holds the lock. If it is a sync wa started, the
		// state file tells us where to listen; otherwise we cannot receive its
		// webhooks at all and must poll.
		if st, err := ReadState(opts.StatePath); err == nil && st.Alive() && st.Port > 0 {
			d.mode, d.port, d.secret = ModeAdopted, st.Port, st.Secret
			d.status = "attached to a running sync"
			return d, nil
		}
		d.mode = ModePolling
		d.status = "a sync process wa did not start holds the lock; polling the store"
		return d, nil
	}

	// A state file with no socket is stale: the process it named is gone.
	_ = os.Remove(opts.StatePath)

	if !opts.Cfg.Autostart {
		d.mode = ModeNone
		d.status = "no sync process, and sync.autostart is off"
		return d, nil
	}

	if err := d.spawnSync(ctx); err != nil {
		return nil, err
	}
	go d.supervise()
	return d, nil
}

func (d *Daemon) spawnSync(ctx context.Context) error {
	args := []string{
		"sync", "--follow",
		"--webhook", fmt.Sprintf("http://127.0.0.1:%d/e", d.opts.Port),
		"--webhook-allow-private",
		"--webhook-secret", d.opts.Secret,
		"--webhook-events", "message,receipt,chat_presence",
	}
	if d.opts.Cfg.DownloadMedia {
		args = append(args, "--download-media")
	}
	if d.opts.StoreDir != "" {
		args = append(args, "--store", d.opts.StoreDir)
	}

	cmd := d.opts.spawn(d.opts.Bin, args...)
	// Its own process group, so a Ctrl-C in the terminal that started wa does
	// not kill the sync process out from under the reaping logic.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("starting %s sync: %w", d.opts.Bin, err)
	}

	d.mu.Lock()
	d.cmd = cmd
	d.mode = ModeSpawned
	d.port = d.opts.Port
	d.secret = d.opts.Secret
	d.status = "starting"
	d.mu.Unlock()

	if err := WriteState(d.opts.StatePath, State{
		PID:       cmd.Process.Pid,
		Port:      d.opts.Port,
		Secret:    d.opts.Secret,
		Owned:     true,
		StartedAt: time.Now(),
	}); err != nil {
		return fmt.Errorf("recording the sync process: %w", err)
	}

	if err := d.waitForSocket(ctx); err != nil {
		d.setStatus("started, but not accepting sends yet: " + err.Error())
	} else {
		d.setStatus("running")
	}
	return nil
}

// waitForSocket blocks until the delegation socket appears. Until it does, a
// send fails with "store is locked" rather than being queued, so the composer
// must not offer to send yet.
func (d *Daemon) waitForSocket(ctx context.Context) error {
	deadline := d.opts.clock().Add(d.opts.Cfg.SendSocketWait.D())
	if d.opts.Cfg.SendSocketWait == 0 {
		deadline = d.opts.clock().Add(15 * time.Second)
	}
	for {
		if SocketPresent(d.opts.StoreDir) {
			return nil
		}
		if d.opts.clock().After(deadline) {
			return fmt.Errorf("no %s after %s", SendSocket, d.opts.Cfg.SendSocketWait)
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(100 * time.Millisecond):
		}
	}
}

// supervise restarts a spawned sync process that dies unexpectedly.
func (d *Daemon) supervise() {
	backoff := time.Second
	const maxBackoff = 30 * time.Second

	for {
		d.mu.Lock()
		cmd := d.cmd
		d.mu.Unlock()
		if cmd == nil {
			return
		}

		err := cmd.Wait()

		d.mu.Lock()
		stopping := d.stopping
		d.mu.Unlock()
		if stopping {
			return
		}

		d.mu.Lock()
		d.lastErr = err
		d.status = "reconnecting"
		d.mu.Unlock()

		select {
		case <-d.done:
			return
		case <-time.After(backoff):
		}
		if backoff *= 2; backoff > maxBackoff {
			backoff = maxBackoff
		}

		if err := d.spawnSync(context.Background()); err != nil {
			d.mu.Lock()
			d.lastErr = err
			d.mu.Unlock()
			continue
		}
		backoff = time.Second
	}
}

// Stop reaps the sync process, but only if wa started it. A sync somebody else
// is running is left alone.
func (d *Daemon) Stop() error {
	d.mu.Lock()
	if d.stopping {
		d.mu.Unlock()
		return nil
	}
	d.stopping = true
	cmd := d.cmd
	owned := d.mode == ModeSpawned
	d.mu.Unlock()

	close(d.done)

	if !owned || cmd == nil || cmd.Process == nil {
		return nil
	}

	_ = cmd.Process.Signal(syscall.SIGTERM)

	exited := make(chan struct{})
	go func() {
		_, _ = cmd.Process.Wait()
		close(exited)
	}()
	select {
	case <-exited:
	case <-time.After(3 * time.Second):
		_ = cmd.Process.Kill()
	}

	return os.Remove(d.opts.StatePath)
}

// Mode reports how updates are arriving.
func (d *Daemon) Mode() Mode {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.mode
}

// Port is the webhook port to listen on, or zero when polling.
func (d *Daemon) Port() int {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.port
}

// Secret is the webhook HMAC secret.
func (d *Daemon) Secret() string {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.secret
}

// Status is a short phrase for the status line.
func (d *Daemon) Status() string {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.status
}

func (d *Daemon) setStatus(s string) {
	d.mu.Lock()
	d.status = s
	d.mu.Unlock()
}

// SendReady reports whether a send would be accepted right now. Until the
// delegation socket exists, wacli answers a send with "store is locked".
func (d *Daemon) SendReady() bool {
	if d.Mode() == ModeNone {
		// No sync holds the lock, so a send takes it directly.
		return !SocketPresent(d.opts.StoreDir)
	}
	return SocketPresent(d.opts.StoreDir)
}

// SocketPresent reports whether a follow-mode sync is offering the delegation
// socket in this store directory.
func SocketPresent(storeDir string) bool {
	if storeDir == "" {
		return false
	}
	fi, err := os.Stat(filepath.Join(storeDir, SendSocket))
	if err != nil {
		return false
	}
	return fi.Mode()&os.ModeSocket != 0
}
