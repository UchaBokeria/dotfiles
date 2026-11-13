#!/usr/bin/env python3
"""Unit tests for clipboard sync: feed() interception, latest-wins sha, ServerCutText echo suppression."""
import io
import os
from pathlib import Path
import queue
import struct
import sys
sys.path.insert(0,str(Path(__file__).parent))
import clipboard
from clipboard import Clipboard,sha
from desktop import View,CTRL,SHIFT
from rfb import Desktop

class FakeDesktop:
    def __init__(self,events):self.events=events;self.cuts=queue.SimpleQueue()
    def press(self,*a):self.events.append(('press',*a))
    def key(self,*a):self.events.append(('key',*a))
    def pointer(self,*a):self.events.append(('pointer',*a))
    def text(self,t):self.events.append(('text',t))
class FakeClip:
    def __init__(self,events,ok=True):self.events=events;self.ok=ok;self.echo=set()
    def sync(self):self.events.append(('sync',))
    def paste(self,text):self.events.append(('paste',text));return self.ok
    def is_echo(self,text):return text in self.echo
    def remember(self,mime,data):self.events.append(("remember",mime,data))
def make(ok=True):
    events=[];v=View(FakeDesktop(events),io.BytesIO(),FakeClip(events,ok));v.mapping=(0,0,100,100,100,100);return v,events
V=ord('v')

def intercept():
    for data in (b'\x16',b'\x1b[27;5;118~',b'\x1b[27;6;86~',b'\x1b[118;5u',b'\x1b[118;6u'):
        v,ev=make();v.feed(data)
        assert ev[0]==('sync',) and ev[1][0]=='press' and ev[1][1] in (V,86) and CTRL in ev[1][2],(data,ev)
    v,ev=make();v.feed(b'\x1b[2;2~');assert ev==[('sync',),('press',0xff63,(SHIFT,))],ev
    v,ev=make();v.feed(b'\x1b[<2;3;3M');assert ev[0]==('sync',) and ev[1][0]=='pointer' and ev[1][3]==4,ev
    # Never for other input: plain v, Ctrl+C, left/middle click, right release, drag, plain Insert, wheel.
    for data in (b'v',b'\x03',b'\x1b[118;3u',b'\x1b[<0;3;3M',b'\x1b[<1;3;3M',b'\x1b[<2;3;3m',b'\x1b[<34;3;3M',b'\x1b[2~',b'\x1b[<64;3;3M',b'\x1b[<35;3;3M'):
        v,ev=make();v.feed(data);assert ('sync',) not in ev,(data,ev)
    v,ev=make();v.clipboard=None;v.feed(b'\x16');assert ev==[('press',V,(CTRL,))],ev # no clipboard configured
    print('PASS: Ctrl+V (raw, 27;5;118~, CSI-u, Ctrl+Shift+V), Shift+Insert and right press sync before forwarding; nothing else does.')

def bracketed():
    v,ev=make();v.feed(b'\x1b[200~hello\nworld \xc3\xa9\x1b[201~z')
    assert ev==[('paste','hello\nworld \xe9'),('press',V,(CTRL,)),('text','z')],ev
    v,ev=make();v.feed(b'\x1b[200~par');assert ev==[]
    v.feed(b't\x1b[201~');assert ev==[('paste','part'),('press',V,(CTRL,))],ev
    v,ev=make(ok=False);v.feed(b'\x1b[200~abc\x1b[201~');assert ev==[('paste','abc'),('text','abc')],ev # falls back to typing
    print('PASS: bracketed paste writes the clipboard then sends Ctrl+V (typing only as fallback).')

class Source:
    def __init__(self):self.item=None;self.reads=0
    def read(self,timeout):self.reads+=1;return self.item
class Sink:
    def __init__(self,ok=True):self.writes=[];self.ok=ok
    def write(self,mime,data,timeout):self.writes.append((mime,data));return self.ok
