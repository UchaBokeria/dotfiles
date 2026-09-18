function __opencode_completions
    # Clear local variables to prevent bleed-through
    set -l tokens (commandline -opc)
    set -l current_token (commandline -ct)

    # If we are just starting, feed the base command
    if test (count $tokens) -le 1
        opencode --get-yargs-completions opencode
    else
        # Otherwise, pass all arguments up to the cursor
        opencode --get-yargs-completions $tokens[2..-1] $current_token
    end
end

# Clear built-in file completions and bind our function
complete -c opencode -f -a '(__opencode_completions)'

