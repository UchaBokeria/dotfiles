function aif
    if not isatty stdin
        cat | coder "analyze output and suggest next pentest steps"
    else
        coder "$argv"
    end
end
