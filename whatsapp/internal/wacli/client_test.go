package wacli

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// fake builds the stand-in wacli, points the client at it, and returns the
// client plus the path of the invocation log. Nothing here touches the real
// wacli, the real store, or the network.
func fake(t *testing.T, script string) (*Client, string) {
	t.Helper()
	dir := t.TempDir()
	bin := filepath.Join(dir, "wacli")

	cmd := exec.Command("go", "build", "-o", bin, "./testdata/fakewacli")
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

	c := New(config.Wacli{Bin: bin, Timeout: config.Duration(10 * time.Second)})
	return c, logPath
}

func calls(t *testing.T, logPath string) string {
	t.Helper()
	body, err := os.ReadFile(logPath)
	if err != nil {
		return ""
	}
	return string(body)
}

func jid(t *testing.T, s string) domain.JID {
	t.Helper()
	j, err := domain.ParseJID(s)
	if err != nil {
		t.Fatal(err)
	}
	return j
}

const doctorOK = `{"doctor --json": {"stdout": "{\"success\":true,\"data\":{\"store_dir\":\"/s\",\"lock_held\":true,\"authenticated\":true,\"linked_jid\":\"995568669331@s.whatsapp.net\",\"fts_enabled\":true,\"store\":{\"messages\":12,\"chats\":3,\"contacts\":9,\"groups\":2}},\"error\":null}", "exit": 0}}`

