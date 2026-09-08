package daemon

import (
	"context"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/config"
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

	var l net.Listener
	r := &recorder{onSpawn: func() {
		time.Sleep(80 * time.Millisecond)
		l, _ = net.Listen("unix", filepath.Join(dir, SendSocket))
	}}
	t.Cleanup(func() {
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