def latest_wins():
    src,sink=Source(),Sink();c=Clipboard(src,sink)
    assert not c.sync() and not sink.writes            # empty/unavailable source
    src.item=('text/plain',b'one');assert c.sync() and sink.writes==[('text/plain',b'one')]
    assert not c.sync() and len(sink.writes)==1        # unchanged since last push: Chrome's own copy is kept
    src.item=('image/png',b'\x89PNG data');assert c.sync() and sink.writes[-1]==('image/png',b'\x89PNG data')
    src.item=('text/plain',b'two');assert c.sync() and len(sink.writes)==3
    assert c.paste('three') and c.last==sha(b'three') and sink.writes[-1]==('text/plain',b'three')
    src.item=('text/plain',b'three');assert not c.sync() and len(sink.writes)==4 # paste updated the sha
    sink.ok=False;src.item=('text/plain',b'four');assert not c.sync() and c.last==sha(b'three') # failed push is retried
    sink.ok=True;assert c.sync() and c.last==sha(b'four')
    assert not Clipboard(None,sink).sync() and not Clipboard(src,None).paste('x')
    class Boom:
        def read(self,t):raise RuntimeError('x')
    assert Clipboard(Boom(),sink).sync() is False        # never raises into the viewer
    print('PASS: latest wins: unchanged sha is not re-pushed, failed pushes retry, paste updates the sha, errors never propagate.')

def echo():
    src,sink=Source(),Sink();c=Clipboard(src,sink);src.item=('text/plain','caf\xe9 ☃'.encode());c.sync()
    for form in ('caf\xe9 ☃','caf\xe9 ☃'.encode().decode('latin-1'),'caf\xe9 ?'):assert c.is_echo(form),form
    assert not c.is_echo('something Chrome copied')
    v,ev=make();copied=[];v.copy_out=copied.append;v.clipboard=c
    v.desktop.cuts.put('page script write');v.drain_cuts();assert copied==[],copied # no copy intent: dropped
    v.feed(b'\x03')                                     # Ctrl+C = copy intent
    v.desktop.cuts.put('caf\xe9 ☃');v.desktop.cuts.put('from chrome');v.drain_cuts()
    assert copied==['from chrome'],copied
    v.desktop.cuts.put('from chrome');v.drain_cuts();assert copied==['from chrome']*2 # a real repeat copy still goes out
    # direct OSC 52 outside tmux, tmux buffer inside it.
    os.environ.pop('TMUX',None);v2,_=make();out=v2.output;View.copy_out(v2,'hi');assert out.getvalue()==b'\x1b]52;c;aGk=\x07',out.getvalue()
    print('PASS: Chrome->client forwards only user-initiated copies and suppresses the echo of what we pushed.')

def cut_text():
    d=Desktop.__new__(Desktop);d.cuts=queue.SimpleQueue();d.closed=False;d.error=None
    stream=bytearray()
    def msg(t):return b'\x03\0\0\0'+struct.pack('>I',len(t))+t
    stream+=msg('caf\xe9'.encode('latin-1'))+b'\x02'+msg(b'x'*((1<<20)+1))+msg('\u2603 caf\xe9'.encode())+msg(b'last')
    def read(n):
        if len(stream)<n:raise EOFError('end')
        out=bytes(stream[:n]);del stream[:n];return out
    d.read=read;d.request=lambda *_:None;d.receive()
    got=[d.cuts.get_nowait() for _ in range(3)]
    assert got==['caf\xe9','\u2603 caf\xe9','last'] and d.cuts.empty(),got   # oversize (>1 MiB) skipped without desync
    print('PASS: ServerCutText decoded as latin-1 (UTF-8 when valid), capped at 1 MiB, stream stays in sync.')

def helpers():
    calls=[]
    def fake(cmd,data=None,timeout=1.5,env=None):
        class R:returncode=0;stdout=b'0 0 192.168.1.8:1 13.140.155.113:22\n0 0 10.0.0.1:2 100.68.91.7:22\n'
        calls.append(cmd);return R
    real=clipboard.run;clipboard.run=fake
    try:assert clipboard.connected()
    finally:clipboard.run=real
    class R2:returncode=0;stdout=b'0 0 192.168.1.8:1 1.2.3.4:22\n'
    clipboard.run=lambda *a,**k:R2
    try:assert not clipboard.connected()
    finally:clipboard.run=real
    assert clipboard.main(['x','write','bogus'])==2
    print('PASS: connection check accepts only Blackwall peers; CLI rejects unknown MIME types.')

if __name__=='__main__':intercept();bracketed();latest_wins();echo();cut_text();helpers()
