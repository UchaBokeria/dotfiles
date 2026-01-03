# =========================
# Interactive only
# =========================
if not status is-interactive
    if not set -q TMUX; and not set -q ZELLIJ
        echo
        echo "Choose multiplexer:"
        echo "1) tmux"
        echo "2) zellij"
        echo "3) none"
        read -P "> " choice

        switch $choice
            case 1
                tmux attach || tmux
            case 2
                zellij
            case '*'
                # do nothing
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








# opencode
fish_add_path /home/scriptkid/.opencode/bin

# bun
set --export BUN_INSTALL "$HOME/.bun"
set --export PATH $BUN_INSTALL/bin $PATH

fish_add_path /home/scriptkid/.spicetify
