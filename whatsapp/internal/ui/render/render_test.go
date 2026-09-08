package render

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/charmbracelet/lipgloss"
	"github.com/muesli/termenv"

	"github.com/UchaBokeria/blackwall/whatsapp/internal/domain"
	"github.com/UchaBokeria/blackwall/whatsapp/internal/theme"
)

var update = flag.Bool("update", false, "rewrite the golden files")

func TestMain(m *testing.M) {
	// Force a colourless profile so golden files hold layout, not escape
	// codes: a golden full of ANSI would fail on any machine with a different
	// terminal and tell us nothing about the layout we care about.
	lipgloss.SetColorProfile(termenv.Ascii)
	os.Exit(m.Run())
}

func plainStyles(t *testing.T) theme.Styles {
	t.Helper()
	p, err := theme.Load("")
	if err != nil {
		t.Fatal(err)
	}
	return theme.New(p, "rounded")
}

func ts(t *testing.T, hh, mm int) time.Time {
	t.Helper()
	return time.Date(2026, 9, 8, hh, mm, 0, 0, time.UTC)
}

func opts(t *testing.T, width int) Options {
	t.Helper()
	return Options{
		Width:     width,
		MaxBubble: width * 2 / 3,
		Timestamp: "15:04",
		Styles:    plainStyles(t),
		// Fixed, so "Today" and "Yesterday" do not change what a golden file
		// means when the clock rolls over midnight.
		Now: time.Date(2026, 9, 20, 12, 0, 0, 0, time.UTC),
	}
}

func TestWrapCountsDisplayWidth(t *testing.T) {
	got := Wrap("გამარჯობა მსოფლიო როგორ ხარ", 10)
	for _, line := range got {
		if VisibleWidth(line) > 10 {
			t.Errorf("line %q is %d cells wide, want at most 10", line, VisibleWidth(line))
		}
	}
	if len(got) < 2 {
		t.Errorf("expected wrapping, got %v", got)
	}
}

func TestWrapKeepsAGraphemeClusterIntact(t *testing.T) {
	// A skin-tone emoji is several runes. Splitting it leaves mojibake.
	got := Wrap("hello 👋🏽 world", 8)
	if !strings.Contains(strings.Join(got, ""), "👋🏽") {
		t.Errorf("the emoji was split: %q", got)
	}
}

func TestWrapBreaksALongUnbrokenToken(t *testing.T) {
	got := Wrap(strings.Repeat("x", 25), 10)
	if len(got) != 3 {
		t.Fatalf("got %d lines, want 3: %v", len(got), got)
	}
	for _, l := range got {
		if VisibleWidth(l) > 10 {
			t.Errorf("line %q exceeds the width", l)
		}
	}
}

func TestWrapPreservesExplicitNewlines(t *testing.T) {
	got := Wrap("one\ntwo", 20)
	if len(got) != 2 || got[0] != "one" || got[1] != "two" {
		t.Errorf("got %v", got)
	}
}

func TestWrapOfEmptyText(t *testing.T) {
	if got := Wrap("", 10); len(got) != 1 || got[0] != "" {
		t.Errorf("got %v, want one empty line", got)
	}
}

func TestTruncate(t *testing.T) {
	cases := []struct {
		in    string
		width int
		want  string
	}{
		{"hello", 10, "hello"},
		{"hello world", 8, "hello w…"},
		{"hello", 1, "…"},
		{"hello", 0, ""},
	}
	for _, c := range cases {
		if got := Truncate(c.in, c.width); got != c.want {
			t.Errorf("Truncate(%q, %d) = %q, want %q", c.in, c.width, got, c.want)
		}
	}
}

func TestTruncateNeverExceedsTheWidth(t *testing.T) {
	for _, s := range []string{"გამარჯობა მსოფლიო", "👋🏽👋🏽👋🏽👋🏽", strings.Repeat("漢", 20)} {
		for w := 1; w <= 12; w++ {
			if got := VisibleWidth(Truncate(s, w)); got > w {
				t.Errorf("Truncate(%q, %d) is %d cells wide", s, w, got)
			}
		}
	}
}

func TestBubbleNeverExceedsThePane(t *testing.T) {
	o := opts(t, 40)
	m := domain.Message{
		FromMe: true, Text: strings.Repeat("long ", 30), TS: ts(t, 14, 3),
		Delivery: domain.Read,
	}
	for _, l := range Bubble(m, o) {
		if VisibleWidth(l) > o.Width {
			t.Fatalf("line is %d cells wide in a %d-wide pane: %q",
				VisibleWidth(l), o.Width, l)
		}
	}
}

