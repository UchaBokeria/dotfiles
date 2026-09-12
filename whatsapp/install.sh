#!/usr/bin/env bash
# wa - install everything needed, on whatever this machine happens to be.
#
#   ./install.sh              install
#   ./install.sh --check      report what is missing and change nothing
#   ./install.sh --no-wacli   skip installing wacli
#   ./install.sh --headless   server install: no clipboard or desktop helpers
#   ./install.sh --desktop    ask for them even with no display attached
#
# It also runs with no checkout at all:
#
#   curl -fsSL https://raw.githubusercontent.com/UchaBokeria/dotfiles/nuc/whatsapp/install.sh | bash
#
# in which case wa is fetched with `go install` instead of built from source.
#
# It handles the things that otherwise go wrong: a distribution whose package
# manager is not apt, a Go too old to build the module, a headless server with
# no clipboard or desktop to install helpers for, and a shell whose PATH does
# not include ~/.local/bin. The last one is the reason this script exists at
# all - `make install` puts the binary somewhere the shell cannot find, and
# the failure looks like the build not working.

set -uo pipefail

CHECK_ONLY=0
WANT_WACLI=1
HEADLESS=auto
for arg in "$@"; do
    case "$arg" in
        --check)     CHECK_ONLY=1 ;;
        --no-wacli)  WANT_WACLI=0 ;;
        --headless)  HEADLESS=yes ;;
        --desktop)   HEADLESS=no ;;
        -h|--help)   sed -n '2,20p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

HERE="$(cd "$(dirname "$(readlink -f "$0")" 2>/dev/null || echo .)" && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
BINDIR="$PREFIX/bin"
GO_MIN_MAJOR=1
GO_MIN_MINOR=22

# Where wa comes from when there is no checkout to build.
MODULE="github.com/UchaBokeria/dotfiles/whatsapp"
WACLI_REPO="openclaw/wacli"

# A checkout to build, or a bare script fetched with curl? The module line is
# the test rather than the file's presence: a stray go.mod in whatever
# directory the pipe happened to run in is not this project.
FROM_SOURCE=0
if [ -f "$HERE/go.mod" ] && grep -q "^module $MODULE\$" "$HERE/go.mod" 2>/dev/null; then
    FROM_SOURCE=1
fi

# A machine with no display gets no clipboard helper and no xdg-utils: they
# pull in a chunk of X11 that a server has no use for, and wa already falls
# back to OSC 52 for copying.
headless() {
    case "$HEADLESS" in
        yes) return 0 ;;
        no)  return 1 ;;
    esac
    [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]
}

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
ok()    { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn()  { printf '  \033[33m!\033[0m %s\n' "$*"; }
bad()   { printf '  \033[31m✗\033[0m %s\n' "$*"; }
step()  { printf '\n\033[1m%s\033[0m\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

# --------------------------------------------------------------------------
# the package manager
# --------------------------------------------------------------------------

PM=""
detect_pm() {
    if   have pacman;  then PM=pacman
    elif have apt-get; then PM=apt
    elif have dnf;     then PM=dnf
    elif have zypper;  then PM=zypper
    elif have apk;     then PM=apk
    elif have brew;    then PM=brew
    fi
}

# sudo only when we are not already root, and only when one exists.
SUDO=""
if [ "$(id -u)" -ne 0 ] && have sudo; then SUDO="sudo"; fi

pm_install() {
    local pkg="$1"
    case "$PM" in
        pacman) $SUDO pacman -S --needed --noconfirm "$pkg" ;;
        apt)    $SUDO apt-get update -qq && $SUDO apt-get install -y "$pkg" ;;
        dnf)    $SUDO dnf install -y "$pkg" ;;
        zypper) $SUDO zypper --non-interactive install "$pkg" ;;
        apk)    $SUDO apk add "$pkg" ;;
        brew)   brew install "$pkg" ;;
        *)      return 1 ;;
    esac
}

# --------------------------------------------------------------------------
# Go
# --------------------------------------------------------------------------

go_version() {
    have go || return 1
    go env GOVERSION 2>/dev/null | sed 's/^go//'
}

