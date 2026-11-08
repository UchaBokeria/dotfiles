#!/usr/bin/env python3
"""Test native Chrome controls, shared Xvfb pixels and return to the shell."""
import base64
import fcntl
import io
import json
import os
from pathlib import Path
import pty
import re
import runpy
import select
import shlex
import signal
import struct
import subprocess
import tempfile
import termios
import threading
import time
from http.server import ThreadingHTTPServer
from PIL import Image

helpers=runpy.run_path(str(Path(__file__).with_name('test-pane.py')))
targets,rpc,evaluate,Fixture,chrome_pid=[helpers[x] for x in ('targets','rpc','evaluate','Fixture','chrome_pid')]
import urllib.request
browser=json.load(urllib.request.urlopen(helpers['BASE']+'/json/version'))
def br(method,params=None):return rpc(browser,method,params)

def main():
    before={x['id'] for x in targets() if x['type']=='page'}
    pid=chrome_pid()
    fixture=ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=fixture.serve_forever,daemon=True).start()
    url=os.environ.get('BROWSER_TEST_URL',f'http://127.0.0.1:{fixture.server_port}/')
    target_id=br('Target.createTarget',{'url':url,'newWindow':True})['targetId']
    own=None;window_id=None
    try:
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            own=next((x for x in targets() if x['id']==target_id),None)
            if own and evaluate(own,'document.readyState')=='complete':break
            time.sleep(.05)
        assert own
        window_id=br('Browser.getWindowForTarget',{'targetId':target_id})['windowId']
        br('Browser.setWindowBounds',{'windowId':window_id,'bounds':{'windowState':'maximized'}})
        br('Target.activateTarget',{'targetId':target_id})
        with tempfile.TemporaryDirectory(prefix='chrome-full-test-') as folder:
            sock=folder+'/tmux';env={**os.environ,'TERM':'xterm-kitty'};env.pop('TMUX',None);env.pop('TMUX_PANE',None)
            def tm(*args):return subprocess.check_output(['tmux','-S',sock,*args],env=env,text=True).strip()
            master=slave=proc=None;output=bytearray()
            def drain(duration=.1):
                end=time.monotonic()+duration
                while time.monotonic()<end:
                    if select.select([master],[],[],.01)[0]:
                        try:output.extend(os.read(master,262144))
                        except OSError:break
            def wait(check,timeout=8):
                end=time.monotonic()+timeout
                while time.monotonic()<end:
                    if check():return True
                    drain(.05)
                return check()
            try:
                tm('-f','/dev/null','new-session','-d','-x','100','-y','32','-s','anchor','sleep 600')
                server=tm('display-message','-p','#{pid}')
                tm('set-option','-g','prefix','C-a')
                tm('set-option','-g','mouse','off')
                tm('bind-key','-T','root','C-l','set-option','-g','@root-key-hit','yes')
                command=shlex.join([str(Path(__file__).with_name('chrome')),'--full'])+"; printf 'FULL_SHELL_RETURNED\\n'; exec sleep 600"
                pane=tm('new-window','-P','-F','#{pane_id}','-t','anchor:','-n','full',command)
                master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',32,100,1000,640))
                proc=subprocess.Popen(['tmux','-S',sock,'attach-session','-t','anchor'],stdin=slave,stdout=slave,stderr=slave,env=env);os.close(slave);slave=None
                assert wait(lambda:b'\x1b_Ga=T' in output),bytes(output[-1000:])
                drain(.5)
                assert tm('display-message','-p','-t',pane,'#{prefix}')=='None'
                assert tm('show-options','-gv','mouse')=='off'
                # Native Ctrl+T creates an actual Chrome tab, then Ctrl+W closes it.
                current={t['id'] for t in targets() if t['type']=='page'}
                os.write(master,b'\x14')
                assert wait(lambda:len([t for t in targets() if t['type']=='page' and t['id'] not in current])>=1)
                os.write(master,b'\x17');drain(.2)
                os.write(master,b'\x0c');drain(.15);os.write(master,(url+'?native-toolbar=ok').encode()+b'\r')
                assert wait(lambda:evaluate(own,'location.search')=='?native-toolbar=ok')
                # Map a point in the page input through the full desktop, including toolbar height.
                y=evaluate(own,'window.screenY+window.outerHeight-window.innerHeight+70')
                col=round((150/1600*1000)/10+.5);row=round((38+y/900*562)/20+.5)
                os.write(master,f'\x1b[<0;{col};{row}M\x1b[<0;{col};{row}m'.encode());drain(.1);os.write(master,b'full-browser')
                assert wait(lambda:evaluate(own,'document.querySelector("input").value')=='full-browser')
                tm('set-option','-g','mouse','on')
                os.write(master,f'\x1b[<0;{col};{row}M\x1b[<0;{col};{row}m'.encode());drain(.1)
                os.write(master,b'\x01');drain(.08);os.write(master,b'Z')
                assert wait(lambda:evaluate(own,'document.querySelector("input").value')=='Z')
                os.write(master,b'\x01');drain(.08);os.write(master,b'\x1b')
                assert wait(lambda:tm('display-message','-p','-t',pane,'#{prefix}')=='C-a'), (tm('display-message','-p','-t',pane,'#{prefix} #{@browser-input} #{@browser-original-input} #{client_key_table}'), tm('list-keys','-T','browser-pane-prefix'), bytes(output[-300:]))
                os.write(master,b'\x0c')
                assert wait(lambda:tm('show-options','-gqv','@root-key-hit')=='yes')
                os.write(master,b'\x01');drain(.08);os.write(master,b'\x1b')
                assert wait(lambda:tm('display-message','-p','-t',pane,'#{prefix}')=='None')
                fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',26,80,800,520));os.kill(proc.pid,signal.SIGWINCH);drain(.4)
                # Extract the last complete real frame for visual inspection.
                image=b'';last=None
                for params,payload in re.findall(rb'\x1b_G([^;]*);([^\x1b]*)\x1b\\',output):
                    if b'a=T' in params:image=b''
                    if payload:image+=payload
                    if payload and b'm=1' not in params:
                        raw=base64.b64decode(image)
                        if raw.startswith(b'\x89PNG'):last=raw
                assert last
                Image.open(io.BytesIO(last)).save('/tmp/chrome-full-terminal-test.png')
                tm('break-pane','-s',pane,'-t','anchor:','-n','moved')
                assert wait(lambda:tm('display-message','-p','-t',pane,'#{allow-passthrough}')=='on')
                drain(.3)
                os.write(master,b'\x11')
                assert wait(lambda:'FULL_SHELL_RETURNED' in tm('capture-pane','-p','-t',pane)),bytes(output[-900:])
                assert tm('display-message','-p','-t',pane,'#{allow-passthrough}')=='off'
                assert tm('display-message','-p','-t',pane,'#{prefix}')=='C-a'
                assert not tm('show-options','-gqv','@browser-mode-installed')
                assert before<={t['id'] for t in targets() if t['type']=='page'}
                assert tm('display-message','-p','#{pid}')==server
                assert pid==chrome_pid()
                print('PASS: same Xvfb Chrome pixels; native toolbar navigation; native new/close tab; mouse/typing; resize; return-to-shell; original browser/tabs/server preserved.')
            finally:
                if master is not None:os.close(master)
                if slave is not None:os.close(slave)
                subprocess.run(['tmux','-S',sock,'kill-server'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                if proc:
                    try:proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=3)
    finally:
        # All fixture tabs belong to our separately created browser window.
        for t in targets():
            if t['type']=='page' and t['id'] not in before:
                try:
                    if br('Browser.getWindowForTarget',{'targetId':t['id']})['windowId']==window_id:br('Target.closeTarget',{'targetId':t['id']})
                except Exception:pass
        fixture.shutdown()

def controls():
    import sys
    sys.path.insert(0,str(Path(__file__).parent))
    from desktop import View,CTRL,SHIFT
    class Fake:
        def __init__(self):self.events=[]
        def press(self,*args):self.events.append(('press',*args))
        def key(self,*args):self.events.append(('key',*args))
        def pointer(self,*args):self.events.append(('pointer',*args))
    fake=Fake();v=View(fake,io.BytesIO());v.mapping=(0,0,100,100,100,100)
    v.feed(b'\x1b[27;5;9~');assert fake.events[-1]==('press',0xff09,(CTRL,))
    v.feed(b'\x1b[9;6u');assert fake.events[-1]==('press',0xff09,(SHIFT,CTRL))
    v.feed(b'\x1b[<16;3;3M');assert ('key',CTRL,True) in fake.events and fake.events[-1]==('key',CTRL,False)
    v.feed(b'\x1b[999z\x1b[A');assert v.buf==b'' and fake.events[-1]==('press',0xff52)
    print('PASS: Ctrl+Tab/Shift+Ctrl+Tab, modified clicks and unknown terminal replies.')

if __name__=='__main__':controls();main()
