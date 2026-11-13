#!/usr/bin/env python3
"""Mirror the exact Xvfb desktop, including Chrome's tabs/toolbars/extensions."""
import base64
import fcntl
import io
import os
from pathlib import Path
import queue
import re
import select
import signal
import struct
import subprocess
import sys
import termios
import time
import tty
from PIL import Image
from rfb import Desktop
from placeholders import grid
from lifetime import PaneFocus
from clipboard import Clipboard

CTRL,ALT,SHIFT=0xffe3,0xffe9,0xffe1
SPECIAL={b'\x1b[A':0xff52,b'\x1b[B':0xff54,b'\x1b[C':0xff53,b'\x1b[D':0xff51,
 b'\x1b[H':0xff50,b'\x1b[F':0xff57,b'\x1b[2~':0xff63,b'\x1b[3~':0xffff,
 b'\x1b[1~':0xff50,b'\x1b[4~':0xff57,b'\x1b[7~':0xff50,b'\x1b[8~':0xff57,
 b'\x1b[5~':0xff55,b'\x1b[6~':0xff56,b'\x1bOP':0xffbe,b'\x1bOQ':0xffbf,
 b'\x1bOR':0xffc0,b'\x1bOS':0xffc1}
for num,f in ((15,5),(17,6),(18,7),(19,8),(20,9),(21,10),(23,11),(24,12)):SPECIAL[f'\x1b[{num}~'.encode()]=0xffbd+f

