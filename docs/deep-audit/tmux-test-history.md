# Nested tmux-test repository history

All71locally available reachable commits across allrefs are read as complete initial tree plus every patch, including sidebranches/mergefirst-parent changes. Five retained bounded review batches specify the full sequence. HEADc38f488 is2017, while an existing remote ref adds2019README cleanup; neither is inferred current upstream. No network fetch, setup, test or VM command was executed.

The framework was extracted from tpm/copycat for Vagrant/Travis isolation. Test helpers deliberately overwrite ~/.tmux.conf, delete ~/.tmux and kill the default tmuxserver, which explains why run_tests_in_isolation is unsafe on this owner desktop. Setup itself creates symlinks, edits .gitignore, replaces Travis config and its undo uses git checkout. A command called test/setup/undo is therefore not a passive check.

Evolution adds named Ubuntu/CentOS VM selection, a single-test route, keep-running and teardown helpers, then builds tmux2.0/2.5 rather than the1.9aPPA. The2015 self-submodule recursively referred to its own older commits; it was removed because recursive submodule initialization caused issues. Historical gitlinks point at ancestors already included in this full review, so they do not require an infinite repository traversal.

VM isolation is the intended upstream execution boundary. Current developer docs still mention the older KEEP_RUNNING environment method after the CLI resets that variable and adds --keep-running. Old provisioning downloads libevent over HTTP and installs tools globally; those commands remain vendor history, not a recommendation or owner preference. No present-day upstream support/compatibility or successful execution is claimed.

This closes this finite nested Git history only; global review convergence remains pending.
