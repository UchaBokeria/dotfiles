package config

import "testing"

func TestGetSetDottedPath(t *testing.T) {
	c := Default()
	if err := c.Set("ui.list_width", "40"); err != nil {
		t.Fatal(err)
	}
	if c.UI.ListWidth != 40 {
		t.Fatalf("Set did not apply: %d", c.UI.ListWidth)
	}
	got, err := c.Get("ui.list_width")
	if err != nil {
		t.Fatal(err)
	}
	if got != "40" {
		t.Errorf("Get = %q, want \"40\"", got)
	}
	if err := c.Set("ui.nonexistent", "1"); err == nil {
		t.Error("Set on an unknown path must fail")
	}
	if err := c.Set("ui.list_width", "wide"); err == nil {
		t.Error("Set with an unparseable value must fail")
	}
}

func TestSetBool(t *testing.T) {
	c := Default()
	if err := c.Set("ui.ignorecase", "false"); err != nil {
		t.Fatal(err)
	}
	if c.UI.IgnoreCase {
		t.Error("ignorecase should be false")
	}
	if got, _ := c.Get("ui.ignorecase"); got != "false" {
		t.Errorf("Get = %q, want \"false\"", got)
	}
}

func TestSetDuration(t *testing.T) {
	c := Default()
	if err := c.Set("lock.idle_timeout", "45s"); err != nil {
		t.Fatal(err)
	}
	if got, _ := c.Get("lock.idle_timeout"); got != "45s" {
		t.Errorf("Get = %q, want \"45s\"", got)
	}
	if err := c.Set("lock.idle_timeout", "soon"); err == nil {
		t.Error("an unparseable duration must fail")
	}
}

func TestGetUnknownPathNamesIt(t *testing.T) {
	c := Default()
	_, err := c.Get("ui.nope")
	if err == nil || !contains(err.Error(), "ui.nope") {
		t.Errorf("err = %v, want it to name the path", err)
	}
}

func TestPathsListsEveryLeaf(t *testing.T) {
	got := Paths()
	want := []string{"ui.list_width", "lock.enabled", "sync.poll_interval", "wacli.bin"}
	for _, w := range want {
		found := false
		for _, g := range got {
			if g == w {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("Paths() is missing %q", w)
		}
	}
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(sub) == 0 || indexOf(s, sub) >= 0)
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}
