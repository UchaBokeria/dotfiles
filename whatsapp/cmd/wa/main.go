// Command wa is a terminal WhatsApp client built on the wacli command line.
//
//	wa                  open the client
//	wa lock set         set the password that gates the interface
//	wa lock clear       remove it
//	wa doctor           report what wa can see
//	wa version          print the version
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"golang.org/x/term"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/config"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/daemon"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/live"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/lock"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/store"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/theme"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/ui"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/wacli"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/xdgpath"
)

// version is overwritten at build time with -ldflags "-X main.version=...".
var version = "dev"

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(args []string) error {
	if len(args) > 0 {
		switch args[0] {
		case "version", "--version", "-v":
			fmt.Println("wa", version)
			return nil
		case "help", "--help", "-h":
			fmt.Print(usage)
			return nil
		case "lock":
			return runLock(args[1:])
		case "doctor":
			return runDoctor()
		default:
			return fmt.Errorf("unknown command %q\n\n%s", args[0], usage)
		}
	}
	return runTUI()
}

const usage = `wa - a terminal WhatsApp client

  wa                open the client
  wa lock set       set the password that gates the interface
  wa lock clear     remove the password
  wa doctor         report what wa can see
  wa version        print the version

Configuration lives in ` + "`$XDG_CONFIG_HOME/wa/config.toml`" + `.
Press <Space>? inside wa for the keys.
`

// setup loads everything the client needs, shared by the TUI and by doctor.
type setup struct {
	cfg       config.Config
	warns     []config.Warning
	client    *wacli.Client
	reader    store.Reader
	degraded  store.Degradation
	storeDir  string
	styles    theme.Styles
	logBuffer *ui.Log
}

func loadSetup() (*setup, error) {
	if err := xdgpath.EnsureDirs(); err != nil {
		return nil, err
	}
	cfg, warns, err := config.Load(xdgpath.Config(), xdgpath.Overrides())
	if err != nil {
		return nil, err
	}

	palette, err := theme.Load(cfg.Theme.File)
	if err != nil {
		return nil, err
	}

	client := wacli.New(cfg.Wacli)

	storeDir := cfg.Wacli.Store
	if storeDir == "" {
		storeDir = xdgpath.WacliStore()
	}

	logBuffer := ui.NewLog()
	reader, degraded, err := store.Open(filepath.Join(storeDir, "wacli.db"), client)
	if err != nil {
		return nil, err
	}

	return &setup{
		cfg:       cfg,
		warns:     warns,
		client:    client,
		reader:    reader,
		degraded:  degraded,
		storeDir:  storeDir,
		styles:    theme.New(palette, cfg.UI.Border),
		logBuffer: logBuffer,
	}, nil
}

// cliEnvironment adapts the real wacli and store to the preflight checks.
type cliEnvironment struct {
	client   *wacli.Client
	storeDir string
}

func (e cliEnvironment) WacliVersion() (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	return e.client.Version(ctx)
}

func (e cliEnvironment) Authenticated() (bool, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	d, err := e.client.Doctor(ctx)
	if err != nil {
		if errors.Is(err, wacli.ErrUnauthenticated) {
			return false, nil
		}
		return false, err
	}
	return d.Authenticated, nil
}

func (e cliEnvironment) StoreReadable() error {
	return fileReadable(filepath.Join(e.storeDir, "wacli.db"))
}

func runTUI() error {
	s, err := loadSetup()
	if err != nil {
		return err
	}
	defer s.reader.Close()

	// Preflight runs before the alternate screen is entered, so a failure is
	// readable in the scrollback rather than wiped by the terminal restoring.
	if err := Preflight(cliEnvironment{client: s.client, storeDir: s.storeDir}); err != nil {
		return err
	}

	secret, err := randomSecret()
	if err != nil {
		return err
	}

	// The webhook listener is started first so its kernel-assigned port can be
	// handed to the sync process it is about to spawn.
	webhook, err := live.NewWebhook(secret, 128)
	if err != nil {
		return err
	}
	defer webhook.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	d, err := daemon.Start(ctx, daemon.Options{
		StoreDir:  s.storeDir,
		StatePath: xdgpath.Daemon(),
		Cfg:       s.cfg.Sync,
		Port:      webhook.Port(),
		Secret:    secret,
		Bin:       s.cfg.Wacli.Bin,
	})
	if err != nil {
		return err
	}
	defer d.Stop()

	// A sync process wa did not start sends its webhooks somewhere else, so
	// the only way to see new messages is to look for them.
	var source live.Source = webhook
	if d.Mode() == daemon.ModePolling || d.Mode() == daemon.ModeNone {
		webhook.Close()
		source = live.NewPoll(s.reader, s.cfg.Sync.PollInterval.D(), 64)
	}
	defer source.Close()

	app, err := ui.NewApp(ui.Deps{
		Cfg:           s.cfg,
		Styles:        s.styles,
		Store:         s.reader,
		Client:        s.client,
		Daemon:        d,
		Live:          source,
		LockPath:      xdgpath.Lock(),
		Log:           s.logBuffer,
		ConfigPath:    xdgpath.Config(),
		OverridesPath: xdgpath.Overrides(),
	})
	if err != nil {
		return err
	}

	for _, w := range s.warns {
		s.logBuffer.Warnf("config: %v", w)
	}
	if s.degraded.Used {
		app.Announce("store", s.degraded.Reason)
	}

	// Hot reload: a config change rebuilds the keymap and the styles in place.
	watcher, err := config.Watch(xdgpath.Config(), func(config.Config, []config.Warning, error) {})
	if err == nil {
		defer watcher.Close()
	}

	p := tea.NewProgram(app, tea.WithAltScreen(), tea.WithMouseCellMotion())

	// Ctrl-C and SIGTERM reach the program rather than killing the process, so
	// the sync child is reaped instead of orphaned.
	stop := make(chan os.Signal, 1)
	// SIGHUP matters as much as the other two: closing the terminal window is
	// the common way a session ends, and without it the sync child is orphaned
	// still holding the store lock.
	signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT, syscall.SIGHUP)
	go func() {
		<-stop
		p.Quit()
	}()

	_, err = p.Run()
	return err
}

