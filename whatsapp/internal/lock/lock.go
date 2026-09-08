// Package lock is the password gate in front of the interface.
//
// Its limits are worth stating plainly, because a lock screen invites the
// assumption that it protects data. It does not. It hides the interface, and
// nothing more: wacli's store stays readable on disk by any process running as
// the same user, with or without a password set here. Encrypting the store
// would be wacli's job, not this one.
//
// What this does buy is that a shoulder-surfer or someone who sits down at an
// unlocked terminal does not read the conversation.
package lock

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"

	"golang.org/x/crypto/argon2"
)

// Argon2id parameters. Deliberately on the expensive side: this is checked
// once when a human opens the client, so a tenth of a second is unnoticeable
// here and costly for anyone working through a stolen credential file.
const (
	timeCost   uint32 = 3
	memoryCost uint32 = 64 * 1024 // KiB
	threads    uint8  = 4
	keyLength  uint32 = 32
	saltLength        = 16
)

// ErrNoCredential means no password has been set.
var ErrNoCredential = errors.New("no password is set (run: wa lock set)")

// Credential is the stored verifier. It never contains the password.
type Credential struct {
	Algo   string `json:"algo"`
	Salt   string `json:"salt"`
	Hash   string `json:"hash"`
	Time   uint32 `json:"t"`
	Memory uint32 `json:"m"`
	Par    uint8  `json:"p"`
}

// Set writes a new credential.
//
// The file goes in the state directory at 0600, never in config.toml: that
// file is symlinked out of the dotfiles repository, and a password verifier
// committed to git would be a mistake nobody notices until it is public.
func Set(path, password string) error {
	if password == "" {
		return fmt.Errorf("refusing to set an empty password")
	}
	salt := make([]byte, saltLength)
	if _, err := rand.Read(salt); err != nil {
		return fmt.Errorf("reading random bytes: %w", err)
	}
	sum := argon2.IDKey([]byte(password), salt, timeCost, memoryCost, threads, keyLength)

	body, err := json.MarshalIndent(Credential{
		Algo:   "argon2id",
		Salt:   hex.EncodeToString(salt),
		Hash:   hex.EncodeToString(sum),
		Time:   timeCost,
		Memory: memoryCost,
		Par:    threads,
	}, "", "  ")
	if err != nil {
		return err
	}

	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, body, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

// Clear removes the credential, turning the lock off.
func Clear(path string) error {
	err := os.Remove(path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil
	}
	return err
}

// Exists reports whether a password is set.
func Exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// Read loads the credential.
func Read(path string) (Credential, error) {
	body, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return Credential{}, ErrNoCredential
	}
	if err != nil {
		return Credential{}, err
	}
	var c Credential
	if err := json.Unmarshal(body, &c); err != nil {
		return Credential{}, fmt.Errorf("%s: %w", path, err)
	}
	return c, nil
}

// Verify checks a password.
//
// A missing credential is an error rather than a quiet false: the caller needs
// to tell "wrong password" apart from "there is no password", and returning
// false for both would let a corrupted file read as a permanently wrong one.
func Verify(path, password string) (bool, error) {
	c, err := Read(path)
	if err != nil {
		return false, err
	}
	if c.Algo != "argon2id" {
		return false, fmt.Errorf("%s: unknown algorithm %q", path, c.Algo)
	}
	salt, err := hex.DecodeString(c.Salt)
	if err != nil {
		return false, fmt.Errorf("%s: bad salt: %w", path, err)
	}
	want, err := hex.DecodeString(c.Hash)
	if err != nil {
		return false, fmt.Errorf("%s: bad hash: %w", path, err)
	}

	// The stored parameters are used rather than the constants above, so a
	// credential written by an older build still verifies after they change.
	got := argon2.IDKey([]byte(password), salt,
		c.Time, c.Memory, c.Par, uint32(len(want)))

	return subtle.ConstantTimeCompare(got, want) == 1, nil
}
