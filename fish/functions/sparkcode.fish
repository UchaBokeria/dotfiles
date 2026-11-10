function sparkcode --description 'Run Claude Code using Meta Spark with Reasoning control' --wraps claude
    # 1. Verification Safety Check: Alert if the variable is blank or unexported
    set -gx MODEL_API_KEY_UCHABOKERIA LLM_2159816524957487_RaDKJs7h0EbPntObbshfz4kmCp0
    if not set -q MODEL_API_KEY_UCHAPRIMARY; or test -z "$MODEL_API_KEY_UCHAPRIMARY"
        echo (set_color red)"Error: \$MODEL_API_KEY_UCHAPRIMARY is empty or not exported."(set_color normal)
        echo "Please run: set -gx MODEL_API_KEY_UCHAPRIMARY \"your_meta_key_here\""
        return 1
    end

    # 2. Setup standard reasoning effort
    set -l effort "xhigh"

    # 3. Fire Claude inside an isolated environment block
    # Note: ANTHROPIC_BASE_URL has no trailing /v1
    env -u ANTHROPIC_API_KEY \
        -u ANTHROPIC_AUTH_TOKEN \
        ANTHROPIC_BASE_URL="https://api.meta.ai" \
        ANTHROPIC_AUTH_TOKEN="$MODEL_API_KEY_UCHAPRIMARY" \
        ANTHROPIC_MODEL="muse-spark-1.3-contributor" \
        ANTHROPIC_DEFAULT_OPUS_MODEL="muse-spark-1.3-contributor" \
        ANTHROPIC_DEFAULT_SONNET_MODEL="muse-spark-1.3-contributor" \
        ANTHROPIC_DEFAULT_HAIKU_MODEL="muse-spark-1.3-contributor" \
        CLAUDE_CODE_SUBAGENT_MODEL="muse-spark-1.3-contributor" \
        ENABLE_TOOL_SEARCH="true" \
        REASONING_EFFORT="$effort" \
        claude $argv
end
