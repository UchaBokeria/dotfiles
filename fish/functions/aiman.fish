function aiman
    if test (count $argv) -lt 2
        echo "usage: aiman <tool> <question>"
        return 1
    end

    set tool $argv[1]
    set -e argv[1]
    set question (string join " " $argv)

    set content ""

    set pages (man -k "^$tool" 2>/dev/null \
        | head -n 3 \
        | sed -E 's/^([a-zA-Z0-9_.+-]+) *\(([0-9]+)\).*/\1 \2/')

    if test (count $pages) -eq 0
        if man -w "$tool" >/dev/null 2>&1
            set pages "$tool"
        else
            echo "No man page found for: $tool"
            return 1
        end
    end

    for p in $pages
        set name (echo $p | awk '{print $1}')
        set section (echo $p | awk '{print $2}')

        if test -n "$section"
            set content $content (man -P cat $section $name | col -b | head -n 400)
        else
            set content $content (man -P cat $name | col -b | head -n 400)
        end

        set content $content "\n-----\n"
    end

    ai "
You are answering a question about the UNIX tool: $tool

Question:
$question

Rules:
- Use ONLY the provided man page content
- Explain HOW to use the tool
- Show real commands and flags
- Do NOT invent behavior
- If the answer is missing, say:
  'Not documented in the man page.'

Man page content:
$content
"
end

