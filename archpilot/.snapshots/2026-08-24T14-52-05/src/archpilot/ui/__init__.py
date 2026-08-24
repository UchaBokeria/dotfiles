"""GTK4 frontend.

A plain GTK4 window rather than a layer-shell surface, on purpose:

* A normal window takes keyboard focus natively. The eww widget is a layer
  surface with on-demand keyboard interactivity, which no compositor command
  can focus - that is what made typing unreliable there.
* Every keystroke is ours, so vim editing is real (see archpilot.vim) instead
  of being approximated with compositor keybinds.
* GTK's ScrolledWindow has a scroll position we can set, so the transcript can
  actually follow the answer as it streams.

Hyprland floats, centres and pins it by window class - see
hypr/configs/archpilot.conf.
"""
