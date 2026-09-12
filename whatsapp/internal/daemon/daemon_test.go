package daemon

import (
	"context"
	"errors"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
)

func syncCfg() config.Sync {
	return config.Sync{
		Autostart:      true,
		PollInterval:   config.Duration(50 * time.Millisecond),
		SendSocketWait: config.Duration(3 * time.Second),
	}
}

// listen creates the delegation socket, standing in for a follow-mode sync.
func listen(t *testing.T, storeDir string) net.Listener {
	t.Helper()
	l, err := net.Listen("unix", filepath.Join(storeDir, SendSocket))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { l.Close() })
	return l
}

// recorder captures the arguments a spawn was asked for and runs a harmless
// long-lived process in place of wacli.
type recorder struct {
	mu   sync.Mutex
	args [][]string
	// onSpawn runs after the command is built, so a test can make the
	// delegation socket appear the way a real sync process would.
	onSpawn func()
}

func (r *recorder) spawn(name string, args ...string) *exec.Cmd {
	r.mu.Lock()
	r.args = append(r.args, append([]string{name}, args...))
	hook := r.onSpawn
	r.mu.Unlock()
	if hook != nil {
		go hook()
	}
	return exec.Command("sleep", "30")
}

func (r *recorder) calls() [][]string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.args
}

func TestStateRoundTripAndPermissions(t *testing.T) {
	p := filepath.Join(t.TempDir(), "daemon.json")
	in := State{PID: os.Getpid(), Port: 1234, Secret: "abc", Owned: true, StartedAt: time.Now()}
	if err := WriteState(p, in); err != nil {
		t.Fatal(err)
	}
	fi, err := os.Stat(p)
	if err != nil {
		t.Fatal(err)
	}
	if fi.Mode().Perm() != 0o600 {
		t.Errorf("mode = %v, want 0600 - the file holds the webhook secret", fi.Mode().Perm())
	}
	out, err := ReadState(p)
	if err != nil {
		t.Fatal(err)
	}
	if out.Port != 1234 || out.Secret != "abc" || !out.Owned {
		t.Errorf("round trip = %+v", out)
	}
	if !out.Alive() {
		t.Error("our own pid should read as alive")
	}
}

func TestStaleStateIsNotAlive(t *testing.T) {
	if (State{PID: 0}).Alive() {
		t.Error("pid 0 must not read as alive")
	}
	if (State{PID: 4294967}).Alive() {
		t.Error("an impossible pid must not read as alive")
	}
}

func TestSocketPresent(t *testing.T) {
	dir := t.TempDir()
	if SocketPresent(dir) {
		t.Fatal("an empty store must have no socket")
	}
	listen(t, dir)
	if !SocketPresent(dir) {
		t.Fatal("the socket was not detected")
	}
}

func TestSocketPresentIgnoresAPlainFile(t *testing.T) {
	// A leftover regular file with the socket's name must not be mistaken for
	// a running sync, or every send would fail with "store is locked".
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, SendSocket), []byte("not a socket"), 0o644)
	if SocketPresent(dir) {
		t.Fatal("a regular file was mistaken for the delegation socket")
	}
}

func TestStartAdoptsWhenOurOwnSyncIsRunning(t *testing.T) {
	dir := t.TempDir()
	listen(t, dir)
	statePath := filepath.Join(dir, "daemon.json")
	WriteState(statePath, State{PID: os.Getpid(), Port: 4321, Secret: "s3cret", Owned: true})

	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: statePath, Cfg: syncCfg(),
		spawn: func(string, ...string) *exec.Cmd { t.Fatal("must not spawn"); return nil },
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()

	if d.Mode() != ModeAdopted {
		t.Fatalf("mode = %v, want ModeAdopted", d.Mode())
	}
	if d.Port() != 4321 || d.Secret() != "s3cret" {
		t.Errorf("port/secret = %d/%q, want the recorded pair", d.Port(), d.Secret())
	}
}

