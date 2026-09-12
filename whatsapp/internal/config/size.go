package config

import (
	"fmt"
	"strconv"
	"strings"
)

// Size is a byte count written in TOML the way a person writes one: "2MB",
// "512KB", "0". The units are powers of 1024, matching what the interface
// prints back.
type Size int64

// B is the size in bytes.
func (s Size) B() int64 { return int64(s) }

// UnmarshalText implements encoding.TextUnmarshaler for the TOML decoder.
func (s *Size) UnmarshalText(b []byte) error {
	text := strings.TrimSpace(string(b))
	if text == "" {
		return fmt.Errorf("a size cannot be empty (try \"2MB\", or \"0\" for none)")
	}

	// Split the number from the unit rather than matching a fixed set of
	// suffixes: people write "2MB", "2 MB", "2m" and "2", and refusing three
	// of those is not a feature.
	i := 0
	for i < len(text) && (text[i] >= '0' && text[i] <= '9' || text[i] == '.') {
		i++
	}
	n, err := strconv.ParseFloat(text[:i], 64)
	if err != nil {
		return fmt.Errorf("%q is not a size (try \"2MB\", \"512KB\", \"0\")", text)
	}

	mult := int64(1)
	switch strings.ToLower(strings.TrimSpace(strings.TrimSuffix(text[i:], "iB"))) {
	case "", "b":
	case "k", "kb":
		mult = 1 << 10
	case "m", "mb":
		mult = 1 << 20
	case "g", "gb":
		mult = 1 << 30
	default:
		return fmt.Errorf("%q is not a unit (use B, KB, MB or GB)", strings.TrimSpace(text[i:]))
	}
	if n < 0 {
		return fmt.Errorf("%q is negative", text)
	}
	*s = Size(n * float64(mult))
	return nil
}

// MarshalText implements encoding.TextMarshaler so :set! round trips.
func (s Size) MarshalText() ([]byte, error) { return []byte(s.String()), nil }

func (s Size) String() string {
	n := int64(s)
	switch {
	case n == 0:
		return "0"
	case n%(1<<30) == 0:
		return strconv.FormatInt(n>>30, 10) + "GB"
	case n%(1<<20) == 0:
		return strconv.FormatInt(n>>20, 10) + "MB"
	case n%(1<<10) == 0:
		return strconv.FormatInt(n>>10, 10) + "KB"
	}
	return strconv.FormatInt(n, 10) + "B"
}
