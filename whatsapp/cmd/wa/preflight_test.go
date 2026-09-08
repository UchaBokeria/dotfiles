package main

import (
	"errors"
	"strings"
	"testing"
)

type fakeEnv struct {
	version  string
	versErr  error
	authed   bool
	authErr  error
	storeErr error
}

func (f fakeEnv) WacliVersion() (string, error) { return f.version, f.versErr }
func (f fakeEnv) Authenticated() (bool, error)  { return f.authed, f.authErr }
func (f fakeEnv) StoreReadable() error          { return f.storeErr }

func TestPreflightPassesOnAHealthySystem(t *testing.T) {
	if err := Preflight(fakeEnv{version: "0.18.1", authed: true}); err != nil {
		t.Fatalf("a healthy system was refused: %v", err)
	}
}

func TestPreflightReportsAMissingBinary(t *testing.T) {
	err := Preflight(fakeEnv{versErr: errors.New("executable file not found")})
	if err == nil {
		t.Fatal("a missing wacli must stop startup")
	}
	if !strings.Contains(err.Error(), "wacli.sh") {
		t.Errorf("err = %v, want it to say where to get wacli", err)
	}
}

func TestPreflightRejectsAnOldWacli(t *testing.T) {
	err := Preflight(fakeEnv{version: "0.17.9", authed: true})
	if err == nil {
		t.Fatal("an old wacli must be refused")
	}
	if !strings.Contains(err.Error(), "0.18") {
		t.Errorf("err = %v, want the version floor named", err)
	}
}

func TestPreflightAcceptsANewerWacli(t *testing.T) {
	for _, v := range []string{"0.19.0", "1.0.0", "0.18.0"} {
		if err := Preflight(fakeEnv{version: v, authed: true}); err != nil {
			t.Errorf("wacli %s was refused: %v", v, err)
		}
	}
}

func TestPreflightToleratesAnOddVersionString(t *testing.T) {
	// A development build should not be refused over its version string.
	for _, v := range []string{"dev", "v0.18.1-rc1", "unknown"} {
		if err := Preflight(fakeEnv{version: v, authed: true}); err != nil {
			t.Errorf("wacli %q was refused: %v", v, err)
		}
	}
}

func TestPreflightExplainsHowToAuthenticate(t *testing.T) {
	err := Preflight(fakeEnv{version: "0.18.1", authed: false})
	if err == nil {
		t.Fatal("an unauthenticated wacli must stop startup")
	}
	if !strings.Contains(err.Error(), "wacli auth") {
		t.Errorf("err = %v, want instructions naming wacli auth", err)
	}
}

func TestPreflightReportsAnUnreadableStore(t *testing.T) {
	err := Preflight(fakeEnv{version: "0.18.1", authed: true, storeErr: errors.New("permission denied")})
	if err == nil {
		t.Fatal("an unreadable store must stop startup")
	}
	if !strings.Contains(err.Error(), "permission denied") {
		t.Errorf("err = %v, want the underlying reason", err)
	}
}

func TestAtLeast(t *testing.T) {
	cases := []struct {
		version string
		want    bool
	}{
		{"0.18.0", true},
		{"0.18.1", true},
		{"0.19.0", true},
		{"1.0.0", true},
		{"0.17.9", false},
		{"0.1.0", false},
	}
	for _, c := range cases {
		got, err := atLeast(c.version, 0, 18)
		if err != nil {
			t.Fatalf("atLeast(%q): %v", c.version, err)
		}
		if got != c.want {
			t.Errorf("atLeast(%q) = %v, want %v", c.version, got, c.want)
		}
	}
}
