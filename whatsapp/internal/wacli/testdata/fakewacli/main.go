// Command fakewacli stands in for the real wacli during tests.
//
// It answers from a script file named by WA_FAKE_SCRIPT: a JSON object mapping
// a joined argument string to the response to give. The key "*" matches
// anything not matched exactly, and a key ending in "..." matches by prefix.
//
//	{
//	  "doctor --json": {"stdout": "{\"success\":true,...}", "exit": 0},
//	  "*":             {"stderr": "boom", "exit": 1}
//	}
//
// Every invocation is appended to WA_FAKE_LOG as a "start" line and an "end"
// line, so a test can assert both on the arguments passed and on whether two
// calls overlapped.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"
)

type response struct {
	Stdout  string `json:"stdout"`
	Stderr  string `json:"stderr"`
	Exit    int    `json:"exit"`
	DelayMS int    `json:"delay_ms"`
}

// logMu serialises appends within one process; separate processes rely on the
// O_APPEND write of a single short line being atomic on Linux.
var logMu sync.Mutex

func logLine(path, format string, args ...any) {
	if path == "" {
		return
	}
	logMu.Lock()
	defer logMu.Unlock()
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	defer f.Close()
	fmt.Fprintf(f, format+"\n", args...)
}

func main() {
	args := strings.Join(os.Args[1:], " ")
	logPath := os.Getenv("WA_FAKE_LOG")
	logLine(logPath, "start %s", args)

	// os.Exit skips deferred calls, so every exit path goes through this.
	done := func(code int) {
		logLine(logPath, "end %s", args)
		os.Exit(code)
	}

	scriptPath := os.Getenv("WA_FAKE_SCRIPT")
	if scriptPath == "" {
		fmt.Fprintln(os.Stderr, "fakewacli: WA_FAKE_SCRIPT is not set")
		done(97)
	}
	body, err := os.ReadFile(scriptPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "fakewacli: %v\n", err)
		done(97)
	}
	var script map[string]response
	if err := json.Unmarshal(body, &script); err != nil {
		fmt.Fprintf(os.Stderr, "fakewacli: bad script: %v\n", err)
		done(97)
	}

	r, ok := lookup(script, args)
	if !ok {
		fmt.Fprintf(os.Stderr, "fakewacli: no scripted response for %q\n", args)
		done(98)
	}
	if r.DelayMS > 0 {
		time.Sleep(time.Duration(r.DelayMS) * time.Millisecond)
	}
	if r.Stdout != "" {
		fmt.Fprint(os.Stdout, r.Stdout)
	}
	if r.Stderr != "" {
		fmt.Fprint(os.Stderr, r.Stderr)
	}
	done(r.Exit)
}

func lookup(script map[string]response, args string) (response, bool) {
	if r, ok := script[args]; ok {
		return r, true
	}
	for k, r := range script {
		if strings.HasSuffix(k, "...") && strings.HasPrefix(args, strings.TrimSuffix(k, "...")) {
			return r, true
		}
	}
	r, ok := script["*"]
	return r, ok
}
