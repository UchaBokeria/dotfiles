function aiman
    if test (count $argv) -eq 0
        echo "usage: aiman <query>"
        return 1
    end

    set query (string join " " $argv)

    # Try to find pages via man -k (apropos)
    set pages (man -k "$query" 2>/dev/null \
        | head -n 3 \
        | sed -E 's/^([a-zA-Z0-9_.+-]+)\s*\(.*/\1/')

    # Fallback: try direct man page
    if test (count $pages) -eq 0
        if man -w "$query" >/dev/null 2>&1
            set pages $query
        else
            echo "No man page found for: $query"
            return 1
        end
    end

    for p in $pages
        man $p | col -b | head -n 400
        echo "\n-----\n"
    end | ai "Answer using ONLY the information from the provided man pages. If the answer is not present, say so."
end

