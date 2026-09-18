package ui

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// Glass.
//
// A terminal cannot blur anything: what is behind the window belongs to the
// compositor. What wa can do is stop painting over it. With the bars and the
// popup left unpainted, the terminal's own transparency shows through, and
// whatever the compositor is doing behind it - Hyprland's blur, or hyprglass's
// refracted edges - becomes part of the interface instead of being hidden
// behind a rectangle of solid colour.
//
// So this detects a compositor worth deferring to, and the rest is subtraction.

// GlassAvailable reports whether the compositor is doing something worth
// showing through, and says what it found either way.
func GlassAvailable() (bool, string) {
	if os.Getenv("HYPRLAND_INSTANCE_SIGNATURE") == "" {
		return false, "not running under Hyprland"
	}
	if hyprglassLoaded() {
		return true, "hyprglass is loaded"
	}
	if home, err := os.UserHomeDir(); err == nil {
		so := filepath.Join(home, ".local", "share", "blackwall", "hyprglass", "hyprglass.so")
		if _, err := os.Stat(so); err == nil {
			return true, "hyprglass is installed (run `blackwall-glass on` to load it)"
		}
	}
	return true, "Hyprland's own blur"
}

// hyprglassLoaded asks the compositor what it has loaded.
func hyprglassLoaded() bool {
	if _, err := exec.LookPath("hyprctl"); err != nil {
		return false
	}
	out, err := exec.Command("hyprctl", "plugin", "list").Output()
	if err != nil {
		return false
	}
	return strings.Contains(string(out), "hyprglass")
}

// GlassWanted decides whether to draw without solid bars.
func GlassWanted(setting string) bool {
	switch strings.ToLower(strings.TrimSpace(setting)) {
	case "on", "true", "yes":
		return true
	case "off", "false", "no":
		return false
	default:
		on, _ := GlassAvailable()
		return on
	}
}
