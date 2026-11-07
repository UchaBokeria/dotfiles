"""Live tmux theme colours shared by every workspace picker view."""
import curses
import re
from workspaces import tm
from picker_preview import colour256

ACCENT = BORDER = BODY = MUTED = SELECTION = BADGE = EDGE = TEXT = 0
_signature = None
_next_check = 0
_pane = ""


def colour(value, default=-1):
    value = value.strip().lower()
    if value in ('default', 'terminal', ''): return default
    if re.fullmatch(r'#[0-9a-f]{6}', value):
        return colour256(*(int(value[i:i + 2], 16) for i in (1, 3, 5)))
    if re.fullmatch(r'colou?r[0-9]+', value): return int(re.search(r'[0-9]+', value)[0])
    names = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
    if value in names: return names.index(value)
    if value.startswith('bright') and value[6:] in names: return 8 + names.index(value[6:])
    return default


def style(value):
    return dict(re.findall(r'(fg|bg)=([^, ]+)', value))


def read_theme(pane=''):
    fields = ['@bw_accent', '@bw_on_accent', '@bw_bg', '@bw_fg', '@bw_raised', '@bw_muted',
              'message-style', 'message-command-style', 'status-style', 'status-left-style', 'mode-style']
    fmt = '\t'.join('#{E:' + field + '}' for field in fields)
    args = ['display-message', '-p'] + (['-t', pane] if pane else []) + [fmt]
    return tuple(tm(*args).split('\t'))


def palette(values):
    accent, on, bg, fg, raised, muted, message, command, status, left, mode = values
    message, command, status, left, mode = map(style, (message, command, status, left, mode))
    highlight = colour(accent, colour(message.get('bg', ''), colour(mode.get('bg', ''), 6)))
    background = colour(bg, colour(command.get('bg', ''), colour(status.get('bg', ''))))
    foreground = colour(fg, colour(status.get('fg', ''), colour(left.get('fg', ''), 7)))
    # Use the theme's own contrasting selection text whenever available.
    contrast = colour(on, colour(message.get('fg', ''), 0 if highlight in (3, 6, 7, 11, 14, 15, 226) else 7))
    return highlight, contrast, background, foreground, colour(raised, background), colour(muted, foreground)


def apply(pane='', force=False):
    global ACCENT, BORDER, BODY, MUTED, SELECTION, BADGE, EDGE, TEXT, _signature, _next_check, _pane
    import time
    if not force and time.monotonic() < _next_check: return False
    _next_check = time.monotonic() + 1
    if pane: _pane = pane
    values = read_theme(_pane)
    if values == _signature: return False
    _signature = values
    highlight, contrast, bg, fg, raised, muted = palette(values)
    try:
        curses.use_default_colors()
        for number, fore, back in [(1, highlight, -1), (2, contrast, highlight), (3, fg, raised),
                                   (4, raised, -1), (5, fg, bg), (6, muted, bg), (7, highlight, bg), (8, fg, -1)]:
            if curses.COLORS < 256:
                fore = fore if fore < curses.COLORS else curses.COLOR_WHITE
                back = back if back < curses.COLORS else curses.COLOR_BLACK
            curses.init_pair(number, fore, back)
        ACCENT, BORDER, BODY, MUTED = (curses.color_pair(i) for i in (1, 7, 5, 6))
        SELECTION = curses.color_pair(2) | curses.A_BOLD
        BADGE, EDGE, TEXT = (curses.color_pair(i) for i in (3, 4, 8))
    except curses.error:
        ACCENT = BORDER = curses.A_BOLD
        SELECTION = curses.A_REVERSE
    return True
