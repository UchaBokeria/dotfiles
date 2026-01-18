function src --description 'Source .env file'
    set -l envfile .env
    if test (count $argv) -gt 0
        set envfile $argv[1]
    end
    
    for line in (cat $envfile | grep -v '^#' | grep -v '^$')
        set -l kv (string split -m 1 = $line)
        set -gx $kv[1] (string replace -ra '^["\']|["\']$' '' $kv[2])
    end
end
