"""Per-window graphics leases and child lifetimes; never stop shared Chrome."""
from contextlib import contextmanager
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

def tm(*args,check=True):
    result=subprocess.run(['tmux',*args],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    if check and result.returncode:raise RuntimeError('The browser pane no longer exists')
    return result.stdout.rstrip('\n')
def start_id(pid):
    try:return Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split()[19]
    except OSError:return None

def parent_death():
    # Linux sends TERM to the viewer/tunnel even if its launcher is SIGKILLed.
    if sys.platform.startswith('linux'):
        parent=os.getppid();ctypes.CDLL(None).prctl(1,signal.SIGTERM)
        if os.getppid()!=parent:os.kill(os.getpid(),signal.SIGTERM)

def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.kill();process.wait()

class Lease:
    def __init__(self,pane):
        self.pane=pane;self.window=tm('display-message','-p','-t',pane,'#{window_id}')
        identity=os.environ['TMUX'].rsplit(',',1)[0]+':'+self.window
        root=Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))/'browser-pane'
        root.mkdir(parents=True,exist_ok=True)
        self.path=root/(hashlib.sha256(identity.encode()).hexdigest()[:24]+'.json')
        self.lock=self.path.with_suffix('.lock');self.owner=str(os.getpid())
        with self.state() as data:
            owners=data.setdefault('owners',{})
            for pid,started in list(owners.items()):
                if start_id(pid)!=started:owners.pop(pid)
            if not owners:
                # A dead launcher can leave a lease; retain the original value.
                data.setdefault('previous',tm('show-options','-wqv','-t',self.window,'allow-passthrough'))
            owners[self.owner]=start_id(os.getpid())
            tm('set-option','-w','-t',self.window,'allow-passthrough','on')
    @contextmanager
    def state(self):
        with self.lock.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            data=json.loads(self.path.read_text()) if self.path.exists() else {}
            yield data
            self.path.write_text(json.dumps(data))
    def alive(self):
        return tm('display-message','-p','-t',self.pane,'#{pane_id}',check=False)==self.pane
    def release(self):
        with self.state() as data:
            owners=data.setdefault('owners',{});owners.pop(self.owner,None)
            for pid,started in list(owners.items()):
                if start_id(pid)!=started:owners.pop(pid)
            if not owners:
                if tm('display-message','-p','-t',self.window,'#{allow-passthrough}',check=False)=='on':
                    value=data.get('previous','')
                    tm('set-option','-w','-t',self.window,'allow-passthrough',value,check=False) if value else tm('set-option','-wu','-t',self.window,'allow-passthrough',check=False)
                data.clear()