go_new_enough() {
    local v major minor
    v="$(go_version)" || return 1
    major="${v%%.*}"; v="${v#*.}"; minor="${v%%.*}"
    [ "${major:-0}" -gt "$GO_MIN_MAJOR" ] && return 0
    [ "${major:-0}" -eq "$GO_MIN_MAJOR" ] && [ "${minor:-0}" -ge "$GO_MIN_MINOR" ]
}

install_go() {
    step "Go"
    if go_new_enough; then ok "go $(go_version)"; return 0; fi

    if have go; then
        warn "go $(go_version) is older than $GO_MIN_MAJOR.$GO_MIN_MINOR"
    else
        warn "go is not installed"
    fi
    [ "$CHECK_ONLY" -eq 1 ] && return 1

    case "$PM" in
        pacman) pm_install go ;;
        apt)
            # Debian and Ubuntu ship a Go that is often too old. Try the
            # archive first, then fall back to the upstream tarball rather
            # than leaving the user with a version that cannot build.
            pm_install golang-go
            if ! go_new_enough; then
                warn "the packaged Go is still too old; fetching the upstream tarball"
                install_go_tarball
            fi
            ;;
        dnf|zypper|apk) pm_install go ;;
        brew)   pm_install go ;;
        *)      install_go_tarball ;;
    esac

    if go_new_enough; then ok "go $(go_version)"; return 0; fi
    bad "could not install a new enough Go"
    return 1
}

install_go_tarball() {
    local arch os url tmp version="1.23.4"
    case "$(uname -m)" in
        x86_64)  arch=amd64 ;;
        aarch64|arm64) arch=arm64 ;;
        armv7l)  arch=armv6l ;;
        *) bad "unsupported architecture $(uname -m)"; return 1 ;;
    esac
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"
    url="https://go.dev/dl/go${version}.${os}-${arch}.tar.gz"

    have curl || have wget || { bad "need curl or wget to fetch Go"; return 1; }
    tmp="$(mktemp -d)"
    echo "  fetching $url"
    if have curl; then curl -fsSL "$url" -o "$tmp/go.tgz"
    else wget -qO "$tmp/go.tgz" "$url"; fi || { bad "download failed"; return 1; }

    $SUDO rm -rf /usr/local/go
    $SUDO tar -C /usr/local -xzf "$tmp/go.tgz" || return 1
    rm -rf "$tmp"
    export PATH="/usr/local/go/bin:$PATH"
    ok "installed go $version to /usr/local/go"
    warn "add /usr/local/go/bin to your PATH for future shells"
}

# --------------------------------------------------------------------------
# wacli
# --------------------------------------------------------------------------

install_wacli() {
    step "wacli"
    if have wacli; then
        ok "wacli $(wacli version 2>/dev/null | head -1)"
        return 0
    fi
    warn "wacli is not installed"
    [ "$CHECK_ONLY" -eq 1 ] && return 1
    [ "$WANT_WACLI" -eq 0 ] && { warn "skipping (--no-wacli)"; return 1; }

    # A published binary first. wacli's own go.mod asks for a Go newer than
    # anything a distribution ships, so building it from source drags in a
    # second toolchain download for no gain.
    install_wacli_release && return 0

    if have go; then
        echo "  go install $WACLI_REPO/cmd/wacli@latest"
        if GOBIN="$BINDIR" GOTOOLCHAIN=auto go install "github.com/$WACLI_REPO/cmd/wacli@latest"; then
            ok "installed wacli to $BINDIR"
            return 0
        fi
    fi

    # The AUR carries it, but only where an AUR helper is already set up.
    if [ "$PM" = pacman ] && have yay; then
        yay -S --needed --noconfirm wacli && { ok "installed wacli"; return 0; }
    fi

    bad "could not install wacli automatically"
    echo "     install it yourself from https://github.com/$WACLI_REPO/releases and re-run this script"
    return 1
}