func TestStartPollsWhenAStrangerHoldsTheLock(t *testing.T) {
	// A sync started by hand in a shell: its webhook goes somewhere we cannot
	// hear, so the only honest option is to poll and say so.
	dir := t.TempDir()
	listen(t, dir)

	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: filepath.Join(dir, "absent.json"), Cfg: syncCfg(),
		spawn: func(string, ...string) *exec.Cmd { t.Fatal("must not spawn a second sync"); return nil },
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()

	if d.Mode() != ModePolling {
		t.Fatalf("mode = %v, want ModePolling", d.Mode())
	}
	if !strings.Contains(d.Status(), "polling") {
		t.Errorf("status = %q, want the degradation to be visible", d.Status())
	}
}

func TestStartPollsWhenTheStateFileIsStale(t *testing.T) {
	dir := t.TempDir()
	listen(t, dir)
	statePath := filepath.Join(dir, "daemon.json")
	WriteState(statePath, State{PID: 4294967, Port: 4321, Secret: "x", Owned: true})

	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: statePath, Cfg: syncCfg(),
		spawn: func(string, ...string) *exec.Cmd { t.Fatal("must not spawn"); return nil },
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()
	if d.Mode() != ModePolling {
		t.Fatalf("mode = %v, want ModePolling for a dead pid", d.Mode())
	}
}

func TestStartSpawnsWhenNothingIsRunning(t *testing.T) {
	dir := t.TempDir()
	statePath := filepath.Join(dir, "daemon.json")

	// The listener is opened on the spawn goroutine and closed on the test's,
	// so it needs a lock of its own.
	var (
		mu sync.Mutex
		l  net.Listener
	)
	r := &recorder{onSpawn: func() {
		time.Sleep(80 * time.Millisecond)
		got, _ := net.Listen("unix", filepath.Join(dir, SendSocket))
		mu.Lock()
		l = got
		mu.Unlock()
	}}
	t.Cleanup(func() {
		mu.Lock()
		defer mu.Unlock()
		if l != nil {
			l.Close()
		}
	})

	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: statePath, Cfg: syncCfg(),
		Port: 7777, Secret: "topsecret", Bin: "wacli", spawn: r.spawn,
	})
	if err != nil {
		t.Fatal(err)
	}

	if d.Mode() != ModeSpawned {
		t.Fatalf("mode = %v, want ModeSpawned", d.Mode())
	}
	if d.Status() != "running" {
		t.Errorf("status = %q, want running once the socket appeared", d.Status())
	}

	calls := r.calls()
	if len(calls) != 1 {
		t.Fatalf("spawned %d times, want 1", len(calls))
	}
	got := strings.Join(calls[0], " ")
	for _, want := range []string{
		"sync --follow",
		"--webhook http://127.0.0.1:7777/e",
		"--webhook-allow-private",
		"--webhook-secret topsecret",
		"--webhook-events message,receipt,chat_presence",
	} {
		if !strings.Contains(got, want) {
			t.Errorf("spawn is missing %q: %s", want, got)
		}
	}

	st, err := ReadState(statePath)
	if err != nil {
		t.Fatal(err)
	}
	if !st.Owned || st.Port != 7777 {
		t.Errorf("state = %+v", st)
	}

	if err := d.Stop(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(statePath); !os.IsNotExist(err) {
		t.Error("Stop must remove the state file it owns")
	}
}

func TestSpawnReportsWhenTheSocketNeverAppears(t *testing.T) {
	dir := t.TempDir()
	cfg := syncCfg()
	cfg.SendSocketWait = config.Duration(150 * time.Millisecond)

	r := &recorder{}
	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: filepath.Join(dir, "daemon.json"), Cfg: cfg,
		Port: 1, Secret: "s", spawn: r.spawn,
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()

	if !strings.Contains(d.Status(), "not accepting sends") {
		t.Errorf("status = %q, want it to say sends are not ready", d.Status())
	}
	if d.SendReady() {
		t.Error("SendReady must be false while the delegation socket is absent")
	}
}

