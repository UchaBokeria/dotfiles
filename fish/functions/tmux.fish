function tmux
    if set -q ZELLIJ
        echo "Already inside Zellij"
    else
	# If you run plain `tmux`, go to (or create) the "default" session
	if test (count $argv) -eq 0
		command tmux new-session -A -s default
		return
	end

	# Otherwise pass through (so `tmux new -s foo`, `tmux ls`, etc. behave normally)
	command tmux $argv
    end
end