func TestDoctorDecodesTheEnvelope(t *testing.T) {
	c, _ := fake(t, doctorOK)
	d, err := c.Doctor(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !d.LockHeld || !d.Authenticated || !d.FTSEnabled {
		t.Errorf("flags wrong: %+v", d)
	}
	if d.Messages != 12 || d.Chats != 3 || d.Contacts != 9 || d.Groups != 2 {
		t.Errorf("counts wrong: %+v", d)
	}
	if d.LinkedJID.User != "995568669331" {
		t.Errorf("linked JID = %v", d.LinkedJID)
	}
}

func TestGlobalFlagsAreInjected(t *testing.T) {
	c, logPath := fake(t, `{"*": {"stdout": "{\"success\":true,\"data\":{},\"error\":null}", "exit": 0}}`)
	c.cfg.Account = "work"
	c.cfg.Store = "/tmp/store"
	if _, err := c.Raw(context.Background(), "chats", "list"); err != nil {
		t.Fatal(err)
	}
	got := calls(t, logPath)
	for _, want := range []string{"--json", "--account work", "--store /tmp/store"} {
		if !strings.Contains(got, want) {
			t.Errorf("call is missing %q: %s", want, got)
		}
	}
}

func TestSendNeverPassesLockWait(t *testing.T) {
	// docs/delegation-probe.md: --lock-wait adds its full duration to every
	// send and changes nothing else. It must never appear.
	c, logPath := fake(t, `{"*": {"stdout": "{\"success\":true,\"data\":{\"id\":\"3EB0\",\"sent\":true},\"error\":null}", "exit": 0}}`)
	_, err := c.SendText(context.Background(), SendTextRequest{
		To: jid(t, "995568669331@s.whatsapp.net"), Message: "hi",
	})
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(calls(t, logPath), "--lock-wait") {
		t.Errorf("a send passed --lock-wait:\n%s", calls(t, logPath))
	}
}

func TestSendTextPassesTheRightFlags(t *testing.T) {
	c, logPath := fake(t, `{"*": {"stdout": "{\"success\":true,\"data\":{\"id\":\"3EB0ABC\",\"to\":\"48735396614220@lid\",\"sent\":true},\"error\":null}", "exit": 0}}`)
	got, err := c.SendText(context.Background(), SendTextRequest{
		To:            jid(t, "995568669331@s.whatsapp.net"),
		Message:       "hi there",
		ReplyTo:       "3EB0PREV",
		ReplyToSender: jid(t, "995568669331@s.whatsapp.net"),
		NoPreview:     true,
	})
	if err != nil {
		t.Fatal(err)
	}
	if got.ID != "3EB0ABC" || !got.Sent || got.To != "48735396614220@lid" {
		t.Errorf("SentMessage = %+v", got)
	}
	log := calls(t, logPath)
	for _, want := range []string{
		"send text",
		"--to 995568669331@s.whatsapp.net",
		"--message hi there",
		"--reply-to 3EB0PREV",
		"--reply-to-sender 995568669331@s.whatsapp.net",
		"--no-preview",
	} {
		if !strings.Contains(log, want) {
			t.Errorf("call is missing %q:\n%s", want, log)
		}
	}
}

func TestSendRejectsEmptyInputWithoutSpawning(t *testing.T) {
	c, logPath := fake(t, `{"*": {"exit": 0}}`)
	if _, err := c.SendText(context.Background(), SendTextRequest{Message: "hi"}); err == nil {
		t.Error("a send with no recipient must fail")
	}
	if _, err := c.SendText(context.Background(), SendTextRequest{To: jid(t, "1@s.whatsapp.net")}); err == nil {
		t.Error("a send with no text must fail")
	}
	if calls(t, logPath) != "" {
		t.Errorf("nothing should have been spawned:\n%s", calls(t, logPath))
	}
}

func TestLockedStoreBecomesATypedError(t *testing.T) {
	c, _ := fake(t, `{"*": {"stderr": "error: store is locked (another wacli is running?) pid=4242", "exit": 1}}`)
	_, err := c.Doctor(context.Background())
	if !errors.Is(err, ErrStoreLocked) {
		t.Fatalf("err = %v, want ErrStoreLocked", err)
	}
}

func TestLockedStoreReportedInTheEnvelope(t *testing.T) {
	// The real wacli reports this in the JSON body, not only on stderr.
	c, _ := fake(t, `{"*": {"stdout": "{\"success\":false,\"data\":null,\"error\":\"store is locked (another wacli is running?): resource temporarily unavailable\"}", "exit": 1}}`)
	_, err := c.SendText(context.Background(), SendTextRequest{
		To: jid(t, "1@s.whatsapp.net"), Message: "x",
	})
	if !errors.Is(err, ErrStoreLocked) {
		t.Fatalf("err = %v, want ErrStoreLocked", err)
	}
}

func TestUnauthenticatedBecomesATypedError(t *testing.T) {
	c, _ := fake(t, `{"*": {"stdout": "{\"success\":false,\"data\":null,\"error\":\"not authenticated: run wacli auth\"}", "exit": 1}}`)
	if _, err := c.Doctor(context.Background()); !errors.Is(err, ErrUnauthenticated) {
		t.Fatalf("err = %v, want ErrUnauthenticated", err)
	}
}

func TestAmbiguousRecipientCarriesCandidates(t *testing.T) {
	c, _ := fake(t, `{"*": {"stdout": "{\"success\":false,\"data\":null,\"error\":\"ambiguous recipient \\\"nika\\\": 2 matches: Nika A, Nika B\"}", "exit": 1}}`)
	_, err := c.SendText(context.Background(), SendTextRequest{
		To: jid(t, "1@s.whatsapp.net"), Message: "x",
	})
	var amb *AmbiguousError
	if !errors.As(err, &amb) {
		t.Fatalf("err = %v, want *AmbiguousError", err)
	}
	if amb.Query != "nika" || len(amb.Candidates) != 2 {
		t.Errorf("AmbiguousError = %+v", amb)
	}
}

func TestMissingBinaryIsReportedClearly(t *testing.T) {
	c := New(config.Wacli{Bin: "/nonexistent/wacli", Timeout: config.Duration(time.Second)})
	_, err := c.Doctor(context.Background())
	if !errors.Is(err, ErrNotInstalled) {
		t.Fatalf("err = %v, want ErrNotInstalled", err)
	}
}

func TestTimeoutIsReportedAsSuch(t *testing.T) {
	c, _ := fake(t, `{"*": {"stdout": "{\"success\":true,\"data\":{},\"error\":null}", "exit": 0, "delay_ms": 800}}`)
	c.cfg.Timeout = config.Duration(100 * time.Millisecond)
	_, err := c.Doctor(context.Background())
	if !errors.Is(err, ErrTimeout) {
		t.Fatalf("err = %v, want ErrTimeout", err)
	}
}

func TestUnrecognisedFailureKeepsWacliMessage(t *testing.T) {
	c, _ := fake(t, `{"*": {"stdout": "{\"success\":false,\"data\":null,\"error\":\"the moon is in the wrong phase\"}", "exit": 3}}`)
	_, err := c.Doctor(context.Background())
	var we *Error
	if !errors.As(err, &we) {
		t.Fatalf("err = %v, want *Error", err)
	}
	if !strings.Contains(we.Message, "moon") {
		t.Errorf("wacli's own message was lost: %q", we.Message)
	}
}

func TestSendsAreSerialised(t *testing.T) {
	// Two wacli send processes racing would interleave on the delegation
	// socket. The fake logs a start and an end line per call; if sends are
	// serialised the log alternates strictly.
	c, logPath := fake(t, `{"*": {"stdout": "{\"success\":true,\"data\":{\"id\":\"x\",\"sent\":true},\"error\":null}", "exit": 0, "delay_ms": 60}}`)
	to := jid(t, "995568669331@s.whatsapp.net")

	done := make(chan error, 3)
	for i := 0; i < 3; i++ {
		go func() {
			_, err := c.SendText(context.Background(), SendTextRequest{To: to, Message: "x"})
			done <- err
		}()
	}
	for i := 0; i < 3; i++ {
		if err := <-done; err != nil {
			t.Fatal(err)
		}
	}

	lines := strings.Split(strings.TrimSpace(calls(t, logPath)), "\n")
	if len(lines) != 6 {
		t.Fatalf("expected 3 start/end pairs, got %d lines:\n%s", len(lines), strings.Join(lines, "\n"))
	}
	for i := 0; i < len(lines); i += 2 {
		if !strings.HasPrefix(lines[i], "start") || !strings.HasPrefix(lines[i+1], "end") {
			t.Fatalf("sends interleaved:\n%s", strings.Join(lines, "\n"))
		}
	}
}

func TestChatActionsUseTheRightVerbs(t *testing.T) {
	c, logPath := fake(t, `{"*": {"stdout": "{\"success\":true,\"data\":{},\"error\":null}", "exit": 0}}`)
	j := jid(t, "120363001234567890@g.us")
	ctx := context.Background()

	cases := []struct {
		run  func() error
		want string
	}{
		{func() error { return c.Archive(ctx, j, true) }, "chats archive"},
		{func() error { return c.Archive(ctx, j, false) }, "chats unarchive"},
		{func() error { return c.Pin(ctx, j, true) }, "chats pin"},
		{func() error { return c.Pin(ctx, j, false) }, "chats unpin"},
		{func() error { return c.Mute(ctx, j, true) }, "chats mute"},
		{func() error { return c.Mute(ctx, j, false) }, "chats unmute"},
		{func() error { return c.MarkRead(ctx, j) }, "chats mark-read"},
		{func() error { return c.MarkUnread(ctx, j) }, "chats mark-unread"},
		{func() error { return c.Typing(ctx, j, true) }, "presence typing"},
		{func() error { return c.Typing(ctx, j, false) }, "presence paused"},
	}
	for _, tc := range cases {
		if err := tc.run(); err != nil {
			t.Fatalf("%s: %v", tc.want, err)
		}
		if !strings.Contains(calls(t, logPath), tc.want) {
			t.Errorf("no call matching %q", tc.want)
		}
	}
}
