"""Kitty virtual placements whose visibility/lifetime follows tmux text cells."""
import json
from pathlib import Path
MARKS=tuple(chr(n) for n in json.loads(Path(__file__).with_name('placeholder-diacritics.json').read_text()))
PLACEHOLDER='\U0010eeee'

def grid(image_id,cols,rows,top=1):
    if rows>len(MARKS):raise ValueError('Terminal has too many rows for Kitty placeholders')
    rgb=image_id&0xffffff;hi=(image_id>>24)&255
    # Normal text, never passthrough: tmux owns these cells and removes them on
    # pane/window changes. Explicit row/column marks also survive clipping.
    chunks=[f'\x1b[38;2;{rgb>>16};{(rgb>>8)&255};{rgb&255}m']
    for row in range(rows):
        chunks.append(f'\x1b[{top+row};1H')
        for col in range(cols):
            marks=MARKS[row]+MARKS[col]+MARKS[hi] if col<len(MARKS) else ''
            chunks.append(PLACEHOLDER+marks)
    chunks.append('\x1b[0m')
    return ''.join(chunks).encode()
