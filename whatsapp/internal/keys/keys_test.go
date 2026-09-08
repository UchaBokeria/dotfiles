package keys

import "testing"

func TestParse(t *testing.T) {
	leader := []Key{{Special: Space}}
	cases := []struct {
		in   string
		want string
	}{
		{"j", "j"},
		{"gg", "gg"},
		{"<C-d>", "<C-d>"},
		{"<C-D>", "<C-D>"},
		{"<Esc>", "<Esc>"},
		{"<CR>", "<CR>"},
		{"<Tab>", "<Tab>"},
		{"<S-Tab>", "<S-Tab>"},
		{"<M-x>", "<M-x>"},
		{"<A-x>", "<M-x>"},
		{"<leader>ts", "<Space>ts"},
		{"<Space>", "<Space>"},
		{"<lt>", "<lt>"}, // `<` round trips as <lt>, which is the canonical spelling
		{"5j", "5j"},
		{"g~", "g~"},
		{"\"", "\""},
		{"<C-S-x>", "<C-S-x>"},
	}
	for _, c := range cases {
		got, err := Parse(c.in, leader)
		if err != nil {
			t.Fatalf("Parse(%q): %v", c.in, err)
		}
		var s string
		for _, k := range got {
			s += k.String()
		}
		if s != c.want {
			t.Errorf("Parse(%q) = %q, want %q", c.in, s, c.want)
		}
	}
}

func TestParseRejectsGarbage(t *testing.T) {
	for _, in := range []string{"<C->", "<Nope>", "<C-d", "<>", "", "<S->"} {
		if _, err := Parse(in, nil); err == nil {
			t.Errorf("Parse(%q) should have failed", in)
		}
	}
}

func TestStringRoundTrips(t *testing.T) {
	for _, in := range []string{"<C-d>", "<M-S-x>", "a", "<Esc>", "<Space>", "<CR>"} {
		ks, err := Parse(in, nil)
		if err != nil {
			t.Fatal(err)
		}
		again, err := Parse(ks[0].String(), nil)
		if err != nil {
			t.Fatalf("re-parsing %q: %v", ks[0].String(), err)
		}
		if again[0] != ks[0] {
			t.Errorf("%q did not round trip: %+v vs %+v", in, ks[0], again[0])
		}
	}
}

func TestLeaderWithoutADefinitionIsAnError(t *testing.T) {
	if _, err := Parse("<leader>x", nil); err == nil {
		t.Fatal("<leader> with no leader defined must be an error, not a silent drop")
	}
}

func TestIsDigit(t *testing.T) {
	k, _ := Parse("5", nil)
	if d, ok := k[0].Digit(); !ok || d != 5 {
		t.Errorf("Digit() = %d, %v", d, ok)
	}
	k, _ = Parse("<C-5>", nil)
	if _, ok := k[0].Digit(); ok {
		t.Error("a modified key is not a digit")
	}
}

func TestPrintable(t *testing.T) {
	k, _ := Parse("a", nil)
	if r, ok := k[0].Printable(); !ok || r != 'a' {
		t.Errorf("Printable() = %q, %v", r, ok)
	}
	sp, _ := Parse("<Space>", nil)
	if r, ok := sp[0].Printable(); !ok || r != ' ' {
		t.Errorf("Space should be printable as a space, got %q %v", r, ok)
	}
	esc, _ := Parse("<Esc>", nil)
	if _, ok := esc[0].Printable(); ok {
		t.Error("Esc is not printable")
	}
	ctrl, _ := Parse("<C-a>", nil)
	if _, ok := ctrl[0].Printable(); ok {
		t.Error("a control key is not printable text")
	}
}
