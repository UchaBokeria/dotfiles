1: ---
2: name: go
3: description: Go development. Use when working with .go files, go.mod, builds, or Go tooling diagnostics.
4: ---
5: 
6: # Go
7: 
8: - Toolchain at `/usr/bin/go`, extras in `~/go/bin` (`gopls`, `golangci-lint`,
9:   `gofumpt`, `goimports`, `richgo`, `mockgen`, `dlv`) — all on PATH.
10: - Diagnostics via the `gopls` LSP entry; prefer CLI feedback: `go vet ./...`,
11:   `gofmt -l .`, `golangci-lint run`, `go test ./...`.
12: - Never commit to `GOPATH`/module cache; respect `go.mod` toolchain lines.
