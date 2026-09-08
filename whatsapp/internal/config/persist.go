package config

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"github.com/BurntSushi/toml"
)

// Persist records assignments in an overrides file that is loaded after the
// main configuration.
//
// It is deliberately a separate file rather than a rewritten block inside
// config.toml, for two reasons. TOML forbids defining the same table twice, so
// an appended `[ui]` block cannot coexist with a hand-written `[ui]` section -
// the result would not parse. And config.toml is symlinked out of the dotfiles
// repository, so writing to it from `:set!` would leave the repository dirty
// every time a setting is nudged.
//
// Existing overrides are merged, so two `:set!` calls do not lose each other.
func Persist(file string, assignments map[string]string) error {
	if len(assignments) == 0 {
		return nil
	}

	// Reject anything that would not load back, so a bad :set! can never leave
	// a file that refuses to parse on the next start.
	probe := Default()
	for path, value := range assignments {
		if err := probe.Set(path, value); err != nil {
			return err
		}
	}

	merged, err := readOverrides(file)
	if err != nil {
		return err
	}
	for path, value := range assignments {
		merged[path] = value
	}

	body, err := renderOverrides(merged)
	if err != nil {
		return err
	}

	if err := os.MkdirAll(filepath.Dir(file), 0o755); err != nil {
		return fmt.Errorf("creating %s: %w", filepath.Dir(file), err)
	}
	tmp := file + ".tmp"
	if err := os.WriteFile(tmp, []byte(body), 0o644); err != nil {
		return fmt.Errorf("writing %s: %w", tmp, err)
	}
	// Rename so a crash mid-write cannot truncate a working overrides file.
	if err := os.Rename(tmp, file); err != nil {
		return fmt.Errorf("replacing %s: %w", file, err)
	}
	return nil
}

// readOverrides flattens an existing overrides file back into dotted paths.
func readOverrides(file string) (map[string]string, error) {
	out := map[string]string{}
	body, err := os.ReadFile(file)
	if errors.Is(err, fs.ErrNotExist) {
		return out, nil
	}
	if err != nil {
		return nil, fmt.Errorf("reading %s: %w", file, err)
	}

	var raw map[string]any
	if _, err := toml.Decode(string(body), &raw); err != nil {
		// A corrupt overrides file should not wedge :set! forever; start over
		// rather than refusing every future write.
		return out, nil
	}
	for section, v := range raw {
		table, ok := v.(map[string]any)
		if !ok {
			continue
		}
		for key, value := range table {
			out[section+"."+key] = fmt.Sprint(value)
		}
	}
	return out, nil
}

func renderOverrides(assignments map[string]string) (string, error) {
	sections := map[string]map[string]string{}
	for path, value := range assignments {
		dot := strings.LastIndex(path, ".")
		if dot < 0 {
			return "", fmt.Errorf("%q is not a section.setting path", path)
		}
		section, key := path[:dot], path[dot+1:]
		if sections[section] == nil {
			sections[section] = map[string]string{}
		}
		sections[section][key] = value
	}

	names := make([]string, 0, len(sections))
	for name := range sections {
		names = append(names, name)
	}
	sort.Strings(names)

	var b strings.Builder
	b.WriteString("# wa - written by :set!\n")
	b.WriteString("# Loaded after config.toml, so anything here wins. Safe to delete.\n")
	for _, name := range names {
		fmt.Fprintf(&b, "\n[%s]\n", name)
		keyNames := make([]string, 0, len(sections[name]))
		for k := range sections[name] {
			keyNames = append(keyNames, k)
		}
		sort.Strings(keyNames)
		for _, k := range keyNames {
			fmt.Fprintf(&b, "%s = %s\n", k, tomlLiteral(sections[name][k]))
		}
	}
	return b.String(), nil
}

// tomlLiteral renders a value the way TOML wants it: bare for numbers and
// booleans, quoted otherwise. Durations are strings, so they quote correctly.
func tomlLiteral(v string) string {
	if v == "true" || v == "false" {
		return v
	}
	if _, err := strconv.ParseInt(v, 10, 64); err == nil {
		return v
	}
	return strconv.Quote(v)
}
