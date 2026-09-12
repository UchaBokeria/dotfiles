# wa - a terminal WhatsApp client.
#
# CGO is off deliberately: every dependency is pure Go, so one `make build`
# produces a working binary on Arch and Ubuntu alike with no toolchain beyond
# Go itself.

BIN     := wa
PREFIX  ?= $(HOME)/.local
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)

GOFLAGS := -trimpath
LDFLAGS := -s -w -X main.version=$(VERSION)

.PHONY: build install uninstall test clean run

build:
	CGO_ENABLED=0 go build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(BIN) ./cmd/wa

# The reference config is installed as an example, never as a live config.
# Copying the whole file into place would freeze every default at install time:
# the binary carries the defaults, and an on-disk copy would shadow them
# forever, including the ones a later version improves.
install: build
	install -Dm755 $(BIN) $(PREFIX)/bin/$(BIN)
	install -Dm644 config.toml $(HOME)/.config/wa/config.toml.example
	@echo "installed $(PREFIX)/bin/$(BIN)"
	@echo "reference config: ~/.config/wa/config.toml.example"
	@echo "copy the lines you want into ~/.config/wa/config.toml"

uninstall:
	rm -f $(PREFIX)/bin/$(BIN)

test:
	./run-tests

run: build
	./$(BIN)

clean:
	rm -f $(BIN)
