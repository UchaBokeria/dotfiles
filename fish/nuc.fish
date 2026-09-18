# Per-machine fish bits. config.fish sources this if it exists, so a machine
# with different hardware or different local tools can add to the shell
# without the file that everyone shares having to know about it.
#
# `alias` and not `alias -s`: the -s form calls funcsave, which rewrote
# fish/functions/figma-linux.fish into this repo on EVERY shell start. The
# function is committed; saving it again on each startup only made git dirty.
alias figma-linux="figma-linux --disable-gpu"
