"""Read tmux's live screen cells without resizing or sending input to applications."""
import curses
from functools import lru_cache
import re
import unicodedata
from workspaces import command_queue, tm

SGR = re.compile(r'\x1b\[([0-9;:]*)m')


@lru_cache(maxsize=4096)
def colour256(red, green, blue):
    levels = (0, 95, 135, 175, 215, 255)
    r, g, b = (min(range(6), key=lambda i: abs(levels[i] - c)) for c in (red, green, blue))
    cube = 16 + 36 * r + 6 * g + b
    gray = max(0, min(23, round(((red + green + blue) / 3 - 8) / 10)))
    return 232 + gray if sum((8 + gray * 10 - c) ** 2 for c in (red, green, blue)) < sum((levels[i] - c) ** 2 for i, c in zip((r, g, b), (red, green, blue))) else cube


def cells(lines):
    """Decode capture-pane -e, including attributes that continue across lines."""
    foreground = background = -1
    attrs = 0
    result = []
    for line in lines:
        output, start = [], 0
        for match in list(SGR.finditer(line)) + [None]:
            end = match.start() if match else len(line)
            for char in line[start:end]:
                if not char.isprintable() and not "\ue000" <= char <= "\uf8ff":
                    continue
                if unicodedata.combining(char) and output:
                    old = output[-1]
                    output[-1] = (old[0] + char, *old[1:])
                    continue
                output.append((char, foreground, background, attrs))
                if unicodedata.east_asian_width(char) in ('W', 'F'):
                    output.append(('', foreground, background, attrs))
            if match is None:
                break
            codes = [int(part or 0) for part in match[1].replace(':', ';').split(';')]
            i = 0
            while i < len(codes):
                code = codes[i]
                if code == 0: foreground = background = -1; attrs = 0
                elif code == 1: attrs |= curses.A_BOLD
                elif code == 2: attrs |= curses.A_DIM
                elif code == 3: attrs |= getattr(curses, 'A_ITALIC', 0)
                elif code == 4: attrs |= curses.A_UNDERLINE
                elif code == 7: attrs |= curses.A_REVERSE
                elif code == 22: attrs &= ~(curses.A_BOLD | curses.A_DIM)
                elif code == 23: attrs &= ~getattr(curses, 'A_ITALIC', 0)
                elif code == 24: attrs &= ~curses.A_UNDERLINE
                elif code == 27: attrs &= ~curses.A_REVERSE
                elif 30 <= code <= 37: foreground = code - 30
                elif 40 <= code <= 47: background = code - 40
                elif 90 <= code <= 97: foreground = code - 90 + 8
                elif 100 <= code <= 107: background = code - 100 + 8
                elif code == 39: foreground = -1
                elif code == 49: background = -1
                elif code in (38, 48) and i + 2 < len(codes):
                    colour = None
                    if codes[i + 1] == 5:
                        colour = codes[i + 2]; i += 2
                    elif codes[i + 1] == 2 and i + 4 < len(codes):
                        colour = colour256(*codes[i + 2:i + 5]); i += 4
                    if colour is not None:
                        if code == 38: foreground = colour
                        else: background = colour
                i += 1
            start = match.end()
        result.append(output)
    return result


def crop_origin(size, cursor, available, visible):
    """The same cursor-centred viewport rule as tmux screen_write_preview."""
    return max(0, min(max(0, size - available), max(0, cursor - available // 3))) if visible else 0


class Preview:
    def __init__(self):
        self.pairs = {}
        self.snapshots = {}
        self.decoded = {}

    def capture(self, pane):
        capture = tm(*command_queue([
            ('display-message', '-p', '-t', pane, '#{pane_width} #{pane_height} #{cursor_x} #{cursor_y} #{cursor_flag}'),
            ('capture-pane', '-p', '-e', '-t', pane)])).splitlines()
        if not capture: return None
        values = capture[0].split()
        if len(values) != 5:
            return None
        width, height, x, y, cursor = map(int, values)
        lines = capture[1:]
        previous = self.decoded.get(pane)
        if previous is None or previous[0] != lines:
            previous = (lines, cells(lines))
            self.decoded[pane] = previous
        return width, height, x, y, bool(cursor), previous[1]

    def style(self, fg, bg, attrs):
        key = fg, bg
        if key not in self.pairs:
            pair = len(self.pairs) + 10
            if pair >= min(curses.COLOR_PAIRS, 240):
                return attrs
            try:
                curses.init_pair(pair, fg, bg)
                self.pairs[key] = pair
            except curses.error:
                return attrs
        return curses.color_pair(self.pairs[key]) | attrs

    def pane(self, screen, pane, y, x, height, width, refresh=True):
        if height < 1 or width < 1:
            return
        if refresh or pane not in self.snapshots:
            self.snapshots[pane] = self.capture(pane)
        snapshot = self.snapshots[pane]
        if not snapshot:
            return
        sx, sy, cx, cy, visible, lines = snapshot
        left = crop_origin(sx, cx, width, visible)
        top = crop_origin(sy, cy, height, visible)
        for row in range(top, min(sy, top + height, len(lines))):
            run, start, style = [], left, None
            def flush():
                if run:
                    try: screen.addstr(y + row - top, x + start - left, ''.join(run), style)
                    except curses.error: pass
            for col in range(left, min(sx, left + width, len(lines[row]))):
                char, fg, bg, attrs = lines[row][col]
                if not char or (col == left and col > 0 and lines[row][col - 1][0] and unicodedata.east_asian_width(lines[row][col - 1][0][0]) in ('W', 'F')):
                    continue
                if col == left + width - 1 and unicodedata.east_asian_width(char[0]) in ('W', 'F'):
                    continue
                if visible and (col, row) == (cx, cy): attrs ^= curses.A_REVERSE
                current = self.style(fg, bg, attrs)
                if current != style:
                    flush();run = [];start = col;style = current
                run.append(char)
            flush()
