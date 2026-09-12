// Package wacli is the only package in wa that runs a subprocess.
//
// Every mutation of WhatsApp state goes through the wacli command line, which
// owns the store lock and, while a `sync --follow` process is running,
// delegates sends to it over a Unix socket. Funnelling every call through one
// package means lock handling, timeouts, JSON decoding and error translation
// exist once rather than at each call site.
package wacli

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/config"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

// Client runs wacli.
type Client struct {
	cfg config.Wacli

	// sendMu serialises sends. Two wacli send processes racing would interleave
	// on the delegation socket, and a burst of Enter presses must not reorder
	// the conversation.
	sendMu sync.Mutex
}

// New returns a client. An empty Bin means "wacli", found on PATH.
func New(cfg config.Wacli) *Client {
	if cfg.Bin == "" {
		cfg.Bin = "wacli"
	}
	if cfg.Timeout == 0 {
		cfg.Timeout = config.Duration(30 * time.Second)
	}
	return &Client{cfg: cfg}
}

// Bin is the configured wacli binary.
func (c *Client) Bin() string { return c.cfg.Bin }

// envelope is wacli's --json wrapper.
type envelope struct {
	Success bool            `json:"success"`
	Data    json.RawMessage `json:"data"`
	Error   string          `json:"error"`
}

// Args builds the full argument list for a call, injecting the global flags.
func (c *Client) Args(args ...string) []string {
	out := append([]string{}, args...)
	out = append(out, "--json")
	if c.cfg.Account != "" {
		out = append(out, "--account", c.cfg.Account)
	}
	if c.cfg.Store != "" {
		out = append(out, "--store", c.cfg.Store)
	}
	return out
}

// run executes wacli and returns the decoded `data` field.
//
// Note what is deliberately absent: --lock-wait. Measurements recorded in
// docs/delegation-probe.md show a send given --lock-wait spends the whole
// duration failing to take the lock and only then falls back to the delegation
// socket, so the flag is pure added latency on every call.
func (c *Client) run(ctx context.Context, args ...string) ([]byte, error) {
	full := c.Args(args...)

	ctx, cancel := context.WithTimeout(ctx, c.cfg.Timeout.D())
	defer cancel()

	cmd := exec.CommandContext(ctx, c.cfg.Bin, full...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	runErr := cmd.Run()

	if ctx.Err() == context.DeadlineExceeded {
		return nil, fmt.Errorf("%w: %s took longer than %s",
			ErrTimeout, strings.Join(full, " "), c.cfg.Timeout)
	}

	// wacli reports failures in the envelope as well as by exit status, and
	// the envelope carries the better message, so try to decode either way.
	var env envelope
	decodeErr := json.Unmarshal(bytes.TrimSpace(stdout.Bytes()), &env)

	if decodeErr == nil && !env.Success {
		return nil, classify(full, env.Error, stderr.String(), exitCode(runErr))
	}
	if runErr != nil {
		detail := env.Error
		if detail == "" {
			detail = stderr.String()
		}
		if detail == "" && decodeErr != nil {
			detail = strings.TrimSpace(stdout.String())
		}
		if detail == "" {
			// Nothing on stdout or stderr: the process never ran. exec's own
			// message is the only description of what went wrong.
			detail = runErr.Error()
		}
		return nil, classify(full, detail, stderr.String(), exitCode(runErr))
	}
	if decodeErr != nil {
		var missing *exec.Error
		if errors.As(runErr, &missing) {
			return nil, classify(full, missing.Error(), "", -1)
		}
		return nil, fmt.Errorf("%s: output is not JSON: %w", strings.Join(full, " "), decodeErr)
	}
	return env.Data, nil
}

func exitCode(err error) int {
	if err == nil {
		return 0
	}
	var ee *exec.ExitError
	if errors.As(err, &ee) {
		return ee.ExitCode()
	}
	return -1
}

// Raw runs an arbitrary wacli subcommand and returns its `data` field. It backs
// the : commands that wrap wacli directly.
func (c *Client) Raw(ctx context.Context, args ...string) ([]byte, error) {
	return c.run(ctx, args...)
}

// Doctor is wacli's own diagnosis of the store.
type Doctor struct {
	StoreDir      string
	LockHeld      bool
	Authenticated bool
	Connected     bool
	LinkedJID     domain.JID
	FTSEnabled    bool
	Messages      int
	Chats         int
	Contacts      int
	Groups        int
}

// Doctor asks wacli about the store.
//
// Do not call this while a sync process is starting: `doctor` takes the store
// lock itself, briefly, and a poll loop against it will starve the sync process
// out of ever acquiring the lock. That is not hypothetical - it is how the
// first delegation probe failed.
func (c *Client) Doctor(ctx context.Context) (Doctor, error) {
	body, err := c.run(ctx, "doctor")
	if err != nil {
		return Doctor{}, err
	}
	var raw struct {
		StoreDir      string `json:"store_dir"`
		LockHeld      bool   `json:"lock_held"`
		Authenticated bool   `json:"authenticated"`
		Connected     bool   `json:"connected"`
		LinkedJID     string `json:"linked_jid"`
		FTSEnabled    bool   `json:"fts_enabled"`
		Store         struct {
			Messages int `json:"messages"`
			Chats    int `json:"chats"`
			Contacts int `json:"contacts"`
			Groups   int `json:"groups"`
		} `json:"store"`
	}
	if err := json.Unmarshal(body, &raw); err != nil {
		return Doctor{}, fmt.Errorf("doctor: %w", err)
	}
	d := Doctor{
		StoreDir:      raw.StoreDir,
		LockHeld:      raw.LockHeld,
		Authenticated: raw.Authenticated,
		Connected:     raw.Connected,
		FTSEnabled:    raw.FTSEnabled,
		Messages:      raw.Store.Messages,
		Chats:         raw.Store.Chats,
		Contacts:      raw.Store.Contacts,
		Groups:        raw.Store.Groups,
	}
	if raw.LinkedJID != "" {
		d.LinkedJID, _ = domain.ParseJID(raw.LinkedJID)
	}
	return d, nil
}

// Version reports the wacli version string, for the preflight check. It does
// not use --json: `wacli version` predates the JSON envelope.
func (c *Client) Version(ctx context.Context) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, c.cfg.Timeout.D())
	defer cancel()
	out, err := exec.CommandContext(ctx, c.cfg.Bin, "--version").Output()
	if err != nil {
		return "", classify([]string{"--version"}, err.Error(), "", exitCode(err))
	}
	// "wacli 0.18.1"
	fields := strings.Fields(strings.TrimSpace(string(out)))
	if len(fields) == 0 {
		return "", fmt.Errorf("wacli --version printed nothing")
	}
	return fields[len(fields)-1], nil
}

// postSendWait is the argument that stops wacli sitting on the connection
// after a send.
//
// wacli waits two seconds by default so it can answer a retry receipt itself.
// That is the right default for a one-shot command line and the wrong one
// here: the sync process is already connected and answers those receipts, and
// two seconds on every message, reaction and forward is most of what made
// them feel slow.
func (c *Client) postSendWait() []string {
	return []string{"--post-send-wait", c.cfg.PostSendWait.D().String()}
}

// PostSendWaitArgs is the same, for the callers that build their own argument
// lists rather than going through a typed request.
func (c *Client) PostSendWaitArgs() []string { return c.postSendWait() }
