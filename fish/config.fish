# =========================
# Interactive only
# =========================
if not status is-interactive
    exit
end


# =========================
# NVM (Node Version Manager)
# =========================
set -Ux NVM_DIR $HOME/.nvm

if test -s "$NVM_DIR/nvm.sh"
    bass source "$NVM_DIR/nvm.sh"
end


# =========================
# Bun
# =========================
set -Ux BUN_INSTALL $HOME/.bun
fish_add_path $BUN_INSTALL/bin


# =========================
# Aliases
# =========================
alias vim='nvim'
alias vi='nvim'

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
