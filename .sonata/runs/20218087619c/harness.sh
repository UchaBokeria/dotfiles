#!/bin/bash
set -o pipefail
export PATH="$HOME/.opencode/bin:$PATH"
cd '/home/scriptkid/.config/.dotfiles/blackwall' || exit 97
opencode run --agent plan -m 'opencode-go/minimax-m3.1-flash' --interactive 'Follow the attached instructions.' -f '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/20218087619c/instructions.md' 2>&1 | tee -a '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/20218087619c/harness.log'
echo $? > '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/20218087619c/exit'