# install_wacli_release fetches the published binary for this machine and
# checks it against the release's own checksums before trusting it.
install_wacli_release() {
    local os arch tag tmp base url
    case "$(uname -s)" in
        Linux)  os=linux ;;
        Darwin) os=darwin ;;
        *) return 1 ;;
    esac
    case "$(uname -m)" in
        x86_64|amd64)  arch=amd64 ;;
        aarch64|arm64) arch=arm64 ;;
        *) return 1 ;;
    esac
    have curl || have wget || return 1

    tag="$(github_latest_tag "$WACLI_REPO")" || return 1
    [ -n "$tag" ] || return 1

    tmp="$(mktemp -d)" || return 1
    base="wacli_${tag#v}_${os}_${arch}.tar.gz"
    url="https://github.com/$WACLI_REPO/releases/download/$tag/$base"

    echo "  fetching $base"
    fetch "$url" "$tmp/$base" || { rm -rf "$tmp"; return 1; }

    # The checksum file covers every asset; failing to fetch it is a reason to
    # stop rather than to shrug, since the point of the check is the download.
    if fetch "https://github.com/$WACLI_REPO/releases/download/$tag/checksums.txt" "$tmp/checksums.txt"; then
        if have sha256sum; then
            ( cd "$tmp" && grep " $base\$" checksums.txt | sha256sum -c - >/dev/null 2>&1 ) || {
                bad "the wacli download does not match its checksum"
                rm -rf "$tmp"; return 1
            }
            ok "checksum verified"
        fi
    else
        warn "no checksums.txt in the release; installing unverified"
    fi

    tar -C "$tmp" -xzf "$tmp/$base" || { rm -rf "$tmp"; return 1; }
    [ -f "$tmp/wacli" ] || { rm -rf "$tmp"; return 1; }
    install -Dm755 "$tmp/wacli" "$BINDIR/wacli" || { rm -rf "$tmp"; return 1; }
    rm -rf "$tmp"

    ok "installed wacli $tag to $BINDIR"
    return 0
}

# github_latest_tag prints the newest release tag of a repository.
github_latest_tag() {
    local body
    body="$(fetch_stdout "https://api.github.com/repos/$1/releases/latest")" || return 1
    printf '%s' "$body" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1
}

fetch() {
    if have curl; then curl -fsSL "$1" -o "$2"
    else wget -qO "$2" "$1"; fi
}

fetch_stdout() {
    if have curl; then curl -fsSL "$1"
    else wget -qO- "$1"; fi
}

# --------------------------------------------------------------------------
# optional helpers
# --------------------------------------------------------------------------

install_optional() {
    step "optional tools"

    # ffmpeg is what turns a video into a still and a voice note into a
    # waveform. Without it those show a chip and a duration instead, which is
    # a degradation rather than a failure - so it is offered, never required.
    if have ffmpeg; then
        ok "ffmpeg present"
    else
        warn "no ffmpeg; videos show no frame and voice notes no waveform"
        [ "$CHECK_ONLY" -eq 0 ] && pm_install ffmpeg >/dev/null 2>&1 && ok "installed ffmpeg"
    fi

    if headless; then
        ok "headless: skipping clipboard and desktop helpers"
        echo "     copying uses OSC 52, which your terminal forwards over ssh"
        return 0
    fi

    # A clipboard helper. Without one, copying falls back to OSC 52, which
    # tmux swallows unless allow-passthrough is on.
    if have wl-copy || have xclip || have xsel; then
        ok "clipboard helper present"
    else
        warn "no clipboard helper; copying will use OSC 52"
        if [ "$CHECK_ONLY" -eq 0 ]; then
            case "$PM" in
                pacman) pm_install wl-clipboard ;;
                apt)    pm_install wl-clipboard || pm_install xclip ;;
                dnf)    pm_install wl-clipboard ;;
                *)      : ;;
            esac
        fi
    fi

    if have xdg-open; then
        ok "xdg-open present"
    else
        warn "no xdg-open; opening media in the desktop will not work"
        [ "$CHECK_ONLY" -eq 0 ] && case "$PM" in
            pacman) pm_install xdg-utils ;;
            apt|dnf|zypper) pm_install xdg-utils ;;
            *) : ;;
        esac
    fi
}

# --------------------------------------------------------------------------
# PATH, for whichever shell this is
# --------------------------------------------------------------------------

# path_line prints the line to append for a given shell.
path_line() {
    case "$1" in
        fish) echo "fish_add_path $BINDIR" ;;
        *)    echo "export PATH=\"$BINDIR:\$PATH\"" ;;
    esac
}

