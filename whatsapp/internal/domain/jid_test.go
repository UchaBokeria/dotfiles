package domain

import "testing"

func TestParseJID(t *testing.T) {
	cases := []struct {
		in   string
		user string
		srv  string
		dev  string
		kind ChatKind
	}{
		{"995568669331@s.whatsapp.net", "995568669331", "s.whatsapp.net", "", KindDM},
		{"995568669331.0:12@s.whatsapp.net", "995568669331.0", "s.whatsapp.net", "12", KindDM},
		{"120363001234567890@g.us", "120363001234567890", "g.us", "", KindGroup},
		{"120363001234567890@newsletter", "120363001234567890", "newsletter", "", KindNewsletter},
		{"status@broadcast", "status", "broadcast", "", KindBroadcast},
		{"995568669331", "995568669331", "s.whatsapp.net", "", KindDM},
		{"+995 568 66 93 31", "995568669331", "s.whatsapp.net", "", KindDM},
	}
	for _, c := range cases {
		got, err := ParseJID(c.in)
		if err != nil {
			t.Fatalf("ParseJID(%q): %v", c.in, err)
		}
		if got.User != c.user || got.Server != c.srv || got.Device != c.dev {
			t.Errorf("ParseJID(%q) = %+v, want user=%q srv=%q dev=%q", c.in, got, c.user, c.srv, c.dev)
		}
		if got.Kind() != c.kind {
			t.Errorf("ParseJID(%q).Kind() = %q, want %q", c.in, got.Kind(), c.kind)
		}
	}
}

func TestParseJIDRoundTrip(t *testing.T) {
	for _, s := range []string{"995568669331@s.whatsapp.net", "120363001234567890@g.us"} {
		j, err := ParseJID(s)
		if err != nil {
			t.Fatal(err)
		}
		if j.String() != s {
			t.Errorf("round trip %q -> %q", s, j.String())
		}
	}
}

func TestParseJIDRejectsEmpty(t *testing.T) {
	for _, in := range []string{"", "   ", "@s.whatsapp.net"} {
		if _, err := ParseJID(in); err == nil {
			t.Errorf("ParseJID(%q) should have failed", in)
		}
	}
}

func TestZeroJID(t *testing.T) {
	var j JID
	if !j.IsZero() {
		t.Error("the zero JID must report IsZero")
	}
	if j.String() != "" {
		t.Errorf("the zero JID stringifies to %q, want empty", j.String())
	}
}

func TestDisplay(t *testing.T) {
	dm, _ := ParseJID("995568669331@s.whatsapp.net")
	if dm.Display() != "+995568669331" {
		t.Errorf("Display = %q, want +995568669331", dm.Display())
	}
	grp, _ := ParseJID("120363001234567890@g.us")
	if grp.Display() != "120363001234567890" {
		t.Errorf("group Display = %q", grp.Display())
	}
}
