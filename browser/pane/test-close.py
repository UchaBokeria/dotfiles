#!/usr/bin/env python3
"""Closing actual browser panes stops owned viewers and restores shared settings."""
import fcntl
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import pty
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

ROOT=Path(__file__).parent
h=runpy.run_path(str(ROOT/'test-pane.py'));targets,rpc,Fixture,chrome_pid=[h[k] for k in ('targets','rpc','Fixture','chrome_pid')]

def live(pid):
    try:return Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split()[0]!='Z'
    except OSError:return False

def descendants(pid):
    rows=[list(map(int,line.split())) for line in subprocess.check_output(['ps','-u',str(os.getuid()),'-o','pid=,ppid='],text=True).splitlines()]
    result={int(pid)}
    while True:
        found={p for p,parent in rows if parent in result}
        if found<=result:
            owned=set()
            for p in result:
                try:cmd=Path(f'/proc/{p}/cmdline').read_bytes().decode(errors='replace')
                except OSError:continue
                if any(token in cmd for token in ('/browser/pane/chrome','/browser/pane/desktop.py','casty/bin/casty.js')):owned.add(p)
            return owned
        result|=found

def main():
    fixture=ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=fixture.serve_forever,daemon=True).start()
    url=os.environ.get('BROWSER_TEST_URL',f'http://127.0.0.1:{fixture.server_port}/');before={t['id'] for t in targets()}
    original_chrome_pid=chrome_pid()
    own=None
    with tempfile.TemporaryDirectory(prefix='chrome-close-') as folder:
        socket=folder+'/tmux';env={**os.environ,'TERM':'xterm-kitty'};env.pop('TMUX',None);env.pop('TMUX_PANE',None)
        def tm(*args):return subprocess.check_output(['tmux','-S',socket,*args],env=env,text=True).rstrip('\n')
        master=slave=proc=None
        def drain(duration=.1):
            end=time.monotonic()+duration
            while time.monotonic()<end:
                if select.select([master],[],[],.01)[0]:
                    try:os.read(master,262144)
                    except OSError:break
        def wait(predicate,timeout=10):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                if predicate():return True
                drain(.08)
            return predicate()
        try:
            tm('-f','/dev/null','new-session','-d','-x','120','-y','38','-s','anchor','sleep 600')
            tm('set-option','-g','prefix','C-a');tm('set-option','-g','mouse','off')
            anchor=tm('display-message','-p','#{pane_id}:#{pane_pid}')
            server=tm('display-message','-p','#{pid}')
            master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',38,120,1200,760))
            proc=subprocess.Popen(['tmux','-S',socket,'attach-session','-t','anchor'],stdin=slave,stdout=slave,stderr=slave,env=env);os.close(slave);slave=None
            full=tm('split-window','-v','-P','-F','#{pane_id}',shlex.join([str(ROOT/'chrome'),'--full']))
            assert wait(lambda:'\U0010eeee' in tm('capture-pane','-p','-t',full))
            full_processes=descendants(tm('display-message','-p','-t',full,'#{pane_pid}'))
            page=tm('split-window','-h','-t',full,'-P','-F','#{pane_id}',shlex.join([str(ROOT/'chrome'),'--page',url]))
            assert wait(lambda:'\U0010eeee' in tm('capture-pane','-p','-t',page))
            own=next(t for t in targets() if t['url']==url)
            page_processes=descendants(tm('display-message','-p','-t',page,'#{pane_pid}'))
            tm('new-window','-d','-t','anchor:','-n','normal','sleep 600')
            tm('select-window','-t','anchor:normal')
            assert wait(lambda:tm('show-options','-Av','mouse')=='off')
            assert tm('display-message','-p','#{prefix}')=='C-a'
            tm('select-window','-t','anchor:0')
            assert wait(lambda:tm('show-options','-Av','mouse')=='on')
            assert wait(lambda:tm('display-message','-p','#{prefix}')=='None')
            tm('kill-pane','-t',full)
            assert wait(lambda:all(not live(p) for p in full_processes)),full_processes
            assert all(live(p) for p in page_processes)
            assert tm('display-message','-p','-t',page,'#{allow-passthrough}')=='on'
            assert tm('display-message','-p','-t',page,'#{prefix}')=='None'
            tm('kill-pane','-t',page)
            assert wait(lambda:all(not live(p) for p in page_processes)),page_processes
            assert wait(lambda:tm('display-message','-p','#{prefix}')=='C-a')
            assert tm('display-message','-p','#{allow-passthrough}')=='off'
            assert tm('display-message','-p','#{pane_id}:#{pane_pid}')==anchor
            assert tm('show-options','-gv','mouse')=='off'
            assert wait(lambda:tm('show-options','-Av','mouse')=='off'), (tm('show-options','-t','anchor','mouse'),tm('show-options','-qv','-t','anchor','@browser-original-mouse'),tm('list-panes','-a','-F','#{pane_id} #{@browser-viewer} #{@browser-input}'))
            assert not tm('show-options','-sqv','@browser-mode-installed')
            assert tm('display-message','-p','#{pid}')==server
            assert before<={t['id'] for t in targets()}
            assert original_chrome_pid==chrome_pid()
            print('PASS: closing full/page panes kills owned viewer processes; concurrent pane retains graphics/input; final settings restored; anchor/Chrome/tabs/server preserved.')
        finally:
            if master is not None:os.close(master)
            if slave is not None:os.close(slave)
            subprocess.run(['tmux','-S',socket,'kill-server'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if proc:
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=3)
            if own:
                try:rpc(own,'Page.close')
                except Exception:pass
            fixture.shutdown()

if __name__=='__main__':main()
