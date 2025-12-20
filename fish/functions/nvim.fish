function nvim
    # Remove padding for this window
    kitty @ set-spacing padding=0 margin=0

    # Launch Neovim
    command nvim $argv

    # Restore padding after exit
    kitty @ set-spacing padding=10 margin=10
end
