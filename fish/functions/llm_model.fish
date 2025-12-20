#
function llm_model
    set model $argv[1]
    set -e argv[1]

    if test -z "$model"
        echo "usage: llm_model <model> [prompt]" >&2
        return 1
    end

    if not isatty stdin
        set input (cat)
        ollama run $model -- "$input"
    else if test (count $argv) -gt 0
        ollama run $model -- "$argv"
    else
        ollama run $model
    end
end

