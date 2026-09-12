package wacli

import (
	"os/exec"
	"strings"
	"testing"
)

// The fake wacli answers anything, which is what makes it useful for testing
// decoding and error handling - and exactly what let a whole class of bug
// through unnoticed: every chats subcommand was called with the JID as a
// positional argument, where wacli wants --chat. The fake shrugged; the real
// binary answered "--chat is required" and pin, mute, archive and mark-read
// all silently did nothing.
//
// These tests check the argument shapes against the real wacli's own help
// output. They skip when wacli is not installed, so they cost nothing in a
// clean checkout and catch the drift wherever it is.

func realWacli(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("wacli"); err != nil {
		t.Skip("wacli is not installed")
	}
}

// helpFor returns the help text for a subcommand.
func helpFor(t *testing.T, args ...string) string {
	t.Helper()
	out, err := exec.Command("wacli", append(args, "--help")...).CombinedOutput()
	if err != nil {
		t.Fatalf("wacli %s --help: %v\n%s", strings.Join(args, " "), err, out)
	}
	return string(out)
}

// flags lists the long flags a subcommand accepts.
func flags(t *testing.T, args ...string) map[string]bool {
	t.Helper()
	out := map[string]bool{}
	for _, line := range strings.Split(helpFor(t, args...), "\n") {
		line = strings.TrimSpace(line)
		i := strings.Index(line, "--")
		if i < 0 {
			continue
		}
		name := line[i:]
		if end := strings.IndexAny(name, " \t"); end > 0 {
			name = name[:end]
		}
		out[name] = true
	}
	return out
}

// takesPositional reports whether the usage line shows a positional argument.
func takesPositional(t *testing.T, args ...string) bool {
	t.Helper()
	for _, line := range strings.Split(helpFor(t, args...), "\n") {
		line = strings.TrimSpace(line)
		if !strings.HasPrefix(line, "wacli "+strings.Join(args, " ")) {
			continue
		}
		rest := strings.TrimSpace(strings.TrimPrefix(line, "wacli "+strings.Join(args, " ")))
		// "[flags]" and "[command]" are not positional arguments.
		rest = strings.ReplaceAll(rest, "[flags]", "")
		rest = strings.ReplaceAll(rest, "[command]", "")
		if strings.TrimSpace(rest) != "" {
			return true
		}
	}
	return false
}

func TestChatCommandsTakeAChatFlag(t *testing.T) {
	realWacli(t)
	for _, verb := range []string{
		"pin", "unpin", "mute", "unmute", "archive", "unarchive",
		"mark-read", "mark-unread",
	} {
		t.Run(verb, func(t *testing.T) {
			got := flags(t, "chats", verb)
			if !got["--chat"] {
				t.Errorf("wacli chats %s has no --chat flag; the client passes one", verb)
			}
			if takesPositional(t, "chats", verb) {
				t.Errorf("wacli chats %s takes a positional argument; the client does not pass one", verb)
			}
		})
	}
}

func TestChatsShowTakesJID(t *testing.T) {
	realWacli(t)
	if !flags(t, "chats", "show")["--jid"] {
		t.Error("wacli chats show has no --jid flag; the store passes one")
	}
}

func TestMessageCommandsTakeChatAndID(t *testing.T) {
	realWacli(t)
	for _, verb := range []string{"show", "revoke", "delete", "forward"} {
		t.Run(verb, func(t *testing.T) {
			got := flags(t, "messages", verb)
			for _, want := range []string{"--chat", "--id"} {
				if !got[want] {
					t.Errorf("wacli messages %s has no %s flag", verb, want)
				}
			}
			if takesPositional(t, "messages", verb) {
				t.Errorf("wacli messages %s takes a positional argument", verb)
			}
		})
	}
}

func TestMediaDownloadFlags(t *testing.T) {
	realWacli(t)
	got := flags(t, "media", "download")
	for _, want := range []string{"--chat", "--id", "--output"} {
		if !got[want] {
			t.Errorf("wacli media download has no %s flag", want)
		}
	}
}

func TestSendReactFlags(t *testing.T) {
	realWacli(t)
	got := flags(t, "send", "react")
	for _, want := range []string{"--to", "--id", "--reaction", "--sender"} {
		if !got[want] {
			t.Errorf("wacli send react has no %s flag", want)
		}
	}
}

