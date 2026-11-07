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