func TestStopLeavesAnAdoptedProcessAlone(t *testing.T) {
	dir := t.TempDir()
	listen(t, dir)
	statePath := filepath.Join(dir, "daemon.json")
	WriteState(statePath, State{PID: os.Getpid(), Port: 4321, Secret: "s", Owned: true})

	d, _ := Start(context.Background(), Options{
		StoreDir: dir, StatePath: statePath, Cfg: syncCfg(),
		spawn: func(string, ...string) *exec.Cmd { return exec.Command("true") },
	})
	if err := d.Stop(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(statePath); err != nil {
		t.Error("an adopted daemon's state file belongs to whoever wrote it and must survive Stop")
	}
}

func TestAutostartOffDoesNotSpawn(t *testing.T) {
	dir := t.TempDir()
	cfg := syncCfg()
	cfg.Autostart = false

	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: filepath.Join(dir, "daemon.json"), Cfg: cfg,
		spawn: func(string, ...string) *exec.Cmd { t.Fatal("autostart is off"); return nil },
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()
	if d.Mode() != ModeNone {
		t.Fatalf("mode = %v, want ModeNone", d.Mode())
	}
}

func TestStaleStateWithNoSocketIsRemoved(t *testing.T) {
	dir := t.TempDir()
	statePath := filepath.Join(dir, "daemon.json")
	WriteState(statePath, State{PID: 4294967, Port: 1, Secret: "x", Owned: true})

	cfg := syncCfg()
	cfg.Autostart = false
	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: statePath, Cfg: cfg,
		spawn: func(string, ...string) *exec.Cmd { return exec.Command("true") },
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()

	if _, err := os.Stat(statePath); !os.IsNotExist(err) {
		t.Error("a state file naming a dead process must be cleaned up, not adopted later")
	}
}

func TestSendReadyWithNoSyncAtAll(t *testing.T) {
	// Nothing holds the lock, so a send takes it directly and is fine.
	dir := t.TempDir()
	cfg := syncCfg()
	cfg.Autostart = false
	d, _ := Start(context.Background(), Options{
		StoreDir: dir, StatePath: filepath.Join(dir, "daemon.json"), Cfg: cfg,
	})
	defer d.Stop()
	if !d.SendReady() {
		t.Error("with no sync running, a send should be possible")
	}
}

func TestStopIsIdempotent(t *testing.T) {
	dir := t.TempDir()
	listen(t, dir)
	d, _ := Start(context.Background(), Options{
		StoreDir: dir, StatePath: filepath.Join(dir, "absent.json"), Cfg: syncCfg(),
	})
	if err := d.Stop(); err != nil {
		t.Fatal(err)
	}
	if err := d.Stop(); err != nil {
		t.Errorf("second Stop returned %v", err)
	}
}

// --- the lock gate ----------------------------------------------------------

func TestNeedsLock(t *testing.T) {
	// Measured against the real wacli: sends and reactions are delegated to a
	// running sync; everything else needs the lock itself.
	cases := []struct {
		args []string
		want bool
	}{
		{[]string{"send", "text"}, false},
		{[]string{"send", "react"}, false},
		{[]string{"messages", "edit"}, false},
		{[]string{"chats", "pin"}, true},
		{[]string{"chats", "mark-read"}, true},
		{[]string{"media", "download"}, true},
		{[]string{"messages", "revoke"}, true},
		{[]string{"messages", "forward"}, true},
		{[]string{"doctor"}, true},
	}
	for _, c := range cases {
		if got := NeedsLock(c.args...); got != c.want {
			t.Errorf("NeedsLock(%v) = %v, want %v", c.args, got, c.want)
		}
	}
}

func TestWithLockRunsTheWorkWhenNothingHoldsTheLock(t *testing.T) {
	dir := t.TempDir()
	cfg := syncCfg()
	cfg.Autostart = false
	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: filepath.Join(dir, "daemon.json"), Cfg: cfg,
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()

	ran := false
	if err := d.WithLock(context.Background(), func(context.Context) error {
		ran = true
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if !ran {
		t.Error("the work never ran")
	}
}

func TestWithLockStopsAndRestartsOurOwnSync(t *testing.T) {
	dir := t.TempDir()
	statePath := filepath.Join(dir, "daemon.json")

	var (
		mu sync.Mutex
		ls []net.Listener
	)
	// The stand-in sync creates the delegation socket, as the real one does,
	// and drops it when told to stop.
	makeSocket := func() {
		mu.Lock()
		defer mu.Unlock()
		l, err := net.Listen("unix", filepath.Join(dir, SendSocket))
		if err == nil {
			ls = append(ls, l)
		}
	}
	dropSocket := func() {
		mu.Lock()
		defer mu.Unlock()
		for _, l := range ls {
			l.Close()
		}
		ls = nil
		os.Remove(filepath.Join(dir, SendSocket))
	}
	t.Cleanup(dropSocket)

	spawns := 0
	spawn := func(name string, args ...string) *exec.Cmd {
		spawns++
		go func() {
			time.Sleep(50 * time.Millisecond)
			makeSocket()
		}()
		return exec.Command("sleep", "30")
	}

	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: statePath, Cfg: syncCfg(),
		Port: 1, Secret: "s", spawn: spawn,
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()

	if d.Mode() != ModeSpawned {
		t.Fatalf("mode = %v", d.Mode())
	}

	// The work runs with the socket gone, which is what "has the lock" means
	// from the point of view of anything wa shells out to.
	sawSocket := true
	err = d.WithLock(context.Background(), func(context.Context) error {
		dropSocket()
		sawSocket = SocketPresent(dir)
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if sawSocket {
		t.Error("the sync process was still holding the store while the work ran")
	}
	if spawns < 2 {
		t.Errorf("the sync process was spawned %d times; it must be restarted afterwards", spawns)
	}
}

func TestWithLockRestartsEvenWhenTheWorkFails(t *testing.T) {
	dir := t.TempDir()
	spawns := 0
	spawn := func(string, ...string) *exec.Cmd {
		spawns++
		go func() {
			time.Sleep(30 * time.Millisecond)
			net.Listen("unix", filepath.Join(dir, SendSocket))
		}()
		return exec.Command("sleep", "30")
	}
	cfg := syncCfg()
	cfg.SendSocketWait = config.Duration(300 * time.Millisecond)

	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: filepath.Join(dir, "daemon.json"), Cfg: cfg,
		Port: 1, Secret: "s", spawn: spawn,
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()
	t.Cleanup(func() { os.Remove(filepath.Join(dir, SendSocket)) })

	boom := errors.New("boom")
	err = d.WithLock(context.Background(), func(context.Context) error { return boom })
	if !errors.Is(err, boom) {
		t.Errorf("err = %v, want the work's own error", err)
	}
	if spawns < 2 {
		t.Error("a failed command left the client without a sync process")
	}
}

func TestLockHolderReadsThePidfile(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "LOCK"),
		[]byte("pid="+strconv.Itoa(os.Getpid())+"\nacquired_at=now\n"), 0o600)

	pid, held := lockHolder(dir)
	if !held || pid != os.Getpid() {
		t.Errorf("lockHolder = (%d, %v)", pid, held)
	}

	os.WriteFile(filepath.Join(dir, "LOCK"), []byte("pid=4294967\n"), 0o600)
	if _, held := lockHolder(dir); held {
		t.Error("a pidfile naming a dead process must not count as held")
	}
}

func TestStateDistinguishesAnOrphanFromALiveClient(t *testing.T) {
	// The sync process and the wa that started it are recorded separately, so
	// an orphan left by a closed terminal can be taken over while a sync
	// belonging to another open client is left alone.
	live := State{PID: os.Getpid(), OwnerPID: os.Getpid()}
	if live.Orphaned() {
		t.Error("a sync whose client is running is not an orphan")
	}
	orphan := State{PID: os.Getpid(), OwnerPID: 4294967}
	if !orphan.Orphaned() {
		t.Error("a sync whose client is gone is an orphan")
	}
	old := State{PID: os.Getpid()} // written before owners were recorded
	if !old.Orphaned() {
		t.Error("a state file with no owner should read as orphaned rather than blocking forever")
	}
}

func TestWithLockRefusesToFightAnotherRunningClient(t *testing.T) {
	dir := t.TempDir()
	listen(t, dir)
	statePath := filepath.Join(dir, "daemon.json")

	// Another wa, still open, owning the sync.
	WriteState(statePath, State{
		PID: os.Getpid(), OwnerPID: os.Getppid(), Port: 1, Secret: "s", Owned: true,
	})

	d, err := Start(context.Background(), Options{
		StoreDir: dir, StatePath: statePath, Cfg: syncCfg(),
		spawn: func(string, ...string) *exec.Cmd { t.Fatal("must not spawn"); return nil },
	})
	if err != nil {
		t.Fatal(err)
	}
	defer d.Stop()

	ran := false
	err = d.WithLock(context.Background(), func(context.Context) error { ran = true; return nil })
	if err == nil {
		t.Fatal("stopping another client's sync must be refused")
	}
	if !strings.Contains(err.Error(), "another wa") {
		t.Errorf("err = %v, want it to name the other client", err)
	}
	if ran {
		t.Error("the work ran anyway, without the lock")
	}
}

func TestWaitSendReadyReturnsAtOnceWhenReady(t *testing.T) {
	dir := t.TempDir()
	d := &Daemon{opts: Options{StoreDir: dir}, mode: ModeNone}

	// No sync at all: a send takes the lock itself, so it is ready.
	start := time.Now()
	if err := d.WaitSendReady(context.Background(), time.Second); err != nil {
		t.Fatal(err)
	}
	if elapsed := time.Since(start); elapsed > 200*time.Millisecond {
		t.Errorf("waited %s for something already ready", elapsed)
	}
}

func TestWaitSendReadyWaitsForTheSocket(t *testing.T) {
	// A lock handover takes the delegation socket away for a few seconds.
	// A message typed during one has to wait for it, not be thrown away.
	dir := t.TempDir()
	d := &Daemon{opts: Options{StoreDir: dir}, mode: ModeSpawned}

	go func() {
		time.Sleep(300 * time.Millisecond)
		l, err := net.Listen("unix", filepath.Join(dir, SendSocket))
		if err == nil {
			t.Cleanup(func() { l.Close() })
		}
	}()

	start := time.Now()
	if err := d.WaitSendReady(context.Background(), 5*time.Second); err != nil {
		t.Fatal(err)
	}
	if elapsed := time.Since(start); elapsed < 200*time.Millisecond {
		t.Errorf("returned after %s without waiting for the socket", elapsed)
	}
}

func TestWaitSendReadyGivesUp(t *testing.T) {
	dir := t.TempDir()
	d := &Daemon{opts: Options{StoreDir: dir}, mode: ModeSpawned}

	err := d.WaitSendReady(context.Background(), 300*time.Millisecond)
	if err == nil {
		t.Fatal("expected a timeout")
	}
	if !strings.Contains(err.Error(), "not accepting sends") {
		t.Errorf("error = %v", err)
	}
}

func TestNilDaemonSendsWithoutWaiting(t *testing.T) {
	var d *Daemon
	if err := d.WaitSendReady(context.Background(), time.Second); err != nil {
		t.Error(err)
	}
}