func TestSendTextFlags(t *testing.T) {
	realWacli(t)
	got := flags(t, "send", "text")
	for _, want := range []string{
		"--to", "--message", "--reply-to", "--reply-to-sender", "--no-preview", "--mention",
	} {
		if !got[want] {
			t.Errorf("wacli send text has no %s flag", want)
		}
	}
}

// A flag on one subcommand is not a flag on its siblings. `send text` refuses
// the linked account unless told otherwise and takes --allow-self for it;
// `send file` has no such objection and no such flag, and passing one wacli
// does not know is an error rather than something it ignores - which is how
// pasting a picture into your own chat failed with "unknown flag".
func TestAllowSelfIsOnlyOnSendText(t *testing.T) {
	realWacli(t)

	if !flags(t, "send", "text")["--allow-self"] {
		t.Error("wacli send text has no --allow-self; the client passes it")
	}
	if flags(t, "send", "file")["--allow-self"] {
		t.Error("wacli send file now takes --allow-self; the client should pass it")
	}
}

func TestPresenceTakesTo(t *testing.T) {
	realWacli(t)
	for _, verb := range []string{"typing", "paused"} {
		if !flags(t, "presence", verb)["--to"] {
			t.Errorf("wacli presence %s has no --to flag", verb)
		}
	}
}

func TestContactsShowTakesJID(t *testing.T) {
	realWacli(t)
	if !flags(t, "contacts", "show")["--jid"] {
		t.Error("wacli contacts show has no --jid flag")
	}
}

func TestChatsCleanupFlags(t *testing.T) {
	realWacli(t)
	got := flags(t, "chats", "cleanup")
	for _, want := range []string{"--jid", "--confirm"} {
		if !got[want] {
			t.Errorf("wacli chats cleanup has no %s flag", want)
		}
	}
}

func TestListingCommandsAcceptTheFiltersTheStoreUses(t *testing.T) {
	realWacli(t)
	chats := flags(t, "chats", "list")
	for _, want := range []string{"--limit", "--query", "--unread", "--pinned", "--muted", "--archived", "--no-archived"} {
		if !chats[want] {
			t.Errorf("wacli chats list has no %s flag", want)
		}
	}
	msgs := flags(t, "messages", "list")
	for _, want := range []string{"--chat", "--limit", "--before", "--after", "--asc"} {
		if !msgs[want] {
			t.Errorf("wacli messages list has no %s flag", want)
		}
	}
	search := flags(t, "messages", "search")
	for _, want := range []string{"--chat", "--limit", "--has-media", "--starred", "--after"} {
		if !search[want] {
			t.Errorf("wacli messages search has no %s flag", want)
		}
	}
}

func TestTheClientsOwnCallsMatchTheRealFlags(t *testing.T) {
	realWacli(t)

	// Each entry is a call the client makes, as (subcommand..., flags used).
	calls := []struct {
		cmd   []string
		flags []string
	}{
		{[]string{"chats", "pin"}, []string{"--chat"}},
		{[]string{"chats", "mark-read"}, []string{"--chat"}},
		{[]string{"chats", "cleanup"}, []string{"--jid", "--confirm"}},
		{[]string{"chats", "show"}, []string{"--jid"}},
		{[]string{"messages", "revoke"}, []string{"--chat", "--id"}},
		{[]string{"messages", "delete"}, []string{"--chat", "--id", "--for-me"}},
		{[]string{"messages", "forward"}, []string{"--chat", "--id", "--to"}},
		{[]string{"messages", "show"}, []string{"--chat", "--id"}},
		{[]string{"media", "download"}, []string{"--chat", "--id"}},
		{[]string{"send", "react"}, []string{"--to", "--id", "--reaction", "--sender"}},
		{[]string{"send", "text"}, []string{
			"--to", "--message", "--reply-to", "--allow-self", "--post-send-wait"}},
		{[]string{"send", "file"}, []string{
			"--to", "--file", "--caption", "--filename", "--reply-to", "--ptt",
			"--post-send-wait"}},
		{[]string{"messages", "forward"}, []string{"--post-send-wait"}},
		{[]string{"send", "react"}, []string{"--post-send-wait"}},
		{[]string{"presence", "typing"}, []string{"--to"}},
		{[]string{"contacts", "show"}, []string{"--jid"}},
	}
	for _, c := range calls {
		name := strings.Join(c.cmd, " ")
		t.Run(name, func(t *testing.T) {
			got := flags(t, c.cmd...)
			for _, f := range c.flags {
				if !got[f] {
					t.Errorf("the client passes %s to `wacli %s`, which does not accept it", f, name)
				}
			}
		})
	}
}
