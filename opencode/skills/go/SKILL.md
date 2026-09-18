---
name: go
description: Go development. Use when working with .go files, go.mod, builds, or Go tooling diagnostics.
---

# Go

- Toolchain at `/usr/bin/go`, extras in `~/go/bin` (`gopls`, `golangci-lint`,
  `gofumpt`, `goimports`, `richgo`, `mockgen`, `dlv`) — all on PATH.
- Diagnostics via the `gopls` LSP entry; prefer CLI feedback: `go vet ./...`,
  `gofmt -l .`, `golangci-lint run`, `go test ./...`.
- Never commit to `GOPATH`/module cache; respect `go.mod` toolchain lines.