func runLock(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: wa lock set|clear|status")
	}
	path := xdgpath.Lock()

	switch args[0] {
	case "status":
		if lock.Exists(path) {
			fmt.Println("a password is set")
		} else {
			fmt.Println("no password is set")
		}
		return nil

	case "clear":
		if err := lock.Clear(path); err != nil {
			return err
		}
		fmt.Println("password removed")
		return nil

	case "set":
		if err := xdgpath.EnsureDirs(); err != nil {
			return err
		}
		first, err := readPassword("password: ")
		if err != nil {
			return err
		}
		if strings.TrimSpace(first) == "" {
			return fmt.Errorf("refusing to set an empty password")
		}
		again, err := readPassword("again: ")
		if err != nil {
			return err
		}
		if first != again {
			return fmt.Errorf("the passwords do not match")
		}
		if err := lock.Set(path, first); err != nil {
			return err
		}
		fmt.Printf("password set in %s\n", path)
		fmt.Println("\nNote: this gates wa's interface only. It does not encrypt")
		fmt.Println("wacli's message store, which stays readable on disk.")
		fmt.Println("\nTurn it on with:  [lock] enabled = true  in", xdgpath.Config())
		return nil
	}
	return fmt.Errorf("usage: wa lock set|clear|status")
}

// readPassword reads without echoing.
func readPassword(prompt string) (string, error) {
	fmt.Print(prompt)
	defer fmt.Println()

	fd := int(os.Stdin.Fd())
	if !term.IsTerminal(fd) {
		return "", fmt.Errorf("a password can only be set from a terminal")
	}
	body, err := term.ReadPassword(fd)
	if err != nil {
		return "", err
	}
	return string(body), nil
}

func runDoctor() error {
	s, err := loadSetup()
	if err != nil {
		return err
	}
	defer s.reader.Close()

	fmt.Println("wa", version)
	fmt.Println("config      ", xdgpath.Config())
	fmt.Println("overrides   ", xdgpath.Overrides())
	fmt.Println("state       ", xdgpath.StateDir())
	fmt.Println("wacli store ", s.storeDir)

	if len(s.warns) > 0 {
		fmt.Println("\nconfiguration warnings:")
		for _, w := range s.warns {
			fmt.Println("  ", w)
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	if v, err := s.client.Version(ctx); err == nil {
		fmt.Println("\nwacli       ", v)
	} else {
		fmt.Println("\nwacli        NOT AVAILABLE:", err)
	}

	// doctor takes the store lock, so it is only safe here because nothing
	// else of ours is running yet.
	if d, err := s.client.Doctor(ctx); err == nil {
		fmt.Printf("account      %s\n", d.LinkedJID)
		fmt.Printf("authenticated %v\n", d.Authenticated)
		fmt.Printf("lock held    %v\n", d.LockHeld)
		fmt.Printf("store        %d messages, %d chats, %d contacts, %d groups\n",
			d.Messages, d.Chats, d.Contacts, d.Groups)
		fmt.Printf("full text    %v\n", d.FTSEnabled)
	} else {
		fmt.Println("doctor       ", err)
	}

	reader := "direct SQLite reads"
	if s.degraded.Used {
		reader = "the wacli CLI: " + s.degraded.Reason
	}
	fmt.Println("reader      ", reader)

	if daemon.SocketPresent(s.storeDir) {
		fmt.Println("sync         a follow-mode sync is running (sends will be delegated)")
	} else {
		fmt.Println("sync         not running")
	}

	if lock.Exists(xdgpath.Lock()) {
		fmt.Println("lock         a password is set")
	} else {
		fmt.Println("lock         no password is set")
	}
	return nil
}

// randomSecret is the webhook's HMAC key, fresh on every start.
func randomSecret() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}
