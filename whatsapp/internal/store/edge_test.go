package store

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
)

func TestFTSQueryQuotesEverythingSyntaxLike(t *testing.T) {
	for _, in := range []string{`"`, `a"b`, `NEAR`, `-x`, `col:val`, `*`, `(`, `AND OR NOT`, `'`, `\`} {
		q := ftsQuery(in)
		if q == "" {
			t.Errorf("ftsQuery(%q) is empty", in)
		}
		if q[0] != '"' || q[len(q)-1] != '"' {
			t.Errorf("ftsQuery(%q) = %s is not quoted", in, q)
		}
	}
}

func TestReceiptLogSurvivesACorruptFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "receipts.json")
	os.WriteFile(path, []byte("{this is not json"), 0o600)
	l := OpenReceiptLog(path)
	if l.Len() != 0 {
		t.Errorf("a corrupt file loaded %d receipts", l.Len())
	}
	if !l.Record("A", domain.Read, 1) {
		t.Fatal("a corrupt file left the log unable to record")
	}
	if err := l.Save(); err != nil {
		t.Fatal(err)
	}
	if OpenReceiptLog(path).Len() != 1 {
		t.Error("saving over a corrupt file did not repair it")
	}
}

func TestANilReceiptLogIsHarmless(t *testing.T) {
	var l *ReceiptLog
	if l.Record("A", domain.Read, 1) || l.Len() != 0 || l.Save() != nil {
		t.Error("a nil log did something")
	}
	m := l.Apply(domain.Message{ID: "A", FromMe: true, Delivery: domain.Sent})
	if m.Delivery != domain.Sent {
		t.Error("a nil log changed a message")
	}
}

func TestReceiptsNeverDowngradeAFailedSend(t *testing.T) {
	l := OpenReceiptLog(filepath.Join(t.TempDir(), "r.json"))
	l.Record("A", domain.Read, 1)
	m := l.Apply(domain.Message{ID: "A", FromMe: true, Delivery: domain.Failed})
	if m.Delivery != domain.Failed {
		t.Errorf("a failed send was ticked as %v", m.Delivery)
	}
}

func TestArchiveDetection(t *testing.T) {
	yes := [][2]string{
		{"Milestone Dealers (1).zip", "application/x-zip-compressed"},
		{"BACKUP.TAR.GZ", ""},
		{"x.7z", ""},
		{"noext", "application/zip"},
		{"file", "application/x-rar-compressed"},
	}
	no := [][2]string{
		{"report.pdf", "application/pdf"},
		{"zipper.txt", "text/plain"},
		{"", ""},
	}
	for _, c := range yes {
		if !isArchive(c[0], c[1]) {
			t.Errorf("%q (%s) is an archive", c[0], c[1])
		}
	}
	for _, c := range no {
		if isArchive(c[0], c[1]) {
			t.Errorf("%q (%s) is not an archive", c[0], c[1])
		}
	}
}
