// Package media turns an attachment into something a terminal can show.
//
// The obvious approach - kitty's graphics protocol - is not the one taken
// here. It produces a real image, but only where the terminal supports it, and
// inside tmux only when `allow-passthrough` is on, which it is not by default.
// A preview that works on the author's machine and nowhere else is not a
// preview.
//
// Instead images are drawn with half-block characters: one cell carries two
// pixels, the upper as the foreground colour and the lower as the background.
// That needs nothing but 24-bit colour, so it works in kitty, in tmux, over
// ssh, and in the golden-file tests. Full-quality viewing is a keystroke away
// through the desktop's own viewer.
package media

import (
	"fmt"
	"path/filepath"
	"strings"
)

// Kind is what an attachment is, for deciding how to show it.
type Kind int

const (
	KindUnknown Kind = iota
	KindImage
	KindVideo
	KindAudio
	KindVoice
	KindDocument
	KindSticker
	KindGIF
)

func (k Kind) String() string {
	switch k {
	case KindImage:
		return "image"
	case KindVideo:
		return "video"
	case KindAudio:
		return "audio"
	case KindVoice:
		return "voice note"
	case KindDocument:
		return "document"
	case KindSticker:
		return "sticker"
	case KindGIF:
		return "gif"
	}
	return "file"
}

// Icon is the glyph shown beside the name.
func (k Kind) Icon() string {
	switch k {
	case KindImage:
		return "🖼"
	case KindVideo:
		return "🎬"
	case KindAudio:
		return "🎵"
	case KindVoice:
		return "🎙"
	case KindDocument:
		return "📄"
	case KindSticker:
		return "🏷"
	case KindGIF:
		return "🎞"
	}
	return "📎"
}

// Classify works out what an attachment is.
//
// wacli's media_type is the first authority, but it is coarse: a WhatsApp GIF
// arrives as media_type "gif" with mime "video/mp4", and a document can be a
// PNG somebody attached as a file. The mime type settles those.
func Classify(mediaType, mime, filename string) Kind {
	mime = strings.ToLower(mime)
	ext := strings.ToLower(filepath.Ext(filename))

	switch strings.ToLower(mediaType) {
	case "image":
		return KindImage
	case "sticker":
		return KindSticker
	case "gif":
		return KindGIF
	case "video":
		return KindVideo
	case "audio":
		// WhatsApp voice notes are ogg/opus; music sent as a file is not.
		if strings.Contains(mime, "opus") || strings.Contains(mime, "ogg") {
			return KindVoice
		}
		return KindAudio
	case "document":
		// A document is whatever was attached, including an image.
		switch {
		case strings.HasPrefix(mime, "image/"):
			return KindImage
		case strings.HasPrefix(mime, "video/"):
			return KindVideo
		case strings.HasPrefix(mime, "audio/"):
			return KindAudio
		}
		return KindDocument
	}

	switch {
	case strings.HasPrefix(mime, "image/"):
		return KindImage
	case strings.HasPrefix(mime, "video/"):
		return KindVideo
	case strings.HasPrefix(mime, "audio/"):
		return KindAudio
	}
	switch ext {
	case ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp":
		return KindImage
	case ".mp4", ".mkv", ".mov", ".webm":
		return KindVideo
	case ".ogg", ".opus", ".mp3", ".m4a", ".wav", ".flac":
		return KindAudio
	case ".pdf", ".txt", ".md", ".doc", ".docx", ".odt", ".zip", ".json":
		return KindDocument
	}
	return KindUnknown
}

// Previewable reports whether a kind can be shown inline at all.
func (k Kind) Previewable() bool {
	switch k {
	case KindImage, KindSticker, KindGIF, KindVideo, KindDocument,
		KindAudio, KindVoice:
		// Audio has no picture, but it has a waveform, which is the
		// difference between a voice note and every other voice note.
		return true
	}
	return false
}

// HumanSize formats a byte count the way a file manager would.
func HumanSize(n int64) string {
	const unit = 1024
	if n < unit {
		return fmt.Sprintf("%dB", n)
	}
	div, exp := int64(unit), 0
	for v := n / unit; v >= unit; v /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f%cB", float64(n)/float64(div), "KMGT"[exp])
}

// HumanDuration formats a media length as m:ss.
func HumanDuration(seconds float64) string {
	if seconds <= 0 {
		return ""
	}
	total := int(seconds + 0.5)
	if h := total / 3600; h > 0 {
		return fmt.Sprintf("%d:%02d:%02d", h, (total%3600)/60, total%60)
	}
	return fmt.Sprintf("%d:%02d", total/60, total%60)
}
