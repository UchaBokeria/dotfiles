package wacli

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
)

const okSend = `{"*": {"stdout": "{\"success\":true,\"data\":{\"id\":\"3EB0ABC\",\"to\":\"x\",\"sent\":true},\"error\":null}", "exit": 0}}`

func TestSendPassesPostSendWait(t *testing.T) {
	// wacli holds the connection open for two seconds after a send so it can
	// answer a retry receipt itself. The sync process answers those, and two
	// seconds on every message, reaction and forward is most of what made
	// them feel slow.
	c, logPath := fake(t, okSend)

	if _, err := c.SendText(context.Background(), SendTextRequest{
		To: jid(t, "995000000000@s.whatsapp.net"), Message: "hello",
	}); err != nil {
		t.Fatal(err)
	}
	if got := calls(t, logPath); !strings.Contains(got, "--post-send-wait 0s") {
		t.Errorf("args = %q", got)
	}
}

func TestPostSendWaitIsConfigurable(t *testing.T) {
	// Somebody sending without a sync running does want wacli to stay for the
	// receipt, so the wait is a setting rather than a decision.
	c, logPath := fake(t, okSend)
	c.cfg.PostSendWait = config.Duration(3 * time.Second)

	if _, err := c.SendText(context.Background(), SendTextRequest{
		To: jid(t, "995000000000@s.whatsapp.net"), Message: "hello",
	}); err != nil {
		t.Fatal(err)
	}
	if got := calls(t, logPath); !strings.Contains(got, "--post-send-wait 3s") {
		t.Errorf("args = %q", got)
	}
}
