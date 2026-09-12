package store

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/wacli"
)

// fakeClient builds the same stand-in wacli the wacli package's tests use and
// returns a client pointed at it, plus the invocation log path.
func fakeClient(t *testing.T, script string) (*wacli.Client, string) {
	t.Helper()
	dir := t.TempDir()
	bin := filepath.Join(dir, "wacli")

	cmd := exec.Command("go", "build", "-o", bin, "../wacli/testdata/fakewacli")
	cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("building the fake wacli: %v\n%s", err, out)
	}

	scriptPath := filepath.Join(dir, "script.json")
	if err := os.WriteFile(scriptPath, []byte(script), 0o644); err != nil {
		t.Fatal(err)
	}
	logPath := filepath.Join(dir, "calls.log")
	t.Setenv("WA_FAKE_SCRIPT", scriptPath)
	t.Setenv("WA_FAKE_LOG", logPath)

	return wacli.New(config.Wacli{Bin: bin, Timeout: config.Duration(10 * time.Second)}), logPath
}

func TestOpenPrefersSQLiteOnAKnownSchema(t *testing.T) {
	r, deg, err := Open(fixturePath(t, KnownMigration), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	if deg.Used {
		t.Errorf("a known schema must not degrade: %s", deg.Reason)
	}
	if _, ok := r.(*sqliteReader); !ok {
		t.Errorf("reader is %T, want *sqliteReader", r)
	}
}

func TestOpenFallsBackOnANewerSchema(t *testing.T) {
	c, _ := fakeClient(t, `{"*": {"stdout": "{\"success\":true,\"data\":[{\"jid\":\"a@s.whatsapp.net\",\"kind\":\"dm\",\"name\":\"Ana\"}],\"error\":null}", "exit": 0}}`)
	r, deg, err := Open(fixturePath(t, KnownMigration+5), c)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	if !deg.Used || deg.Reason == "" {
		t.Fatal("a newer schema must degrade, with a stated reason")
	}
	if !strings.Contains(deg.Reason, "newer") {
		t.Errorf("reason = %q, want it to explain the version mismatch", deg.Reason)
	}
	if _, ok := r.(*cliReader); !ok {
		t.Fatalf("reader is %T, want *cliReader", r)
	}

	got, err := r.Chats(context.Background(), ChatFilter{Limit: 50})
	if err != nil || len(got) != 1 || got[0].Name != "Ana" {
		t.Fatalf("Chats through the CLI = %v, %v", names(got), err)
	}
}

func TestOpenWithoutAFallbackClientReportsTheProblem(t *testing.T) {
	_, _, err := Open(fixturePath(t, KnownMigration+5), nil)
	if err == nil {
		t.Fatal("with no client to fall back to, an unreadable schema must be an error")
	}
}

func TestOpenOnAMissingFileFallsBack(t *testing.T) {
	c, _ := fakeClient(t, `{"*": {"stdout": "{\"success\":true,\"data\":[],\"error\":null}", "exit": 0}}`)
	r, deg, err := Open(filepath.Join(t.TempDir(), "absent.db"), c)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	if !deg.Used {
		t.Error("a missing database must degrade rather than pretend to work")
	}
}

func TestCLIReaderPassesFilterFlags(t *testing.T) {
	c, logPath := fakeClient(t, `{"*": {"stdout": "{\"success\":true,\"data\":[],\"error\":null}", "exit": 0}}`)
	r := OpenCLI(c)

	if _, err := r.Chats(context.Background(), ChatFilter{Unread: true, Pinned: true, Limit: 25}); err != nil {
		t.Fatal(err)
	}
	log, _ := os.ReadFile(logPath)
	for _, want := range []string{"chats list", "--limit 25", "--unread", "--pinned", "--no-archived"} {
		if !strings.Contains(string(log), want) {
			t.Errorf("call is missing %q:\n%s", want, log)
		}
	}
}

func TestCLIReaderFiltersGroupsLocally(t *testing.T) {
	// wacli has no group filter, so the reader narrows the result itself.
	c, _ := fakeClient(t, `{"*": {"stdout": "{\"success\":true,\"data\":[{\"jid\":\"a@s.whatsapp.net\",\"kind\":\"dm\",\"name\":\"Ana\"},{\"jid\":\"1@g.us\",\"kind\":\"group\",\"name\":\"Team\"}],\"error\":null}", "exit": 0}}`)
	r := OpenCLI(c)

	got, err := r.Chats(context.Background(), ChatFilter{Groups: true})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Name != "Team" {
		t.Errorf("got %v, want just Team", names(got))
	}
}

func TestCLIReaderParsesMessages(t *testing.T) {
	// The real shape: Go field names, nested under data.messages beside an
	// "fts" flag. An invented snake_case shape here is what hid a reader that
	// decoded nothing.
	c, _ := fakeClient(t, `{"*": {"stdout": "{\"success\":true,\"data\":{\"fts\":true,\"messages\":[{\"MsgID\":\"M1\",\"ChatJID\":\"a@s.whatsapp.net\",\"Timestamp\":\"2026-09-08T12:33:50Z\",\"FromMe\":true,\"Text\":\"hello\",\"MediaType\":\"image\",\"Filename\":\"a.png\",\"LocalPath\":\"/tmp/a.png\",\"DownloadedAt\":\"2026-09-08T12:34:00Z\"}]},\"error\":null}", "exit": 0}}`)
	r := OpenCLI(c)

	got, err := r.Messages(context.Background(), MessageFilter{Chat: mustJID(t, "a@s.whatsapp.net")})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 {
		t.Fatalf("got %d messages", len(got))
	}
	m := got[0]
	if m.ID != "M1" || !m.FromMe || m.Text != "hello" {
		t.Errorf("message = %+v", m)
	}
	if m.TS.IsZero() {
		t.Error("the RFC3339 timestamp was not parsed")
	}
	if m.Media == nil || !m.Media.Downloaded() {
		t.Errorf("media = %+v", m.Media)
	}
}

func TestCLIReaderSearchPassesTheQuery(t *testing.T) {
	c, logPath := fakeClient(t, `{"*": {"stdout": "{\"success\":true,\"data\":{\"fts\":true,\"messages\":[]},\"error\":null}", "exit": 0}}`)
	r := OpenCLI(c)
	if _, err := r.Search(context.Background(), Query{Text: "nuc", HasMedia: true}); err != nil {
		t.Fatal(err)
	}
	log, _ := os.ReadFile(logPath)
	for _, want := range []string{"messages search nuc", "--has-media"} {
		if !strings.Contains(string(log), want) {
			t.Errorf("call is missing %q:\n%s", want, log)
		}
	}
}

func TestCLIReaderEmptySearchDoesNotSpawn(t *testing.T) {
	c, logPath := fakeClient(t, `{"*": {"stdout": "{\"success\":true,\"data\":[],\"error\":null}", "exit": 0}}`)
	r := OpenCLI(c)
	if _, err := r.Search(context.Background(), Query{Text: "  "}); err != nil {
		t.Fatal(err)
	}
	if body, _ := os.ReadFile(logPath); len(body) != 0 {
		t.Errorf("an empty search spawned wacli:\n%s", body)
	}
}

func TestBothReadersSatisfyTheSameInterface(t *testing.T) {
	// The point of the fallback is that the interface cannot tell them apart.
	var _ Reader = (*sqliteReader)(nil)
	var _ Reader = (*cliReader)(nil)
}

func TestCLIReaderDropsAJIDUsedAsAName(t *testing.T) {
	// Same trap as the direct reader: wacli returns the JID as the name when
	// it knows nothing better.
	c, _ := fakeClient(t, `{"*": {"stdout": "{\"success\":true,\"data\":[{\"jid\":\"120363406498717807@g.us\",\"kind\":\"group\",\"name\":\"120363406498717807@g.us\"}],\"error\":null}", "exit": 0}}`)
	r := OpenCLI(c)

	got, err := r.Chats(context.Background(), ChatFilter{})
	if err != nil {
		t.Fatal(err)
	}
	if got[0].Name != "" {
		t.Errorf("name = %q, want empty so the caller formats the identifier", got[0].Name)
	}
}
