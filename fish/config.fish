# =========================
# Interactive only
# =========================
if status is-interactive
    if not set -q TMUX
        if not set -q START_TMUX
	    tmux has-session -t default 2>/dev/null \
		|| tmux new-session -d -s default

	    tmux attach -t default
	end
    end
end

# =========================
# Bun
# =========================
set -Ux BUN_INSTALL $HOME/.bun
fish_add_path $BUN_INSTALL/bin

set --universal nvm_default_version latest
set -U fish_user_paths /usr/local/bin $fish_user_paths

set -Ux ELECTRON_OZONE_PLATFORM_HINT x11 

# =========================
# Aliases
# =========================

alias ls='eza --icons -X --color --hyperlink -@ -Z --git -a'
alias ll='eza --icons -X --color --hyperlink -@ -Z --git -a -l'
alias grep='grep --color=auto'


# =========================
# Prompt (fish-native)
# =========================
function fish_prompt
    set_color cyan
    printf '[%s@%s %s]$ ' (whoami) (hostname -s) (prompt_pwd)
    set_color normal
end

fish_vi_key_bindings
set -U EDITOR nvim

zoxide init fish | source
starship init fish | source







# Go
fish_add_path "$HOME/go/bin"

# opencode
fish_add_path "$HOME/.opencode/bin"

# bun
set --export BUN_INSTALL "$HOME/.bun"
set --export PATH $BUN_INSTALL/bin $PATH

fish_add_path "$HOME/.spicetify"
export PATH="$HOME/.local/bin:$PATH"

set -x QT_QPA_PLATFORM wayland
fish_add_path "$HOME/.platformio/penv/bin"

