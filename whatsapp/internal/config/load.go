package config

import (
	_ "embed"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"sort"
	"strings"

	"github.com/BurntSushi/toml"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/keys"
)

//go:embed default.toml
var defaultTOML string

// Default is the shipped configuration. It is decoded from the same embedded
// file the documentation describes, so the two cannot drift.
func Default() Config {
	var c Config
	if _, err := toml.Decode(defaultTOML, &c); err != nil {
		// The embedded file is part of the binary; a failure here is a build
		// defect, not a runtime condition a user can cause or recover from.
		panic("config: embedded default.toml does not parse: " + err.Error())
	}
	return c
}

// Load reads each path in turn over the defaults, so a later file wins over an
// earlier one - config.toml first, then the overrides file :set! writes.
//
// A missing file is not an error: wa runs fine with no configuration at all.
// Unknown settings are returned as warnings rather than failing, because a
// config shared across wa versions will name settings this build has not heard
// of. A syntax error is fatal - silently running on defaults would hide it.
func Load(paths ...string) (Config, []Warning, error) {
	cfg := Default()
	var warns []Warning
	for _, path := range paths {
		var w []Warning
		var err error
		cfg, w, err = apply(cfg, path)
		if err != nil {
			return Default(), nil, err
		}
		warns = append(warns, w...)
	}
	return cfg, warns, nil
}

func apply(cfg Config, path string) (Config, []Warning, error) {
	if path == "" {
		return cfg, nil, nil
	}

	body, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return cfg, nil, nil
	}
	if err != nil {
		return cfg, nil, fmt.Errorf("reading %s: %w", path, err)
	}

	// Keymaps merge rather than replace, so a user who binds one key keeps the
	// rest of the defaults. Decoding into the populated maps would leave that
	// to the decoder's discretion, so do it explicitly.
	var user Config
	md, err := toml.Decode(string(body), &user)
	if err != nil {
		return cfg, nil, fmt.Errorf("%s: %w", path, err)
	}

	// Re-decode over what we have for scalars: the decoder only touches keys
	// the file actually contains, which is exactly the overlay we want.
	base := cfg.Keys
	cfg.Keys = nil
	if _, err := toml.Decode(string(body), &cfg); err != nil {
		return cfg, nil, fmt.Errorf("%s: %w", path, err)
	}
	cfg.Keys = mergeKeys(base, user.Keys)

	var warns []Warning
	for _, k := range md.Undecoded() {
		warns = append(warns, Warning{File: path, Key: k.String()})
	}
	sort.Slice(warns, func(i, j int) bool { return warns[i].Key < warns[j].Key })
	return cfg, warns, nil
}

// mergeKeys overlays user bindings onto the defaults, per mode. Binding a key
// to the empty string removes the default, which is how a user disables one.
func mergeKeys(base, user map[string]map[string]string) map[string]map[string]string {
	out := make(map[string]map[string]string, len(base))
	for mode, binds := range base {
		m := make(map[string]string, len(binds))
		for k, v := range binds {
			m[k] = v
		}
		out[mode] = m
	}
	for mode, binds := range user {
		if out[mode] == nil {
			out[mode] = make(map[string]string, len(binds))
		}
		for k, v := range binds {
			if v == "" {
				delete(out[mode], k)
				continue
			}
			out[mode][k] = v
		}
	}
	return out
}

// Validate checks every keymap: the mode must exist, the notation must parse,
// and - for the action tables - the action must be registered. An unknown
// action is fatal rather than a warning, because a key bound to nothing looks
// like a broken program, not a misconfiguration.
func (c Config) Validate(known func(action string) bool) error {
	leader, err := keys.Parse(c.UI.Leader, nil)
	if err != nil {
		return fmt.Errorf("ui.leader: %w", err)
	}

	modes := make([]string, 0, len(c.Keys))
	for mode := range c.Keys {
		modes = append(modes, mode)
	}
	sort.Strings(modes)

	var problems []string
	for _, mode := range modes {
		if !actionModes[mode] && !grammarModes[mode] {
			problems = append(problems, fmt.Sprintf(
				"keys.%s: unknown mode (expected one of %s)", mode, knownModes()))
			continue
		}
		binds := c.Keys[mode]
		notations := make([]string, 0, len(binds))
		for n := range binds {
			notations = append(notations, n)
		}
		sort.Strings(notations)

		for _, n := range notations {
			if _, err := keys.Parse(n, leader); err != nil {
				problems = append(problems, fmt.Sprintf("keys.%s: %v", mode, err))
				continue
			}
			target := binds[n]
			if target == "" {
				problems = append(problems, fmt.Sprintf(
					"keys.%s: %q is bound to nothing", mode, n))
				continue
			}
			if actionModes[mode] && known != nil && !known(target) {
				problems = append(problems, fmt.Sprintf(
					"keys.%s: %q is bound to %q, which is not an action (try :actions)",
					mode, n, target))
			}
		}
	}
	if len(problems) > 0 {
		return errors.New(strings.Join(problems, "\n"))
	}
	return nil
}

func knownModes() string {
	all := make([]string, 0, len(actionModes)+len(grammarModes))
	for m := range actionModes {
		all = append(all, m)
	}
	for m := range grammarModes {
		all = append(all, m)
	}
	sort.Strings(all)
	return strings.Join(all, ", ")
}

// Leader is the parsed leader key sequence.
func (c Config) Leader() []keys.Key {
	k, err := keys.Parse(c.UI.Leader, nil)
	if err != nil {
		return []keys.Key{{Special: keys.Space}}
	}
	return k
}