func TestBubbleFromMeIsRightAligned(t *testing.T) {
	o := opts(t, 40)
	lines := Bubble(domain.Message{
		FromMe: true, Text: "yes", TS: ts(t, 14, 3), Delivery: domain.Read,
	}, o)
	if !strings.HasPrefix(lines[0], " ") {
		t.Errorf("an own-message bubble should be padded on the left, got %q", lines[0])
	}
	last := lines[len(lines)-1]
	if !strings.Contains(last, "14:03") || !strings.Contains(last, "✓✓") {
		t.Errorf("footer = %q, want the time and read ticks", last)
	}
}

func TestBubbleFromThemIsLeftAligned(t *testing.T) {
	o := opts(t, 40)
	lines := Bubble(domain.Message{SenderName: "Nika", Text: "hi", TS: ts(t, 14, 2)}, o)
	for _, l := range lines {
		if strings.HasPrefix(l, "  ") {
			t.Errorf("their bubble should sit at the left edge, got %q", l)
		}
	}
}

func TestBubbleShowsTheSenderOnlyWhenAsked(t *testing.T) {
	o := opts(t, 40)
	m := domain.Message{SenderName: "Nika", Text: "hi", TS: ts(t, 14, 2)}

	if strings.Contains(strings.Join(Bubble(m, o), "\n"), "Nika") {
		t.Error("a direct message should not repeat the sender's name")
	}
	o.ShowSender = true
	if !strings.Contains(strings.Join(Bubble(m, o), "\n"), "Nika") {
		t.Error("a group message should name the sender")
	}
}

func TestBubbleRendersAQuotedReply(t *testing.T) {
	o := opts(t, 44)
	lines := Bubble(domain.Message{
		Text: "yes", QuotedID: "M1", QuotedText: "did you push?", TS: ts(t, 1, 1),
	}, o)
	body := strings.Join(lines, "\n")
	if !strings.Contains(body, "did you push?") {
		t.Errorf("the quote is missing:\n%s", body)
	}
	if !strings.Contains(body, quoteBar) {
		t.Errorf("the quote has no bar:\n%s", body)
	}
}

func TestBubbleMarksRevokedAndEdited(t *testing.T) {
	o := opts(t, 40)
	rev := strings.Join(Bubble(domain.Message{Revoked: true, TS: ts(t, 1, 1)}, o), "\n")
	if !strings.Contains(rev, "deleted") {
		t.Errorf("a revoked message must say so:\n%s", rev)
	}
	ed := strings.Join(Bubble(domain.Message{Text: "x", Edited: true, TS: ts(t, 1, 1)}, o), "\n")
	if !strings.Contains(ed, "edited") {
		t.Errorf("an edited message must say so:\n%s", ed)
	}
}

func TestBubbleShowsAMediaChip(t *testing.T) {
	o := opts(t, 44)
	m := domain.Message{
		TS: ts(t, 1, 1),
		Media: &domain.MediaRef{
			Type: "image", Filename: "screenshot.png", Length: 1258291,
		},
	}
	body := strings.Join(Bubble(m, o), "\n")
	if !strings.Contains(body, "screenshot.png") {
		t.Errorf("the filename is missing:\n%s", body)
	}
	if !strings.Contains(body, "1.2MB") {
		t.Errorf("the size is missing or wrong:\n%s", body)
	}
}

func TestBubbleDeliveryGlyphs(t *testing.T) {
	o := opts(t, 40)
	cases := []struct {
		state domain.DeliveryState
		want  string
	}{
		{domain.Pending, tickPending},
		{domain.Sent, tickSent},
		{domain.Delivered, tickDelivered},
		{domain.Read, tickRead},
		{domain.Failed, tickFailed},
	}
	for _, c := range cases {
		lines := Bubble(domain.Message{FromMe: true, Text: "x", TS: ts(t, 1, 1), Delivery: c.state}, o)
		last := lines[len(lines)-1]
		if !strings.Contains(last, c.want) {
			t.Errorf("delivery %v rendered %q, want %q", c.state, last, c.want)
		}
	}
}

func TestBubbleFromThemHasNoTicks(t *testing.T) {
	// Ticks describe our own message's journey; drawing them on a received
	// message would be meaningless.
	o := opts(t, 40)
	lines := Bubble(domain.Message{Text: "hi", TS: ts(t, 1, 1), Delivery: domain.Read}, o)
	if strings.Contains(strings.Join(lines, "\n"), tickRead) {
		t.Error("a received message should carry no delivery ticks")
	}
}

