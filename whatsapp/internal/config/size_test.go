package config

import "testing"

func TestSizeParses(t *testing.T) {
	cases := []struct {
		in   string
		want int64
	}{
		{"0", 0},
		{"512", 512},
		{"512B", 512},
		{"512KB", 512 << 10},
		{"2MB", 2 << 20},
		{"2 MB", 2 << 20},
		{"2mb", 2 << 20},
		{"2m", 2 << 20},
		{"1.5MB", 1024 * 1024 * 3 / 2},
		{"1GB", 1 << 30},
		{"2MiB", 2 << 20},
	}
	for _, c := range cases {
		var s Size
		if err := s.UnmarshalText([]byte(c.in)); err != nil {
			t.Errorf("%q: %v", c.in, err)
			continue
		}
		if s.B() != c.want {
			t.Errorf("%q = %d bytes, want %d", c.in, s.B(), c.want)
		}
	}
}

func TestSizeRejectsNonsense(t *testing.T) {
	for _, in := range []string{"", "  ", "big", "2TB", "MB", "-1"} {
		var s Size
		if err := s.UnmarshalText([]byte(in)); err == nil {
			t.Errorf("%q was accepted as %v", in, s)
		}
	}
}

func TestSizeRoundTrips(t *testing.T) {
	// :set! writes the value back, so what it writes must parse to the same
	// number, or a saved setting drifts every time it is saved.
	for _, in := range []string{"0", "512B", "512KB", "2MB", "1GB", "1536B"} {
		var s Size
		if err := s.UnmarshalText([]byte(in)); err != nil {
			t.Fatal(err)
		}
		var back Size
		if err := back.UnmarshalText([]byte(s.String())); err != nil {
			t.Fatalf("%q printed as %q, which does not parse: %v", in, s, err)
		}
		if back != s {
			t.Errorf("%q printed as %q, which parses as %v", in, s, back)
		}
	}
}

func TestSetAndGetASize(t *testing.T) {
	c, _, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if err := c.Set("media.auto_download", "512KB"); err != nil {
		t.Fatal(err)
	}
	if c.Media.AutoDownload.B() != 512<<10 {
		t.Errorf("auto_download = %d bytes", c.Media.AutoDownload.B())
	}
	got, err := c.Get("media.auto_download")
	if err != nil {
		t.Fatal(err)
	}
	if got != "512KB" {
		t.Errorf("Get = %q", got)
	}
	if err := c.Set("media.auto_download", "enormous"); err == nil {
		t.Error("a bad size should be refused")
	}
}

func TestSizeIsListedAsASetting(t *testing.T) {
	// A new type that the reflect walker descends into instead of treating as
	// a leaf disappears from :set completion and from the settings picker.
	for _, p := range Paths() {
		if p == "media.auto_download" {
			return
		}
	}
	t.Error("media.auto_download is not in Paths()")
}
