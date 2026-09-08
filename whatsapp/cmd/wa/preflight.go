package main

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// minWacli is the oldest wacli wa is known to work against. 0.18 is the
// version whose delegation socket and JSON envelope this was built on.
const minWacliMajor, minWacliMinor = 0, 18

// Environment is what preflight inspects. It is an interface so the checks can
// be tested without a wacli binary or a store.
type Environment interface {
	// WacliVersion returns the version string, or an error if wacli cannot be
	// run at all.
	WacliVersion() (string, error)
	// Authenticated reports whether a WhatsApp session is linked.
	Authenticated() (bool, error)
	// StoreReadable reports whether the database can be opened.
	StoreReadable() error
}

// ErrPreflight wraps every startup refusal.
var ErrPreflight = errors.New("wa cannot start")

// Preflight checks the things that would otherwise fail as an empty screen.
//
// Each failure explains what to do about it. Opening an interface that cannot
// possibly work and letting the user discover why is the outcome this exists
// to prevent.
func Preflight(env Environment) error {
	version, err := env.WacliVersion()
	if err != nil {
		return fmt.Errorf("%w: wacli is not available: %v\n\n"+
			"wa is a front end for wacli. Install it from https://wacli.sh and try again.",
			ErrPreflight, err)
	}
	if ok, err := atLeast(version, minWacliMajor, minWacliMinor); err == nil && !ok {
		return fmt.Errorf("%w: wacli %s is too old; wa needs at least %d.%d",
			ErrPreflight, version, minWacliMajor, minWacliMinor)
	}

	authed, err := env.Authenticated()
	if err != nil {
		return fmt.Errorf("%w: cannot ask wacli about the session: %v", ErrPreflight, err)
	}
	if !authed {
		return fmt.Errorf("%w: no WhatsApp session is linked.\n\n"+
			"Run `wacli auth` and scan the QR code, then start wa again.", ErrPreflight)
	}

	if err := env.StoreReadable(); err != nil {
		return fmt.Errorf("%w: the wacli store cannot be read: %v", ErrPreflight, err)
	}
	return nil
}

// atLeast compares a dotted version against a floor. An unparseable version is
// not an error: a fork or a development build should not be refused over its
// version string.
func atLeast(version string, major, minor int) (bool, error) {
	parts := strings.SplitN(strings.TrimPrefix(version, "v"), ".", 3)
	if len(parts) < 2 {
		return true, fmt.Errorf("cannot parse %q", version)
	}
	gotMajor, err := strconv.Atoi(parts[0])
	if err != nil {
		return true, err
	}
	gotMinor, err := strconv.Atoi(strings.SplitN(parts[1], "-", 2)[0])
	if err != nil {
		return true, err
	}
	if gotMajor != major {
		return gotMajor > major, nil
	}
	return gotMinor >= minor, nil
}

// fileReadable is the store check: opening the file is the same thing the
// reader will do a moment later.
func fileReadable(path string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	return f.Close()
}
