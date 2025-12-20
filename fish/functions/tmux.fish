function tmux
    if set -q ZELLIJ
        echo "Already inside Zellij"
    else
        command tmux $argv
    end
end
