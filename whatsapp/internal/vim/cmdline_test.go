package vim

import (
	"strings"
	"testing"
)

func TestParseCommand(t *testing.T) {
	cases := []struct {
		in   string
		name string
		bang bool
		args []string
		raw  string
	}{
		{":set ui.list_width=40", "set", false, []string{"ui.list_width=40"}, "ui.list_width=40"},
		{":set! ui.list_width=40", "set", true, []string{"ui.list_width=40"}, "ui.list_width=40"},
		{"set ui.list_width=40", "set", false, []string{"ui.list_width=40"}, "ui.list_width=40"},
		{":map n <C-p> picker.chats", "map", false, []string{"n", "<C-p>", "picker.chats"}, "n <C-p> picker.chats"},
		{":grep deploy the nuc", "grep", false, []string{"deploy", "the", "nuc"}, "deploy the nuc"},
		{":q", "q", false, nil, ""},
		{":q!", "q", true, nil, ""},
		{`:chat "Team Blackwall"`, "chat", false, []string{"Team Blackwall"}, `"Team Blackwall"`},
	}
	for _, c := range cases {
		got, err := ParseCommand(c.in)
		if err != nil {
			t.Fatalf("ParseCommand(%q): %v", c.in, err)
		}
		if got.Name != c.name || got.Bang != c.bang || got.Raw != c.raw {
			t.Errorf("ParseCommand(%q) = %+v", c.in, got)
		}
		if len(got.Args) != len(c.args) {
			t.Fatalf("ParseCommand(%q) args = %v, want %v", c.in, got.Args, c.args)
		}
		for i := range c.args {
			if got.Args[i] != c.args[i] {
				t.Errorf("ParseCommand(%q) args = %v, want %v", c.in, got.Args, c.args)
			}
		}
	}
}

func TestParseCommandRejectsEmpty(t *testing.T) {
	for _, in := range []string{"", ":", "   ", ": "} {
		if _, err := ParseCommand(in); err == nil {
			t.Errorf("ParseCommand(%q) should have failed", in)
		}
	}
}

func TestParseCommandRejectsAnUnclosedQuote(t *testing.T) {
	if _, err := ParseCommand(`:chat "Team`); err == nil {
		t.Fatal("an unclosed quote must be reported, not silently accepted")
	}
}

func TestParseCommandKeepsRawForSentenceCommands(t *testing.T) {
	// :grep takes a phrase, not a list of words.
	c, err := ParseCommand(":grep did you push")
	if err != nil {
		t.Fatal(err)
	}
	if c.Raw != "did you push" {
		t.Errorf("Raw = %q", c.Raw)
	}
}

func TestCompleteCommand(t *testing.T) {
	names := []string{"set", "search", "sync", "quit"}
	got := CompleteCommand(":se", names)
	if len(got) != 2 || got[0] != "search" || got[1] != "set" {
		t.Errorf("completions = %v, want [search set]", got)
	}
	if got := CompleteCommand(":", names); len(got) != 4 {
		t.Errorf("a bare colon should offer everything, got %v", got)
	}
	if got := CompleteCommand(":set ", names); got != nil {
		t.Errorf("once an argument is being typed the name is settled, got %v", got)
	}
}

func TestCompleteArg(t *testing.T) {
	got := CompleteArg(":chat An", []string{"Ana", "Andro", "Beka"})
	if len(got) != 2 || got[0] != "Ana" {
		t.Errorf("completions = %v", got)
	}
	if got := CompleteArg(":chat ", []string{"Ana", "Beka"}); len(got) != 2 {
		t.Errorf("an empty prefix should offer everything, got %v", got)
	}
}

func TestHistory(t *testing.T) {
	h := NewHistory(10)
	h.Add(":set x=1")
	h.Add(":grep nuc")

	if got, ok := h.Prev(); !ok || got != ":grep nuc" {
		t.Fatalf("Prev = %q, %v", got, ok)
	}
	if got, ok := h.Prev(); !ok || got != ":set x=1" {
		t.Fatalf("second Prev = %q, %v", got, ok)
	}
	if _, ok := h.Prev(); ok {
		t.Error("Prev past the oldest entry should report false")
	}
	if got, ok := h.Next(); !ok || got != ":grep nuc" {
		t.Fatalf("Next = %q, %v", got, ok)
	}
	if got, ok := h.Next(); !ok || got != "" {
		t.Errorf("Next past the newest should clear the prompt, got %q, %v", got, ok)
	}
}

func TestHistorySkipsBlanksAndRepeats(t *testing.T) {
	h := NewHistory(10)
	h.Add(":q")
	h.Add(":q")
	h.Add("   ")
	if n := len(h.Items()); n != 1 {
		t.Errorf("history holds %d entries, want 1: %v", n, h.Items())
	}
}

func TestHistoryIsBounded(t *testing.T) {
	h := NewHistory(3)
	for _, s := range []string{"a", "b", "c", "d", "e"} {
		h.Add(s)
	}
	items := h.Items()
	if len(items) != 3 || items[0] != "c" {
		t.Errorf("history = %v, want the last three", items)
	}
}

func TestSplitArgsHandlesEscapes(t *testing.T) {
	c, err := ParseCommand(`:send hello\ world`)
	if err != nil {
		t.Fatal(err)
	}
	if len(c.Args) != 1 || !strings.Contains(c.Args[0], "hello world") {
		t.Errorf("args = %v", c.Args)
	}
}
