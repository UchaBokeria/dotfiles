package daemon

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

// Delegated names the commands a running `sync --follow` accepts on behalf of
// another process, over the socket in the store directory. Everything else
// needs the lock itself.
//
// Measured, not assumed: with a sync running, `chats pin` answers "store is
// locked" while `send text` goes through. wacli documents the delegated set as
// send text/file/sticker/voice/react and messages edit.
var Delegated = map[string]bool{
	"send text":     true,
	"send file":     true,
	"send sticker":  true,
	"send voice":    true,
	"send react":    true,
	"messages edit": true,
}

// NeedsLock reports whether a command must hold the store lock itself.
func NeedsLock(args ...string) bool {
	if len(args) < 2 {
		return true
	}
	return !Delegated[args[0]+" "+args[1]]
}

// gateMu serialises lock handovers. Two of them at once would have one restart
// the sync process while the other is still working without it.
var gateMu sync.Mutex

// WithLock runs fn with the store lock available.
//
// When wa owns the sync process it stops it, waits for the lock to clear, runs
// fn, and starts it again. That handover costs a few seconds, which is why it
// is only used for the commands that cannot be delegated - pinning, muting,
// archiving, deleting, forwarding, downloading media.
//
// When the lock is held by a sync wa did not start, there is nothing to stop:
// fn runs and fails, and the error says who is holding it, which is more use
// than a spinner that never resolves.
func (d *Daemon) WithLock(ctx context.Context, fn func(context.Context) error) error {
	if d == nil {
		return fn(ctx)
	}

	gateMu.Lock()
	defer gateMu.Unlock()

	d.mu.Lock()
	mode := d.mode
	haveChild := d.cmd != nil && d.cmd.Process != nil
	d.mu.Unlock()

	switch {
	case mode == ModeSpawned && haveChild:
		// Our own child; the ordinary case.

	case mode == ModeAdopted:
		// A sync started by some earlier wa. Whether it may be stopped depends
		// on whether that wa is still open.
		return d.withAdoptedLock(ctx, fn)

	default:
		if holder, ok := lockHolder(d.opts.StoreDir); ok && holder != os.Getpid() {
			if err := fn(ctx); err != nil {
				return fmt.Errorf("%w (the store lock is held by pid %d, which wa did not start)", err, holder)
			}
			return nil
		}
		return fn(ctx)
	}

	d.setStatus("pausing sync")
	if err := d.pause(); err != nil {
		return fmt.Errorf("pausing the sync process: %w", err)
	}

	runErr := fn(ctx)

	// The sync process is restarted whatever happened, so a failure in fn
	// cannot leave the client without live updates.
	if err := d.resume(ctx); err != nil {
		if runErr != nil {
			return fmt.Errorf("%w (and the sync process did not restart: %v)", runErr, err)
		}
		return fmt.Errorf("restarting the sync process: %w", err)
	}
	return runErr
}

// withAdoptedLock stops a sync process recorded in the state file, runs fn,
// and then starts one of our own so live updates resume.
func (d *Daemon) withAdoptedLock(ctx context.Context, fn func(context.Context) error) error {
	st, err := ReadState(d.opts.StatePath)
	if err != nil || !st.Owned || !st.Alive() {
		// Not ours after all; run and let the error explain itself.
		return fn(ctx)
	}

	// Another wa is open and this sync belongs to it. Stopping it would start
	// a tug of war: that client's supervisor would restart the process, this
	// one would stop it again, and neither would get anything done. Say so
	// instead.
	if st.OwnerAlive() && st.OwnerPID != os.Getpid() {
		return fmt.Errorf(
			"another wa (pid %d) is holding the store; run this there, or close it first",
			st.OwnerPID)
	}

	d.setStatus("pausing sync")
	if p, err := os.FindProcess(st.PID); err == nil {
		_ = p.Signal(syscall.SIGTERM)
	}
	waitForRelease(d.opts.StoreDir, 10*time.Second)

	runErr := fn(ctx)

	// Take ownership: the old process is gone, so this one starts its own and
	// stops being a session that merely watches.
	d.mu.Lock()
	d.paused = false
	d.mu.Unlock()

	if err := d.spawnSync(ctx); err != nil {
		if runErr != nil {
			return fmt.Errorf("%w (and no sync process could be started: %v)", runErr, err)
		}
		return fmt.Errorf("starting a sync process: %w", err)
	}
	d.Supervise()
	return runErr
}

// waitForRelease blocks until nothing holds the store lock.
func waitForRelease(storeDir string, timeout time.Duration) {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if !SocketPresent(storeDir) {
			if _, held := lockHolder(storeDir); !held {
				return
			}
		}
		time.Sleep(100 * time.Millisecond)
	}
}

// pause stops the sync process and waits for the lock to be released.
func (d *Daemon) pause() error {
	d.mu.Lock()
	cmd := d.cmd
	d.paused = true
	d.mu.Unlock()

	if cmd == nil || cmd.Process == nil {
		return nil
	}
	// SIGSTOP would not do: a stopped process still holds its lock.
	_ = cmd.Process.Signal(syscall.SIGTERM)

	waitForRelease(d.opts.StoreDir, 10*time.Second)
	if _, held := lockHolder(d.opts.StoreDir); held {
		_ = cmd.Process.Kill()
		waitForRelease(d.opts.StoreDir, 3*time.Second)
	}
	return nil
}

// resume starts the sync process again.
func (d *Daemon) resume(ctx context.Context) error {
	d.mu.Lock()
	d.paused = false
	d.mu.Unlock()

	if err := d.spawnSync(ctx); err != nil {
		d.setStatus("sync did not restart")
		return err
	}
	d.Supervise()
	return nil
}

// Paused reports whether the sync process is deliberately stopped, so the
// supervisor does not treat the gap as a crash.
func (d *Daemon) Paused() bool {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.paused
}

// lockHolder reads the advisory pidfile.
func lockHolder(storeDir string) (int, bool) {
	body, err := os.ReadFile(filepath.Join(storeDir, "LOCK"))
	if err != nil {
		return 0, false
	}
	for _, line := range strings.Split(string(body), "\n") {
		rest, found := strings.CutPrefix(strings.TrimSpace(line), "pid=")
		if !found {
			continue
		}
		pid, err := strconv.Atoi(rest)
		if err != nil {
			return 0, false
		}
		// A pidfile outlives the process that wrote it, so liveness decides.
		if p, err := os.FindProcess(pid); err == nil && p.Signal(syscall.Signal(0)) == nil {
			return pid, true
		}
		return pid, false
	}
	return 0, false
}

// WaitSendReady blocks until a send would be accepted, or the timeout passes.
//
// A send is delegated over the socket a follow-mode sync offers, and that
// socket is gone for the few seconds a lock handover takes. Refusing the send
// outright was tolerable while those handovers froze the interface - nobody
// could type during one. Now that they run in the background, a message typed
// while a chat is being pinned would be thrown away for no reason the person
// typing could see, so it waits instead.
func (d *Daemon) WaitSendReady(ctx context.Context, timeout time.Duration) error {
	if d == nil || d.SendReady() {
		return nil
	}
	deadline := time.Now().Add(timeout)
	tick := time.NewTicker(100 * time.Millisecond)
	defer tick.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-tick.C:
			if d.SendReady() {
				return nil
			}
			if time.Now().After(deadline) {
				return fmt.Errorf("the sync process is not accepting sends (it has been busy for %s)", timeout)
			}
		}
	}
}
