"""Publish curses' initial screen in one write instead of flashing setup frames."""
import os
import sys


class FirstPaint:
    def __enter__(self):
        self.output = os.dup(1)
        size = os.get_terminal_size(self.output)
        self.previous = {key: os.environ.get(key) for key in ('LINES', 'COLUMNS')}
        os.environ.update(LINES=str(size.lines), COLUMNS=str(size.columns))
        self.buffer = os.fdopen(os.memfd_create('tmux-picker-first-paint', os.MFD_CLOEXEC), 'w+b')
        sys.stdout.flush()
        os.dup2(self.buffer.fileno(), 1)
        return self

    def release(self):
        if self.output is None:
            return
        sys.stdout.flush()
        self.buffer.seek(0)
        frame = self.buffer.read()
        output, self.output = self.output, None
        os.dup2(output, 1)
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            while frame:
                frame = frame[os.write(output, frame):]
        finally:
            os.close(output)
            self.buffer.close()

    def __exit__(self, *exc):
        self.release()


def frame(screen, top, left, height, width, attr=0, rounded=False):
    import curses
    corners = ('╭', '╮', '╰', '╯') if rounded else ('┌', '┐', '└', '┘')
    def put(y, x, value):
        try: screen.addstr(y, x, value, attr)
        except curses.error: pass
    put(top, left, corners[0] + '─' * max(0, width - 2) + corners[1])
    put(top + height - 1, left, corners[2] + '─' * max(0, width - 2) + corners[3])
    for y in range(top + 1, top + height - 1):
        put(y, left, '│'); put(y, left + width - 1, '│')


def reveal_bounds(height, width, steps=9):
    """A short ease-out reveal with a fixed centre and monotonically growing bounds."""
    for index in range(steps):
        progress = 1 - (1 - index / (steps - 1)) ** 3
        h = min(height, round(min(5, height) + (height - min(5, height)) * progress))
        w = min(width, round(min(24, width) + (width - min(24, width)) * progress))
        top, left = (height - h) // 2, (width - w) // 2
        yield top, left, h, w


def reveal(screen, canvas, publish, attr=0, rounded=False):
    import curses
    import time
    height, width = screen.getmaxyx()
    published = False
    try:
        for index, (top, left, h, w) in enumerate(reveal_bounds(height, width)):
            screen.erase()
            if index == 8:
                canvas.overwrite(screen)
            else:
                canvas.overwrite(screen, top + 1, left + 1, top + 1, left + 1, top + h - 2, left + w - 2)
                frame(screen, top, left, h, w, attr, rounded)
            screen.refresh()
            if not published:
                publish(); published = True
            if index != 8: time.sleep(.015)
    except curses.error:
        # A resize may arrive mid-reveal; normal rendering resumes immediately.
        screen.touchwin()
        screen.refresh()
    finally:
        if not published: publish()
