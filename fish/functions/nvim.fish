function nvim
    set -l KTTY_TO "unix:@mykitty"

    # Remove padding (don’t block startup if kitty remote control fails)
    if command -q kitty
        kitty @ --to $KTTY_TO set-spacing padding=0 margin=0 2>/dev/null; or true
    end

    command nvim $argv

    # Restore padding
    if command -q kitty
        kitty @ --to $KTTY_TO set-spacing padding=10 margin=10 2>/dev/null; or true
    end
end