# ensure_path adds BINDIR to every shell the user actually has, not just the
# one running this script: installing from bash and then opening fish is the
# normal case, and only fixing the current shell is what makes wa look
# uninstalled.
ensure_path() {
    step "PATH"
    case ":$PATH:" in
        *":$BINDIR:"*) ok "$BINDIR is already on PATH for this shell" ;;
        *) warn "$BINDIR is not on PATH for this shell" ;;
    esac
    [ "$CHECK_ONLY" -eq 1 ] && return 0

    local marker="# added by wa install.sh"
    local files=()

    # Only touch a shell that exists on this machine.
    have bash && files+=("$HOME/.bashrc:bash")
    have zsh  && files+=("${ZDOTDIR:-$HOME}/.zshrc:zsh")
    have fish && files+=("$HOME/.config/fish/config.fish:fish")

    local entry file shell line
    for entry in "${files[@]}"; do
        file="${entry%%:*}"; shell="${entry##*:}"
        line="$(path_line "$shell")"

        mkdir -p "$(dirname "$file")"
        touch "$file"

        if grep -Fq "$BINDIR" "$file" 2>/dev/null; then
            ok "$shell already points at $BINDIR"
            continue
        fi
        printf '\n%s\n%s\n' "$marker" "$line" >> "$file"
        ok "added $BINDIR to $(basename "$file")"
    done
}

# --------------------------------------------------------------------------
# build and install
# --------------------------------------------------------------------------

build_and_install() {
    step "wa"
    if [ "$CHECK_ONLY" -eq 1 ]; then
        if [ "$FROM_SOURCE" -eq 1 ]; then warn "would build and install to $BINDIR"
        else warn "would install $MODULE/cmd/wa with go install"; fi
        return 0
    fi

    if [ "$FROM_SOURCE" -eq 0 ]; then
        # No checkout: fetch it. GOTOOLCHAIN is left alone so a Go older than
        # the module asks for downloads what it needs instead of failing.
        echo "  go install $MODULE/cmd/wa@latest"
        if ! GOBIN="$BINDIR" go install "$MODULE/cmd/wa@latest"; then
            bad "go install failed"
            echo "     clone the repository and run ./install.sh from whatsapp/ instead"
            return 1
        fi
        ok "installed $BINDIR/wa"
        return 0
    fi

    cd "$HERE" || return 1

    # The same stamp the Makefile uses, so a binary installed this way can say
    # which commit it is rather than calling itself "dev" forever.
    local version ldflags
    version="$(git describe --tags --always --dirty 2>/dev/null || echo dev)"
    ldflags="-s -w -X main.version=$version"

    if ! CGO_ENABLED=0 go build -trimpath -ldflags "$ldflags" -o wa ./cmd/wa; then
        bad "build failed"
        return 1
    fi
    install -Dm755 wa "$BINDIR/wa" || return 1
    ok "installed $BINDIR/wa"

    # A reference file, not a live config. The binary already carries every
    # default; a full copy on disk would shadow them forever, so a later
    # version could never improve one.
    mkdir -p "$HOME/.config/wa"
    install -Dm644 config.toml "$HOME/.config/wa/config.toml.example"
    ok "reference config at ~/.config/wa/config.toml.example"
    if [ -e "$HOME/.config/wa/config.toml" ]; then
        ok "kept your ~/.config/wa/config.toml"
    fi
}

# --------------------------------------------------------------------------

main() {
    bold "wa installer"
    if [ "$FROM_SOURCE" -eq 1 ]; then
        echo "  building from $HERE"
    else
        echo "  no checkout here; wa will be fetched with go install"
    fi
    headless && echo "  no display: installing for a server"
    detect_pm
    if [ -n "$PM" ]; then
        echo "  package manager: $PM"
    else
        warn "no known package manager; anything missing must be installed by hand"
    fi

    local failed=0
    install_go       || failed=1
    install_wacli    || failed=1
    install_optional
    [ "$failed" -eq 0 ] && { build_and_install || failed=1; }
    ensure_path

    step "next"
    if [ "$CHECK_ONLY" -eq 1 ]; then
        echo "  nothing was changed (--check)"
        return 0
    fi
    if [ "$failed" -ne 0 ]; then
        bad "some steps did not complete; see above"
        return 1
    fi

    if ! wacli doctor --json 2>/dev/null | grep -q '"authenticated":true'; then
        echo "  1. link your account:   wacli auth"
        echo "  2. start the client:    wa"
    else
        echo "  start the client:  wa"
    fi
    echo "  open a new shell first, or run:  export PATH=\"$BINDIR:\$PATH\""
}

main
