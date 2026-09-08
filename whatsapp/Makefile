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

install: build
	install -Dm755 $(BIN) $(PREFIX)/bin/$(BIN)
	@mkdir -p $(HOME)/.config/wa
	@if [ ! -e $(HOME)/.config/wa/config.toml ]; then \
		install -Dm644 config.toml $(HOME)/.config/wa/config.toml; \
		echo "installed a starter config to ~/.config/wa/config.toml"; \
	else \
		echo "kept your existing ~/.config/wa/config.toml"; \
	fi
	@echo "installed $(PREFIX)/bin/$(BIN)"

uninstall:
	rm -f $(PREFIX)/bin/$(BIN)

test:
	./run-tests

run: build
	./$(BIN)

clean:
	rm -f $(BIN)
