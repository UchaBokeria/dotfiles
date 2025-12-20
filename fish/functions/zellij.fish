function zellij
    if set -q TMUX
        echo "Already inside tmux"
    else
        command zellij $argv
    end
end