func TestBubbleLinesNeverOverflowForAnyContent(t *testing.T) {
	// The first golden run caught a media chip and a "deleted" placeholder
	// spilling past their own box, because only the message text was wrapped.
	long := strings.Repeat("filename-", 8) + ".png"
	cases := map[string]domain.Message{
		"long media chip": {TS: ts(t, 1, 1), Media: &domain.MediaRef{
			Type: "document", Filename: long, Length: 999999999}},
		"revoked":    {TS: ts(t, 1, 1), Revoked: true},
		"edited":     {TS: ts(t, 1, 1), Text: "x", Edited: true},
		"long quote": {TS: ts(t, 1, 1), Text: "ok", QuotedID: "1", QuotedText: strings.Repeat("quoted ", 20)},
		"cjk":        {TS: ts(t, 1, 1), Text: strings.Repeat("漢字", 40)},
		"emoji":      {TS: ts(t, 1, 1), Text: strings.Repeat("👋🏽", 30)},
	}
	for _, width := range []int{20, 32, 40, 80} {
		o := opts(t, width)
		o.ShowSender = true
		for name, m := range cases {
			for _, l := range Bubble(m, o) {
				if VisibleWidth(l) > width {
					t.Errorf("%s at width %d: line is %d cells: %q",
						name, width, VisibleWidth(l), l)
				}
			}
		}
	}
}

func TestBubbleInAVeryNarrowPane(t *testing.T) {
	o := opts(t, 6)
	lines := Bubble(domain.Message{Text: "hello there", TS: ts(t, 1, 1)}, o)
	if len(lines) == 0 {
		t.Fatal("no output")
	}
	for _, l := range lines {
		if VisibleWidth(l) > 6 {
			t.Errorf("line %q exceeds a 6-cell pane", l)
		}
	}
}

func TestStreamInsertsOneSeparatorPerDay(t *testing.T) {
	o := opts(t, 40)
	msgs := []domain.Message{
		{ID: "1", Text: "day one a", TS: time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)},
		{ID: "2", Text: "day one b", TS: time.Date(2026, 9, 6, 11, 0, 0, 0, time.UTC)},
		{ID: "3", Text: "day two", TS: time.Date(2026, 9, 7, 10, 0, 0, 0, time.UTC)},
	}
	lines := Stream(msgs, o, "Monday, 2 January 2006")

	seps := 0
	for _, l := range lines {
		if l.IsSeparator {
			seps++
		}
	}
	if seps != 2 {
		t.Errorf("separators = %d, want one per day", seps)
	}
}

func TestStreamMapsRowsBackToMessages(t *testing.T) {
	o := opts(t, 40)
	msgs := []domain.Message{
		{ID: "1", Text: "first", TS: ts(t, 10, 0)},
		{ID: "2", Text: "second", TS: ts(t, 10, 1)},
	}
	lines := Stream(msgs, o, "")

	if got := FirstRowOf(lines, 1); got < 0 {
		t.Fatal("the second message has no rows")
	}
	if FirstRowOf(lines, 0) >= FirstRowOf(lines, 1) {
		t.Error("messages are out of order in the stream")
	}
	if LastRowOf(lines, 0) < FirstRowOf(lines, 0) {
		t.Error("LastRowOf is before FirstRowOf")
	}
}

func TestDaySeparatorNamesTodayAndYesterday(t *testing.T) {
	o := opts(t, 40)
	o.Now = time.Now()
	if got := DaySeparator(time.Now(), o, ""); !strings.Contains(got, "Today") {
		t.Errorf("today's separator = %q", got)
	}
	if got := DaySeparator(time.Now().AddDate(0, 0, -1), o, ""); !strings.Contains(got, "Yesterday") {
		t.Errorf("yesterday's separator = %q", got)
	}
	old := time.Date(2020, 3, 1, 12, 0, 0, 0, time.UTC)
	if got := DaySeparator(old, o, ""); !strings.Contains(got, "2020") {
		t.Errorf("an old separator should carry the date, got %q", got)
	}
}

func TestDaySeparatorFitsTheWidth(t *testing.T) {
	for _, w := range []int{20, 40, 80} {
		o := opts(t, w)
		got := DaySeparator(time.Date(2026, 9, 8, 0, 0, 0, 0, time.UTC), o, "Monday, 2 January 2006")
		if VisibleWidth(got) > w {
			t.Errorf("width %d: separator is %d cells: %q", w, VisibleWidth(got), got)
		}
	}
}

