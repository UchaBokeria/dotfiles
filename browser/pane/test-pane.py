#!/usr/bin/env python3
"""Exercise real Chrome pixels/input through a disposable tmux server and PTY."""
import base64
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import pty
import re
import select
import shlex
import signal
import socket
import struct
import subprocess
import tempfile
import termios
import threading
import time
import urllib.request
import websocket

BASE='http://127.0.0.1:9222'
def targets(): return json.load(urllib.request.urlopen(BASE+'/json/list'))
def rpc(target,method,params=None):
    ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=8)
    try:
        ws.send(json.dumps({'id':1,'method':method,'params':params or {}}))
        while True:
            data=json.loads(ws.recv())
            if data.get('id')==1:
                assert 'error' not in data,data
                return data.get('result',{})
    finally: ws.close()
def evaluate(target,expr):return rpc(target,'Runtime.evaluate',{'expression':expr,'returnByValue':True})['result'].get('value')
class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        page=b'''<!doctype html><style>body{margin:0;background:#d63975;color:white;height:3000px}input{position:absolute;left:50px;top:50px;width:300px;height:40px}</style><h1>Real Chrome in tmux</h1><input id="typing"><div style="margin-top:800px">Scrolled</div>'''
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(page)
    def log_message(self,*a):pass

def main():
    before={x['id'] for x in targets()};pid=subprocess.check_output(['systemctl','--user','show','cloud-chrome','--value','-p','MainPID'],text=True).strip()
    fixture=ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=fixture.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{fixture.server_port}/'
    with tempfile.TemporaryDirectory(prefix='browser-pane-test-') as folder:
        sock=folder+'/tmux';env={**os.environ,'TERM':'xterm-kitty'};env.pop('TMUX',None);env.pop('TMUX_PANE',None)
        def tm(*a):return subprocess.check_output(['tmux','-S',sock,*a],env=env,text=True).strip()
        master=slave=proc=None;own=None;output=bytearray()
        def drain(duration=.15):
            end=time.monotonic()+duration
            while time.monotonic()<end:
                if select.select([master],[],[],.01)[0]:
                    try: output.extend(os.read(master,262144))
                    except OSError: break
        def wait(check,timeout=10):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                if check():return True
                drain(.08)
            return check()
        try:
            tm('-f','/dev/null','new-session','-d','-x','100','-y','32','-s','anchor','sleep 600')
            server=tm('display-message','-p','#{pid}')
            command=shlex.join([str(Path(__file__).with_name('chrome')),'--page',url])+"; printf 'SHELL_RETURNED\\n'; exec sleep 600"
            pane=tm('new-window','-P','-F','#{pane_id}','-t','anchor:','-n','browser',command)
            master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',32,100,1000,640))
            proc=subprocess.Popen(['tmux','-S',sock,'attach-session','-t','anchor'],stdin=slave,stdout=slave,stderr=slave,env=env);os.close(slave);slave=None
            assert wait(lambda:any(x['url']==url for x in targets())),bytes(output[-1500:])
            own=next(x for x in targets() if x['url']==url)
            assert wait(lambda:b'\x1b_Ga=T' in output),bytes(output[-1500:])
            chunks=re.findall(rb'\x1b_G([^;]*);([^\x1b]*)\x1b\\',output)
            image=b'';found=False
            for params,payload in chunks:
                if b'a=T' in params:image=b''
                if payload:image+=payload
                if payload and b'm=1' not in params:
                    assert base64.b64decode(image).startswith(b'\x89PNG'),params
                    found=True;break
            assert found,'No actual PNG frame reached enclosing terminal'
            assert tm('show-options','-wqv','-t',pane,'allow-passthrough')=='on'
            # terminal cell (10,6) maps to CSS (76,72), inside the input.
            os.write(master,b'\x1b[<0;10;6M\x1b[<0;10;6m');drain(.25);os.write(master,b'pane-input')
            assert wait(lambda:evaluate(own,'document.querySelector("input").value')=='pane-input')
            os.write(master,b'\x1b[<65;50;20M')
            assert wait(lambda:evaluate(own,'window.scrollY')>0)
            os.write(master,b'\x1bl');drain(.2);os.write(master,(url+'?address-bar=ok').encode()+b'\r')
            assert wait(lambda:evaluate(own,'location.search')=='?address-bar=ok')
            fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',26,80,800,520));os.kill(proc.pid,signal.SIGWINCH)
            assert wait(lambda:evaluate(own,'window.innerWidth')==640),evaluate(own,'window.innerWidth')
            os.write(master,b'\x11')
            assert wait(lambda:'SHELL_RETURNED' in tm('capture-pane','-p','-t',pane)),bytes(output[-800:])
            assert tm('display-message','-p','-t',pane,'#{allow-passthrough}')=='off'
            assert evaluate(own,'window.innerWidth') != 640
            assert b'd=A' not in output, 'Other panes graphics must never be cleared'
            assert before <= {x['id'] for x in targets()},'An existing browser tab was closed'
            assert pid==subprocess.check_output(['systemctl','--user','show','cloud-chrome','--value','-p','MainPID'],text=True).strip()
            assert tm('display-message','-p','#{pid}')==server
            print('PASS: real PNG frames through tmux; mouse click; typing; scrolling; address bar; resize; Ctrl+Q; original Chrome/tabs and tmux server retained.')
        finally:
            if master is not None:os.close(master)
            if slave is not None:os.close(slave)
            subprocess.run(['tmux','-S',sock,'kill-server'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if proc:
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=3)
            if own:
                try:rpc(own,'Page.close')
                except Exception:pass
            fixture.shutdown()

if __name__=='__main__':main()
