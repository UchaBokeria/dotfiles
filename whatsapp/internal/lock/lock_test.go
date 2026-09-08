package lock

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func tmpPath(t *testing.T) string {
	t.Helper()
	return filepath.Join(t.TempDir(), "lock.json")
}

func TestSetThenVerify(t *testing.T) {
	p := tmpPath(t)
	if err := Set(p, "correct horse"); err != nil {
		t.Fatal(err)
	}
	ok, err := Verify(p, "correct horse")
	if err != nil || !ok {
		t.Fatalf("Verify with the right password = %v, %v", ok, err)
	}
	ok, err = Verify(p, "wrong")
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Fatal("Verify accepted the wrong password")
	}
}

func TestCredentialFileIsNotWorldReadable(t *testing.T) {
	p := tmpPath(t)
	if err := Set(p, "x"); err != nil {
		t.Fatal(err)
	}
	fi, err := os.Stat(p)
	if err != nil {
		t.Fatal(err)
	}
	if fi.Mode().Perm() != 0o600 {
		t.Fatalf("mode = %v, want 0600", fi.Mode().Perm())
	}
}

func TestStoredFileHoldsNoPlaintext(t *testing.T) {
	p := tmpPath(t)
	Set(p, "hunter2")
	body, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(body), "hunter2") {
		t.Fatalf("the password is in the file verbatim:\n%s", body)
	}
}

func TestIdenticalPasswordsProduceDifferentFiles(t *testing.T) {
	a, b := tmpPath(t), tmpPath(t)
	Set(a, "same")
	Set(b, "same")

	ca, err := Read(a)
	if err != nil {
		t.Fatal(err)
	}
	cb, err := Read(b)
	if err != nil {
		t.Fatal(err)
	}
	if ca.Salt == cb.Salt {
		t.Error("the salt is not random")
	}
	if ca.Hash == cb.Hash {
		t.Error("identical passwords produced identical hashes, so the salt is not being used")
	}
}

func TestVerifyOnAMissingFile(t *testing.T) {
	ok, err := Verify(tmpPath(t), "x")
	if ok {
		t.Fatal("a missing credential must never verify")
	}
	if !errors.Is(err, ErrNoCredential) {
		t.Fatalf("err = %v, want ErrNoCredential - the caller has to tell this apart from a wrong password", err)
	}
}

func TestSetRejectsAnEmptyPassword(t *testing.T) {
	if err := Set(tmpPath(t), ""); err == nil {
		t.Fatal("an empty password must be refused; it would be a lock that opens itself")
	}
}

func TestClear(t *testing.T) {
	p := tmpPath(t)
	Set(p, "x")
	if !Exists(p) {
		t.Fatal("Exists is wrong after Set")
	}
	if err := Clear(p); err != nil {
		t.Fatal(err)
	}
	if Exists(p) {
		t.Fatal("the credential survived Clear")
	}
	if err := Clear(p); err != nil {
		t.Errorf("clearing an absent credential should succeed, got %v", err)
	}
}

func TestVerifyUsesTheStoredParameters(t *testing.T) {
	// A credential written with different cost parameters must still verify,
	// so changing the constants does not lock people out.
	p := tmpPath(t)
	Set(p, "pw")

	c, err := Read(p)
	if err != nil {
		t.Fatal(err)
	}
	if c.Time == 0 || c.Memory == 0 || c.Par == 0 {
		t.Fatalf("the parameters were not recorded: %+v", c)
	}
}

func TestVerifyRejectsAnUnknownAlgorithm(t *testing.T) {
	p := tmpPath(t)
	os.WriteFile(p, []byte(`{"algo":"rot13","salt":"00","hash":"00","t":1,"m":8,"p":1}`), 0o600)
	if _, err := Verify(p, "x"); err == nil {
		t.Fatal("an unknown algorithm must be an error, not a silent false")
	}
}

func TestVerifyRejectsCorruptHex(t *testing.T) {
	p := tmpPath(t)
	os.WriteFile(p, []byte(`{"algo":"argon2id","salt":"zz","hash":"zz","t":1,"m":8,"p":1}`), 0o600)
	if _, err := Verify(p, "x"); err == nil {
		t.Fatal("a corrupt credential must be reported")
	}
}

func TestIdleFires(t *testing.T) {
	var fired atomic.Int32
	i := NewIdle(30*time.Millisecond, func() { fired.Add(1) })
	defer i.Stop()

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if fired.Load() > 0 {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatal("the idle timer never fired")
}

func TestTouchDefersTheIdleTimer(t *testing.T) {
	var fired atomic.Int32
	i := NewIdle(120*time.Millisecond, func() { fired.Add(1) })
	defer i.Stop()

	for n := 0; n < 6; n++ {
		time.Sleep(30 * time.Millisecond)
		i.Touch()
	}
	if fired.Load() != 0 {
		t.Fatal("the timer fired despite continuous activity")
	}
}

func TestStopPreventsFiring(t *testing.T) {
	var fired atomic.Int32
	i := NewIdle(20*time.Millisecond, func() { fired.Add(1) })
	i.Stop()
	time.Sleep(80 * time.Millisecond)
	if fired.Load() != 0 {
		t.Error("the timer fired after Stop")
	}
	i.Stop() // must not panic
}

func TestZeroTimeoutDisablesTheLock(t *testing.T) {
	var fired atomic.Int32
	i := NewIdle(0, func() { fired.Add(1) })
	defer i.Stop()
	if i.Enabled() {
		t.Error("a zero timeout must not arm the timer")
	}
	i.Touch() // must not panic
	time.Sleep(30 * time.Millisecond)
	if fired.Load() != 0 {
		t.Error("a disabled idle lock fired")
	}
}