class View:
    def __init__(self,desktop,output=None,clipboard=None):
        self.desktop=desktop;self.clipboard=clipboard;self.output=output or sys.stdout.buffer;self.buttons=0;self.buf=b'';self.paste=False;self.intent=0
        self.cell_w,self.cell_h=10,20;self.image_id=(os.getpid()*4)%2147483644;self.shown=0;self.version=-1;self.size=None;self.last_paint=0;self.focus=PaneFocus();self.was_focused=True
    def write(self,data):self.output.write(data);self.output.flush()
    def sync(self):
        if self.clipboard:self.clipboard.sync()
    def paste_text(self,text):
        # Bracketed paste: clipboard + Ctrl+V instead of typing every character.
        if self.clipboard and self.clipboard.paste(text):self.desktop.press(ord('v'),(CTRL,))
        else:self.desktop.text(text)
    def copy_out(self,text):
        # Chrome -> client clipboard: tmux relays OSC 52 itself; outside tmux write it directly.
        # The client clipboard now equals this text: the next paste must not re-push it over Chrome's richer copy.
        if self.clipboard:self.clipboard.remember('text/plain',text.encode('utf-8'))
        if os.environ.get('TMUX'):
            try:subprocess.run(['tmux','set-buffer','-w','--',text],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
            except (OSError,subprocess.SubprocessError):pass
        else:
            try:self.write(b'\x1b]52;c;'+base64.b64encode(text.encode('utf-8'))+b'\x07')
            except OSError:pass
    def drain_cuts(self):
        while True:
            try:text=self.desktop.cuts.get_nowait()
            except (queue.Empty,AttributeError):return
            # Only a copy the user asked for (Ctrl+C/X/Insert or a click, e.g. menu Copy) reaches the client;
            # page scripts writing the clipboard on their own are dropped.
            if text and time.monotonic()-self.intent<3 and not (self.clipboard and self.clipboard.is_echo(text)):self.copy_out(text)
    def graphics(self,data):
        if os.environ.get('TMUX'):data=b'\x1bPtmux;'+data.replace(b'\x1b',b'\x1b\x1b')+b'\x1b\\'
        return data
    def dimensions(self):
        rows,cols,x,y=struct.unpack('HHHH',fcntl.ioctl(1,termios.TIOCGWINSZ,bytes(8)))
        return cols,rows,max(1,cols*self.cell_w),max(1,rows*self.cell_h)
    def render(self,force=False):
        if not self.focus.active():
            self.was_focused=False
            return
        force=force or not self.was_focused
        self.was_focused=True
        version,image=self.desktop.snapshot();size=self.dimensions()
        if not force and self.version==version and self.size==size and time.monotonic()-self.last_paint<1:return
        cols,rows,width,height=size;factor=min(width/image.width,height/image.height)
        w,h=max(1,round(image.width*factor)),max(1,round(image.height*factor))
        left,top=(width-w)//2,(height-h)//2;self.mapping=(left,top,w,h,image.width,image.height)
        canvas=Image.new('RGB',(width,height),(12,12,12));canvas.paste(image.resize((w,h),Image.Resampling.LANCZOS),(left,top))
        png=io.BytesIO();canvas.save(png,format='PNG',compress_level=1);data=base64.b64encode(png.getvalue())
        ident=self.image_id+1 if self.shown!=self.image_id+1 else self.image_id+2;parts=[]
        for i in range(0,len(data),4096):
            more=int(i+4096<len(data));header=(f'a=T,U=1,f=100,q=2,C=1,i={ident},c={cols},r={rows},m={more}' if i==0 else f'm={more}').encode()
            parts.append(b'\x1b_G'+header+b';'+data[i:i+4096]+b'\x1b\\')
        # Keep the other buffer resident until it is reused. Deleting it here
        # can reach the terminal before tmux redraws the placeholder cells.
        # Keep tmux from emitting partially composed placeholder cells. Kitty
        # needs the complete row/column marks in the same terminal update.
        self.write(b'\x1b[?2026h'+b''.join(self.graphics(part) for part in parts)+grid(ident,cols,rows)+b'\x1b[?2026l');self.shown=ident;self.version=version;self.size=size;self.last_paint=time.monotonic()
    def mouse(self,code,col,row,release):
        left,top,w,h,sw,sh=self.mapping
        x=round(((col-.5)*self.cell_w-left)*sw/w);y=round(((row-.5)*self.cell_h-top)*sh/h)
        if not (0<=x<sw and 0<=y<sh):return
        button=code&3
        modifiers=tuple(key for bit,key in ((4,SHIFT),(8,ALT),(16,CTRL)) if code&bit)
        for key in modifiers:self.desktop.key(key,True)
        try:
            if code&64:
                if not release:
                    mask=1<<(3+button);self.desktop.pointer(x,y,self.buttons|mask);self.desktop.pointer(x,y,self.buttons)
            else:
                if not release and not code&32:self.intent=time.monotonic()
                if button==2 and not release and not code&32:self.sync() # context menu paste
                if not code&32:
                    if release:self.buttons&=~(1<<button)
                    elif button<3:self.buttons|=1<<button
                self.desktop.pointer(x,y,self.buttons)
        finally:
            for key in reversed(modifiers):self.desktop.key(key,False)
    def feed(self,data):
        self.buf+=data
        while self.buf:
            if self.paste:
                end=self.buf.find(b'\x1b[201~')
                if end<0:return True
                self.paste_text(self.buf[:end].decode('utf-8','replace'));self.buf=self.buf[end+6:];self.paste=False;continue
            if self.buf.startswith(b'\x1b[200~'):self.buf=self.buf[6:];self.paste=True;continue
            if self.buf.startswith(b'\x1b['):
                match=re.match(rb'\x1b\[<([0-9]+);([0-9]+);([0-9]+)([Mm])',self.buf)
                if match:
                    self.mouse(*map(int,match.groups()[:3]),match[4]==b'm');self.buf=self.buf[match.end():];continue
                match=re.match(rb'\x1b\[27;([0-9]+);([0-9]+)~',self.buf)
                if match:
                    mod,num=int(match[1])-1,int(match[2])
                    mods=tuple(v for bit,v in ((1,SHIFT),(2,ALT),(4,CTRL)) if mod&bit)
                    if num in (86,118) and mod&4:self.sync()
                    if mod&4 and num in (67,88,99,120):self.intent=time.monotonic()
                    self.desktop.press({9:0xff09,13:0xff0d,27:0xff1b,127:0xff08}.get(num,num),mods)
                    self.buf=self.buf[match.end():];continue
                match=re.match(rb'\x1b\[([0-9]+);([0-9]+)([ABCDHFu~])',self.buf)
                if match:
                    num,mod=int(match[1]),int(match[2])-1;end=match[3]
                    mods=tuple(v for bit,v in ((1,SHIFT),(2,ALT),(4,CTRL)) if mod&bit)
                    key={b'A':0xff52,b'B':0xff54,b'C':0xff53,b'D':0xff51,b'H':0xff50,b'F':0xff57}.get(end)
                    if end==b'u':key={9:0xff09,13:0xff0d,27:0xff1b,127:0xff08}.get(num,num)
                    if end==b'~':key=SPECIAL.get(f'\x1b[{num}~'.encode())
                    if key and (key in (86,118) and CTRL in mods and end==b'u' or end==b'~' and num==2 and mods==(SHIFT,)):self.sync()
                    if key and CTRL in mods and (key in (67,88,99,120) or end==b'~' and num==2):self.intent=time.monotonic()
                    if key:self.desktop.press(key,mods)
                    self.buf=self.buf[match.end():];continue
            unknown=re.match(rb'\x1b\[[0-?]*[ -/]*[@-~]',self.buf)
            if unknown and unknown[0] not in SPECIAL and unknown[0]!=b'\x1b[Z':
                self.buf=self.buf[unknown.end():];continue
            found=next((key for key in SPECIAL if self.buf.startswith(key)),None)
            if found:self.desktop.press(SPECIAL[found]);self.buf=self.buf[len(found):];continue
            if self.buf.startswith(b'\x1b[Z'):self.desktop.press(0xff09,(SHIFT,));self.buf=self.buf[3:];continue
            if self.buf.startswith(b'\x1b'):
                if len(self.buf)==1 or any(key.startswith(self.buf) for key in SPECIAL):return True
                if self.buf[1:2] in (b'[',b'O'):return True
                c=self.buf[1];self.desktop.press(c,(ALT,));self.buf=self.buf[2:];continue
            c=self.buf[0]
            if c==17:return False
            if c in (9,10,13,127):self.desktop.press({9:0xff09,10:0xff0d,13:0xff0d,127:0xff08}[c]);self.buf=self.buf[1:];continue
            if c==22:self.sync()
            if c in (3,24):self.intent=time.monotonic()
            if c<32:self.desktop.press(c+96,(CTRL,));self.buf=self.buf[1:];continue
            count=1 if c<128 else 2 if c<224 else 3 if c<240 else 4
            if len(self.buf)<count:return True
            self.desktop.text(self.buf[:count].decode('utf-8','replace'));self.buf=self.buf[count:]
        return True
    def run(self):
        saved=termios.tcgetattr(0);running=True
        def stop(*_):
            nonlocal running
            running=False
        for sig in (signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)
        try:
            tty.setraw(0);self.write(b'\x1b[?1049h\x1b[?25l\x1b[?1003h\x1b[?1006h\x1b[?2004h\x1b[2J\x1b[H')
            self.write(b'\x1b[16t');end=time.monotonic()+.2
            probe=b''
            while time.monotonic()<end:
                if select.select([0],[],[],.02)[0]:probe+=os.read(0,4096)
                match=re.search(rb'\x1b\[6;([0-9]+);([0-9]+)t',probe)
                if match:self.cell_h,self.cell_w=map(int,match.groups());break
            while running:
                if self.desktop.error:raise RuntimeError(str(self.desktop.error))
                self.render();self.drain_cuts()
                if select.select([0],[],[],.04)[0]:
                    data=os.read(0,65536)
                    if not data or not self.feed(data):break
                elif self.buf==b'\x1b':self.desktop.press(0xff1b);self.buf=b''
        finally:
            try:self.desktop.pointer(0,0,0)
            except OSError:pass
            try:
                for ident in (self.image_id+1,self.image_id+2):
                    self.write(self.graphics(f'\x1b_Ga=d,d=I,i={ident},q=2;\x1b\\'.encode()))
                self.write(b'\x1b[?1003l\x1b[?1006l\x1b[?2004l\x1b[?25h\x1b[?1049l')
            except OSError:pass
            finally:
                try:termios.tcsetattr(0,termios.TCSADRAIN,saved)
                except termios.error:pass

if __name__=='__main__':
    import json
    info=json.loads(os.environ['CHROME_VNC_INFO']);client=Desktop(info['host'],int(info['port']),info['password'])
    clipboard=Clipboard.from_env()
    try:View(client,clipboard=clipboard).run()
    finally:clipboard.close();client.close()
