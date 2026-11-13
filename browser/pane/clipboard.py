#!/usr/bin/env python3
"""Clipboard bridge between the viewer's machine and Chrome's :99 clipboard.

Library: Clipboard(source,sink).sync()/paste(text). CLI (remote helpers):
  clipboard.py read          -> JSON header line {"mime","sha"} + raw bytes, or {"mime":null}
  clipboard.py write MIME    -> stdin bytes into the :99 clipboard (UTF8_STRING|image/png)
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

CAP=32<<20
PEERS={'13.140.155.113','100.68.100.11','100.68.91.7'}
SOURCE_HELPER='~/.config/.dotfiles/blackwall/browser/pane/clipboard.py'
TYPES={'UTF8_STRING':'UTF8_STRING','text':'UTF8_STRING','text/plain':'UTF8_STRING','image/png':'image/png'}

def sha(data):return hashlib.sha256(data).hexdigest()
def run(cmd,data=None,timeout=1.5,env=None):
    try:return subprocess.run(cmd,input=data,capture_output=True,timeout=timeout,env=env)
    except (OSError,subprocess.SubprocessError):return None

def wayland_env():
    """Environment for wl-paste, falling back to the default session socket (tmux may lack it)."""
    env=dict(os.environ);runtime=env.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}'
    display=env.get('WAYLAND_DISPLAY') or 'wayland-1'
    if not (Path(runtime)/display).exists() and not Path(display).is_absolute():return None
    env.update(WAYLAND_DISPLAY=display,XDG_RUNTIME_DIR=runtime);return env
def local_read(timeout=1.2):
    """(mime,bytes) from the Wayland clipboard: image/png if any image is offered, else text."""
    env=wayland_env()
    if not env or not shutil.which('wl-paste',path=env.get('PATH')):return None
    end=time.monotonic()+timeout;left=lambda:max(.1,end-time.monotonic())
    listed=run(['wl-paste','--list-types'],timeout=left(),env=env)
    if not listed or listed.returncode:return None
    offered=listed.stdout.decode('utf-8','replace').split()
    if any(t.startswith('image/') for t in offered):
        got=run(['wl-paste','-t','image/png'],timeout=left(),env=env);mime='image/png'
    elif offered:
        got=run(['wl-paste','--no-newline','-t','text/plain;charset=utf-8'],timeout=left(),env=env)
        if not got or got.returncode or not got.stdout:got=run(['wl-paste','--no-newline'],timeout=left(),env=env)
        mime='text/plain'
    else:return None
    if not got or got.returncode or not got.stdout or len(got.stdout)>CAP:return None
    return mime,got.stdout

def connected():
    """True when this machine holds an established ssh connection to Blackwall."""
    out=run(['ss','-tnH','state','established','( dport = :22 )'],timeout=1)
    if not out or out.returncode:return False
    for line in out.stdout.decode().splitlines():
        parts=line.split()
        if parts and parts[-1].rsplit(':',1)[0].strip('[]').removeprefix('::ffff:') in PEERS:return True
    return False

def x_write(mime,data):
    """Own :99's CLIPBOARD with xclip (detached so it keeps serving the selection)."""
    target=TYPES.get(mime)
    if not target or len(data)>CAP or not shutil.which('xclip'):return False
    try:
        p=subprocess.Popen(['xclip','-selection','clipboard','-t',target,'-i'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env={**os.environ,'DISPLAY':':99'},start_new_session=True)
        threading.Thread(target=p.wait,daemon=True).start()
        p.stdin.write(data);p.stdin.close();return True
    except OSError:return False

class LocalSource:
    def read(self,timeout):return local_read(timeout)
    def close(self):pass
class LocalSink:
    def write(self,mime,data,timeout):return x_write(mime,data)
    def close(self):pass

class Ssh:
    """ssh with a viewer-owned ControlMaster, so repeated calls cost tens of milliseconds."""
    def __init__(self,host,identity=None,tag='x'):
        folder=Path.home()/'.cache/browser-pane';folder.mkdir(parents=True,exist_ok=True)
        self.host=host;self.control=str(folder/f'cm-{os.getpid()}-{tag}')
        self.base=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','ControlMaster=auto','-o',f'ControlPath={self.control}','-o','ControlPersist=120','-o','LogLevel=ERROR']
        if identity:self.base+=['-i',str(Path(identity).expanduser())]
    def run(self,command,data=None,timeout=1.5):return run([*self.base,self.host,command],data,timeout)
    def warm(self):threading.Thread(target=run,args=([*self.base,self.host,'true'],None,10),daemon=True).start()
    def close(self):run(['ssh','-o',f'ControlPath={self.control}','-O','exit',self.host],timeout=2)

class RemoteSource:
    def __init__(self,host,helper=SOURCE_HELPER):self.ssh=Ssh(host,tag='src');self.helper=helper;self.ssh.warm()
    def read(self,timeout):
        got=self.ssh.run(f'python3 {self.helper} read',timeout=timeout)
        if not got or got.returncode:self.ssh.warm();return None
        head,_,body=got.stdout.partition(b'\n')
        try:info=json.loads(head)
        except ValueError:return None
        return (info['mime'],body) if info.get('mime') and body else None
    def close(self):self.ssh.close()
class RemoteSink:
    def __init__(self,host,identity,folder):self.ssh=Ssh(host,identity,'sink');self.folder=folder;self.ssh.warm()
    def write(self,mime,data,timeout):
        got=self.ssh.run(f'python3 {self.folder}/clipboard.py write {TYPES.get(mime,mime)}',data,timeout)
        if not got or got.returncode:self.ssh.warm();return False
        return True
    def close(self):self.ssh.close()

class Clipboard:
    """Pull source -> :99 sink on paste intents; newest wins, unchanged content is never re-pushed."""
    def __init__(self,source=None,sink=None):
        self.source=source;self.sink=sink;self.last=None;self.echo=set()
    @classmethod
    def from_env(cls):
        """Wayland viewer (Arch): local source, ssh sink. Blackwall viewer: Arch source, local sink."""
        try:
            sink_info=json.loads(os.environ.get('CHROME_CLIP_SINK') or 'null')
            source=wayland_env() and shutil.which('wl-paste') and LocalSource()
            if not source:
                host=os.environ.get('CHROME_CLIP_SOURCE','archlinux')
                source=RemoteSource(host) if host and not sink_info else None
            sink=RemoteSink(sink_info['host'],sink_info.get('identity'),sink_info['dir']) if sink_info else LocalSink()
            return cls(source or None,sink)
        except (OSError,ValueError,KeyError):return cls()
    def remember(self,mime,data):
        self.last=sha(data)
        if mime=='text/plain':
            text=data.decode('utf-8','replace');self.echo={text,text.encode('utf-8').decode('latin-1'),text.encode('latin-1','replace').decode('latin-1')}
        else:self.echo=set()
    def sync(self,timeout=1.5):
        """Push the client's clipboard into :99 if it changed since the last push. Never raises."""
        try:
            if not self.source or not self.sink:return False
            end=time.monotonic()+timeout
            got=self.source.read(max(.2,end-time.monotonic()))
            if not got or sha(got[1])==self.last:return False
            if not self.sink.write(got[0],got[1],max(.2,end-time.monotonic())):return False
            self.remember(*got);return True
        except Exception:return False
    def paste(self,text):
        """Bracketed paste: put TEXT on the :99 clipboard. True when Ctrl+V can paste it."""
        try:
            data=text.encode('utf-8')
            if not self.sink or not data or len(data)>CAP or not self.sink.write('text/plain',data,1.5):return False
            self.remember('text/plain',data);return True
        except Exception:return False
    def is_echo(self,text):return text in self.echo
    def close(self):
        for side in (self.source,self.sink):
            try:side and side.close()
            except Exception:pass

def main(argv):
    if len(argv)==2 and argv[1]=='read':
        out=sys.stdout.buffer
        if not connected():out.write(b'{"mime":null,"reason":"not-connected"}\n');return 0
        got=local_read()
        if not got:out.write(b'{"mime":null}\n');return 0
        out.write(json.dumps({'mime':got[0],'sha':sha(got[1])}).encode()+b'\n'+got[1]);return 0
    if len(argv)==3 and argv[1]=='write' and argv[2] in TYPES:
        return 0 if x_write(argv[2],sys.stdin.buffer.read(CAP+1)) else 1
    sys.stderr.write(__doc__);return 2

if __name__=='__main__':sys.exit(main(sys.argv))
