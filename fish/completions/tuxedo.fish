# Tuxedo 2026.8.1: no upstream completion generator in this release.
function __fish_tuxedo_ids
    command tuxedo ls --json 2>/dev/null | command python3 -c 'import json,sys; tasks=json.load(sys.stdin); [print(str(t["n"])+"\t"+t["raw"].replace("\t"," ").replace("\n"," ")[:100]) for t in tasks]' 2>/dev/null
end
function __fish_tuxedo_tags
    command tuxedo ls --json 2>/dev/null | command python3 -c 'import json,sys; tasks=json.load(sys.stdin); print("\n".join(sorted({"+"+p for t in tasks for p in t["projects"]}|{"@"+c for t in tasks for c in t["contexts"]})))' 2>/dev/null
end
complete -c tuxedo -f
complete -c tuxedo -s h -l help -d 'Show help'
complete -c tuxedo -s V -l version -d 'Show version'
complete -c tuxedo -s f -l force -d 'Skip confirmation prompts'
complete -c tuxedo -l json -d 'Machine-readable CLI output'
complete -c tuxedo -l sample -d 'Open the sample in the TUI'
complete -c tuxedo -n '__fish_use_subcommand' -F
complete -c tuxedo -n '__fish_use_subcommand' -a 'add a' -d 'Add task'
complete -c tuxedo -n '__fish_use_subcommand' -a 'append app' -d 'Append to task'
complete -c tuxedo -n '__fish_use_subcommand' -a 'prepend prep' -d 'Prepend to task'
complete -c tuxedo -n '__fish_use_subcommand' -a 'replace' -d 'Replace task'
complete -c tuxedo -n '__fish_use_subcommand' -a 'pri p' -d 'Set priority A-Z'
complete -c tuxedo -n '__fish_use_subcommand' -a 'depri dp' -d 'Remove priority'
complete -c tuxedo -n '__fish_use_subcommand' -a 'done do' -d 'Complete task'
complete -c tuxedo -n '__fish_use_subcommand' -a 'del rm' -d 'Delete task or term'
complete -c tuxedo -n '__fish_use_subcommand' -a 'archive' -d 'Archive completed tasks'
complete -c tuxedo -n '__fish_use_subcommand' -a 'list ls' -d 'List active tasks'
complete -c tuxedo -n '__fish_use_subcommand' -a 'listall lsa' -d 'List tasks and archive'
complete -c tuxedo -n '__fish_use_subcommand' -a 'listpri lsp' -d 'List prioritized tasks'
complete -c tuxedo -n '__fish_use_subcommand' -a 'listproj lsprj' -d 'List project tags'
complete -c tuxedo -n '__fish_use_subcommand' -a 'listcon lsc' -d 'List context tags'
complete -c tuxedo -n '__fish_use_subcommand' -a 'update' -d 'Show upgrade instructions'
complete -c tuxedo -n '__fish_seen_subcommand_from append app prepend prep replace depri dp done do del rm; or begin; __fish_seen_subcommand_from pri p; and test (count (commandline -opc)) -eq 2; end' -a '(__fish_tuxedo_ids)' -d 'Task number'
complete -c tuxedo -n '__fish_seen_subcommand_from pri p; and test (count (commandline -opc)) -eq 3' -a 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z' -d 'Priority'
complete -c tuxedo -n '__fish_seen_subcommand_from listpri lsp' -a 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z' -d 'Priority'
complete -c tuxedo -n '__fish_seen_subcommand_from list ls listall lsa add a append app prepend prep replace' -a '(__fish_tuxedo_tags)'
