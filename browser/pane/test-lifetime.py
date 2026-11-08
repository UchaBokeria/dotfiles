#!/usr/bin/env python3
"""Real Kitty pixel checks: hide/restore/close a pane without floating images."""
import base64
import io
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
from PIL import Image,ImageGrab

ROOT=Path(__file__).resolve().parent
KITTY=os.environ.get('KITTY_TEST_BINARY','/tmp/browser-kitty-check/root/usr/bin/kitty')
MARKER=(223,37,104)

def main():
    with tempfile.TemporaryDirectory(prefix='browser-kitty-lifetime-') as folder:
        path=Path(folder);sock=str(path/'tmux');remote=str(path/'kitty.sock')
        display=os.environ.get('BROWSER_TEST_DISPLAY',':99')
        env={**os.environ,'DISPLAY':display,'KITTY_ENABLE_WAYLAND':'0','LIBGL_ALWAYS_SOFTWARE':'1','CHROME_PLACEHOLDER_DATA':str(ROOT/'placeholder-diacritics.json')}
        env.pop('TMUX',None);env.pop('TMUX_PANE',None)
        def tm(*args):return subprocess.check_output(['tmux','-S',sock,*args],env=env,text=True).strip()
        def wait(check,timeout=8):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                if check():return True
                time.sleep(.08)
            return check()
        proc=None
        try:
            tm('-f','/dev/null','new-session','-d','-x','100','-y','32','-s','anchor','sleep 600')
            anchor=tm('display-message','-p','-t','anchor','#{pane_id}:#{pane_pid}')
            tm('set-option','-s','terminal-overrides','xterm-kitty:Tc')
            tm('set-option','-gw','allow-passthrough','on')
            tm('new-window','-d','-t','anchor:','-n','other','sleep 600')
            tm('select-window','-t','anchor:0')
            log=(path/'kitty.log').open('wb')
            proc=subprocess.Popen([KITTY,'--config','NONE','--class','BrowserPaneLifetime','--title','Browser Pane Lifetime Test',
                '-o','allow_remote_control=yes','-o','listen_on=unix:'+remote,'-o','confirm_os_window_close=0',
                '-o','remember_window_size=no','-o','initial_window_width=1000','-o','initial_window_height=650','-o','shell_integration=disabled',
                'tmux','-S',sock,'attach-session','-t','anchor'],env=env,stdout=log,stderr=log)
            def ids():
                r=subprocess.run(['xdotool','search','--onlyvisible','--class','BrowserPaneLifetime'],env=env,text=True,capture_output=True)
                return r.stdout.splitlines()
            assert wait(lambda:bool(ids())),(path/'kitty.log').read_text()
            window=ids()[-1]
            def pixel_count():
                output=subprocess.check_output(['xdotool','getwindowgeometry','--shell',window],env=env,text=True)
                d=dict(line.split('=',1) for line in output.splitlines() if '=' in line)
                x,y,w,h=(int(d[k]) for k in ('X','Y','WIDTH','HEIGHT'))
                image=ImageGrab.grab(bbox=(x,y,x+w,y+h),xdisplay=display).convert('RGB')
                colors=dict((color,count) for count,color in image.getcolors(image.width*image.height))
                return colors.get(MARKER,0)
            for mode in ('full','page'):
                if mode=='full':
                    script=path/'fixture.py';script.write_text('''import sys,time\nfrom PIL import Image\nsys.path.insert(0,''' + repr(str(ROOT)) + ''')\nfrom desktop import View\nclass Fake:\n def snapshot(self):return 1,Image.new('RGB',(800,500),(223,37,104))\nv=View(Fake());v.write(b'\\x1b[?1049h\\x1b[?25l');v.render()\nwhile True: v.render();time.sleep(.1)\n''')
                    command=shlex.join(['python3',str(script)])
                else:
                    im=Image.new('RGB',(800,500),MARKER);png=io.BytesIO();im.save(png,'PNG')
                    module=Path.home()/'.local/share/browser-pane/casty/lib/kitty.js'
                    js=path/'fixture.mjs';js.write_text(f"import {{setDisplaySize,sendFrame,resetFrameCache}} from {str(module)!r}; setDisplaySize(process.stdout.columns,process.stdout.rows-1); process.stdout.write('\\x1b[?1049h'); sendFrame({base64.b64encode(png.getvalue()).decode()!r}); process.on('SIGWINCH',()=>{{setDisplaySize(process.stdout.columns,process.stdout.rows-1);resetFrameCache();sendFrame({base64.b64encode(png.getvalue()).decode()!r});}});setInterval(()=>{{sendFrame({base64.b64encode(png.getvalue()).decode()!r});}},100);")
                    command=shlex.join(['node',str(js)])
                pane=tm('split-window','-h','-P','-F','#{pane_id}','-t','anchor:0',command)
                tm('set-option','-w','-t',pane,'allow-passthrough','on')
                assert wait(lambda:pixel_count()>30000),(mode,'image not rendered',pixel_count(),tm('show-options','-Aw','-t',pane,'allow-passthrough'),tm('list-clients','-F','#{client_termname} #{client_termfeatures}'),tm('capture-pane','-p','-t',pane)[-1000:],(path/'kitty.log').read_text()[-600:])
                tm('select-window','-t','anchor:1')
                assert wait(lambda:pixel_count()<50),(mode,'image leaked onto another window',pixel_count())
                tm('select-window','-t','anchor:0')
                assert wait(lambda:pixel_count()>30000),(mode,'image failed to return with its pane',pixel_count())
                original=tm('display-message','-p','-t',pane,'#{pane_width}')
                large=pixel_count();tm('resize-pane','-t',pane,'-x','25')
                assert wait(lambda:1000<pixel_count()<large*.8),(mode,'resize failed',pixel_count(),large,tm('capture-pane','-p','-t',pane)[-1000:],tm('display-message','-p','-t',pane,'#{pane_width} #{pane_height} #{pane_current_command}'))
                tm('resize-pane','-t',pane,'-x',original)
                assert wait(lambda:pixel_count()>30000)
                tm('break-pane','-s',pane,'-t','anchor:','-n','moved-'+mode)
                tm('set-option','-w','-t',pane,'allow-passthrough','on')
                assert wait(lambda:pixel_count()>30000),(mode,'moving to window failed')
                tm('kill-pane','-t',pane)
                assert wait(lambda:pixel_count()<50),(mode,'image survived closed pane',pixel_count())
                assert tm('display-message','-p','-t','anchor:0','#{pane_id}:#{pane_pid}')==anchor
                print('PASS:',mode,'real Kitty graphics hide/restore with window and disappear on pane closure; sibling pane retained.',flush=True)
        finally:
            if proc:
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
            subprocess.run(['tmux','-S',sock,'kill-server'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

if __name__=='__main__':main()
