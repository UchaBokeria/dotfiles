#!/bin/bash
set -o pipefail
export PATH="$HOME/.opencode/bin:$PATH"
cd '/home/scriptkid/.config/.dotfiles/blackwall' || exit 97
opencode run --agent plan -m 'opencode-go/kimi-k3.1-pro' --interactive 'Follow the attached instructions.' -f '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/d3c6d52afa40/instructions.md' 2>&1 | tee -a '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/d3c6d52afa40/harness.log'
echo $? > '/home/scriptkid/.config/.dotfiles/blackwall/.sonata/runs/d3c6d52afa40/exit'
