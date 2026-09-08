package wacli

import (
	"errors"
	"fmt"
	"strings"
)

// Sentinel failures the interface reacts to differently. Everything else
// arrives as a *Error carrying wacli's own message.
var (
	// ErrStoreLocked means another wacli holds the store lock and this command
	// is not one that can be delegated to it.
	ErrStoreLocked = errors.New("the wacli store is locked by another process")
	// ErrUnauthenticated means there is no linked WhatsApp session.
	ErrUnauthenticated = errors.New("wacli is not authenticated")
	// ErrTimeout means the invocation outlived its deadline.
	ErrTimeout = errors.New("wacli timed out")
	// ErrNotInstalled means the wacli binary could not be run at all.
	ErrNotInstalled = errors.New("wacli is not installed")
)

// AmbiguousError is returned when a recipient name matched several contacts.
// The candidates are carried so the interface can offer a choice instead of
// making the user retype a JID.
type AmbiguousError struct {
	Query      string
	Candidates []string
}

func (e *AmbiguousError) Error() string {
	return fmt.Sprintf("%q matches %d contacts: %s",
		e.Query, len(e.Candidates), strings.Join(e.Candidates, ", "))
}

// Error is any other wacli failure.
type Error struct {
	Args     []string
	ExitCode int
	Message  string
}

func (e *Error) Error() string {
	if e.Message == "" {
		return fmt.Sprintf("wacli %s: exit %d", strings.Join(e.Args, " "), e.ExitCode)
	}
	return fmt.Sprintf("wacli %s: %s", strings.Join(e.Args, " "), e.Message)
}

// classify turns wacli's prose into something the interface can branch on.
// wacli has no machine-readable error codes, so this matches on the message
// text; each pattern below was taken from an observed failure.
func classify(args []string, message, stderr string, code int) error {
	detail := strings.TrimSpace(message)
	if detail == "" {
		detail = strings.TrimSpace(stderr)
	}
	lower := strings.ToLower(detail)

	switch {
	case strings.Contains(lower, "executable file not found"),
		strings.Contains(lower, "no such file or directory") && strings.Contains(lower, "wacli"):
		return fmt.Errorf("%w: %s", ErrNotInstalled, detail)

	case strings.Contains(lower, "store is locked"), strings.Contains(lower, "store locked"):
		return fmt.Errorf("%w: %s", ErrStoreLocked, detail)

	case strings.Contains(lower, "not authenticated"),
		strings.Contains(lower, "no session"),
		strings.Contains(lower, "not logged in"):
		return fmt.Errorf("%w: %s", ErrUnauthenticated, detail)

	case strings.Contains(lower, "ambiguous"):
		return parseAmbiguous(detail)
	}

	return &Error{Args: args, ExitCode: code, Message: detail}
}

// parseAmbiguous pulls the candidate list out of a message shaped like
//
//	ambiguous recipient "nika": 2 matches: Nika A, Nika B
func parseAmbiguous(detail string) error {
	e := &AmbiguousError{}

	if open := strings.Index(detail, `"`); open >= 0 {
		if close := strings.Index(detail[open+1:], `"`); close >= 0 {
			e.Query = detail[open+1 : open+1+close]
		}
	}

	// The candidates follow the last colon.
	if colon := strings.LastIndex(detail, ":"); colon >= 0 && colon+1 < len(detail) {
		for _, part := range strings.Split(detail[colon+1:], ",") {
			if p := strings.TrimSpace(part); p != "" {
				e.Candidates = append(e.Candidates, p)
			}
		}
	}
	if len(e.Candidates) == 0 {
		// Shape we did not anticipate: keep the message rather than pretending
		// to have parsed it.
		return &Error{Message: detail}
	}
	return e
}