func TestHumanSize(t *testing.T) {
	cases := []struct {
		in   int64
		want string
	}{
		{512, "512B"},
		{2048, "2.0KB"},
		{1258291, "1.2MB"},
	}
	for _, c := range cases {
		if got := humanSize(c.in); got != c.want {
			t.Errorf("humanSize(%d) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestCacheReusesARender(t *testing.T) {
	c := NewCache(64)
	o := opts(t, 40)
	m := domain.Message{ID: "M1", Text: "hello", TS: ts(t, 1, 1)}

	a := c.Bubble(m, o)
	b := c.Bubble(m, o)
	if &a[0] != &b[0] {
		t.Error("a repeated render at the same width should come from the cache")
	}
	if c.Len() != 1 {
		t.Errorf("cache holds %d entries, want 1", c.Len())
	}
}

func TestCacheKeysOnWidth(t *testing.T) {
	c := NewCache(64)
	m := domain.Message{ID: "M1", Text: "hello", TS: ts(t, 1, 1)}
	a := c.Bubble(m, opts(t, 40))
	wide := opts(t, 60)
	b := c.Bubble(m, wide)
	if len(a) > 0 && len(b) > 0 && &a[0] == &b[0] {
		t.Error("a different width reused a cached render")
	}
}

func TestCacheInvalidatesOnAChangedMessage(t *testing.T) {
	c := NewCache(64)
	o := opts(t, 40)
	m := domain.Message{ID: "M1", Text: "hello", TS: ts(t, 1, 1), FromMe: true, Delivery: domain.Sent}
	first := strings.Join(c.Bubble(m, o), "\n")

	m.Delivery = domain.Read
	second := strings.Join(c.Bubble(m, o), "\n")
	if first == second {
		t.Error("a receipt did not invalidate the cached render")
	}
}

func TestCacheEvictsTheOldest(t *testing.T) {
	c := NewCache(2)
	o := opts(t, 40)
	for i := 0; i < 5; i++ {
		c.Bubble(domain.Message{ID: fmt.Sprintf("M%d", i), Text: "x", TS: ts(t, 1, 1)}, o)
	}
	if c.Len() != 2 {
		t.Errorf("cache holds %d entries, want its limit of 2", c.Len())
	}
}

func TestGoldenStream(t *testing.T) {
	fixture := []domain.Message{
		{ID: "1", SenderName: "Nika", Text: "did you push the nuc branch?",
			TS: time.Date(2026, 9, 8, 14, 2, 0, 0, time.UTC)},
		{ID: "2", FromMe: true, Text: "yeah, just now", Delivery: domain.Read,
			QuotedID: "1", QuotedText: "did you push the nuc branch?",
			TS: time.Date(2026, 9, 8, 14, 3, 0, 0, time.UTC)},
		{ID: "3", SenderName: "Nika", TS: time.Date(2026, 9, 8, 14, 5, 0, 0, time.UTC),
			Media: &domain.MediaRef{Type: "image", Filename: "screenshot.png", Length: 1258291}},
		{ID: "4", FromMe: true, Text: "that is a very long message intended to exercise the wrapping logic at every width the golden files cover",
			Delivery: domain.Delivered, TS: time.Date(2026, 9, 8, 14, 6, 0, 0, time.UTC)},
		{ID: "5", SenderName: "Nika", Revoked: true,
			TS: time.Date(2026, 9, 8, 14, 7, 0, 0, time.UTC)},
	}

	for _, w := range []int{40, 80, 120} {
		t.Run(fmt.Sprintf("width%d", w), func(t *testing.T) {
			o := opts(t, w)
			o.ShowSender = true

			var b strings.Builder
			for _, l := range Stream(fixture, o, "Monday, 2 January 2006") {
				b.WriteString(l.Text)
				b.WriteString("\n")
			}
			got := b.String()

			golden := filepath.Join("testdata", fmt.Sprintf("stream-%d.golden", w))
			if *update {
				os.MkdirAll("testdata", 0o755)
				if err := os.WriteFile(golden, []byte(got), 0o644); err != nil {
					t.Fatal(err)
				}
			}
			want, err := os.ReadFile(golden)
			if err != nil {
				t.Fatalf("missing golden file; rerun with -update: %v", err)
			}
			if got != string(want) {
				t.Errorf("render drift at width %d\n--- got ---\n%s\n--- want ---\n%s", w, got, want)
			}
		})
	}
}
