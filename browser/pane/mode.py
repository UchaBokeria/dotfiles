#!/usr/bin/env python3
"""Pane-scoped browser input, with reversible tmux session defaults."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from lifetime import tm,start_id

TABLE='browser-pane'
HOOK=9348
KEYS=('prefix','prefix2','key-table','assume-paste-time')

def queue(commands):
    argv=[]
    for command in commands:
        if argv:argv.append(';')
        argv.extend(command)
    if argv:tm(*argv,check=False)
@contextmanager
def lock():
    root=Path.home()/'.cache/browser-pane';root.mkdir(parents=True,exist_ok=True)
    identity=hashlib.sha256(os.environ.get('TMUX','').rsplit(',',2)[0].encode()).hexdigest()[:20]
    with (root/('input-'+identity+'.lock')).open('a') as fd:
        fcntl.flock(fd,fcntl.LOCK_EX);yield

def callback(action,extra=''):
    return shlex.join([sys.executable,str(Path(__file__).resolve()),action]) + (' '+extra if extra else '')

def install():
    if tm('show-options','-gsqv','@browser-mode-installed')=='1':return
    original=tm('list-keys','-T','prefix','Escape',check=False)
    tm('set-option','-s','@browser-mode-escape-backup',original)
    fallback=original.split(' Escape ',1)[-1].strip() if original else 'run-shell true'
    queue([
      ('bind-key','-T',TABLE,'Any','send-keys'),
      ('bind-key','-T',TABLE,'C-a','send-keys C-a ; switch-client -T '+TABLE+'-prefix'),
      ('bind-key','-T',TABLE+'-prefix','Escape','run-shell',callback('toggle','--pane "#{pane_id}" --client "#{client_name}"')),
      ('bind-key','-T',TABLE+'-prefix','C-a','send-keys C-a ; switch-client -T '+TABLE),
      ('bind-key','-T',TABLE+'-prefix','Any','send-keys ; switch-client -T '+TABLE),
      ('bind-key','-T','prefix','Escape','if-shell','-F','#{@browser-viewer}',
       'run-shell '+shlex.quote(callback('toggle','--pane "#{pane_id}" --client "#{client_name}"')),fallback),
    ])
    mouse=[]
    for action in ('Down','Up','Drag','DragEnd'):
        mouse.extend('Mouse'+action+str(button)+'Pane' for button in (1,2,3))
    mouse+=['WheelUpPane','WheelDownPane']
    mouse += [name+str(button)+'Pane' for name in ('SecondClick','DoubleClick','TripleClick') for button in (1,2,3)]
    for key in mouse:
        tm('bind-key','-T',TABLE,key,'if-shell','-F','#{@browser-viewer}',
           'select-pane -t = ; send-keys -M','select-pane -t =',check=False)
        tm('bind-key','-T',TABLE+'-prefix',key,
           'send-keys -M ; switch-client -T '+TABLE+'-prefix',check=False)
    for hook in ('after-select-pane','after-select-window','client-session-changed','client-attached',
                 'session-window-changed','window-pane-changed','after-kill-pane','pane-exited'):
        tm('set-hook','-g',f'{hook}[{HOOK}]','run-shell -b '+shlex.quote(callback('sync')))
    tm('set-option','-s','@browser-mode-installed','1')

def sync_locked():
    panes=tm('list-panes','-a','-F','#{pane_id}\t#{@browser-viewer}\t#{@browser-input}\t#{window_id}',check=False).splitlines()
    live=[];browser_windows=set()
    for row in panes:
        pane,owner,control,window=row.split('\t')
        if not owner:continue
        pid,_,started=owner.partition(':')
        if not started or start_id(pid)!=started:
            queue([('set-option','-pu','-t',pane,'@browser-viewer'),('set-option','-pu','-t',pane,'@browser-input')])
        else:live.append(pane);browser_windows.add(window)
    for row in tm('list-sessions','-F','#{session_id}\t#{pane_id}\t#{@browser-input}\t#{@browser-original-input}\t#{window_id}\t#{@browser-original-mouse}',check=False).splitlines():
        sid,pane,control,saved,window,saved_mouse=row.split('\t')
        if window in browser_windows:
            if not saved_mouse:
                original=tm('show-options','-qv','-t',sid,'mouse')
                tm('set-option','-t',sid,'@browser-original-mouse',json.dumps({'local':original}))
            if tm('show-options','-Av','-t',sid,'mouse')!='on':tm('set-option','-t',sid,'mouse','on')
        elif saved_mouse:
            snapshot=json.loads(saved_mouse)
            original=snapshot.get('local','') if isinstance(snapshot,dict) else snapshot
            tm('set-option','-t',sid,'mouse',original) if original else tm('set-option','-u','-t',sid,'mouse')
            tm('set-option','-u','-t',sid,'@browser-original-mouse')
        active=pane in live and control=='browser'
        if active and not saved:
            local={}
            for line in tm('show-options','-t',sid).splitlines():
                parts=shlex.split(line)
                if len(parts)==2 and parts[0] in KEYS:local[parts[0]]=parts[1]
            saved=json.dumps(local)
            queue([('set-option','-t',sid,'@browser-original-input',saved),
                   ('set-option','-t',sid,'prefix','None'),('set-option','-t',sid,'prefix2','None'),
                   ('set-option','-t',sid,'key-table',TABLE),('set-option','-t',sid,'assume-paste-time','0')])
            for client in tm('list-clients','-t',sid,'-F','#{client_name}').splitlines():tm('switch-client','-c',client,'-T',TABLE)
        elif not active and saved:
            local=json.loads(saved)
            commands=[]
            for key in KEYS:
                commands.append(('set-option','-t',sid,key,local[key]) if key in local else ('set-option','-u','-t',sid,key))
            commands.append(('set-option','-u','-t',sid,'@browser-original-input'));queue(commands)
            for client in tm('list-clients','-t',sid,'-F','#{client_name}').splitlines():tm('switch-client','-c',client,'-T',local.get('key-table','root'))
    if not live and tm('show-options','-gsqv','@browser-mode-installed')=='1':
        original=tm('show-options','-gsqv','@browser-mode-escape-backup')
        if original:subprocess.run(['tmux','source-file','-'],input=original+'\n',text=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:tm('unbind-key','-T','prefix','Escape',check=False)
        for hook in ('after-select-pane','after-select-window','client-session-changed','client-attached',
                     'session-window-changed','window-pane-changed','after-kill-pane','pane-exited'):
            tm('set-hook','-gu',f'{hook}[{HOOK}]',check=False)
        tm('set-option','-su','@browser-mode-installed',check=False)
        tm('set-option','-su','@browser-mode-escape-backup',check=False)

def sync():
    with lock():sync_locked()
def register(pane):
    with lock():
        install()
        queue([('set-option','-p','-t',pane,'@browser-viewer',str(os.getpid())+':'+start_id(os.getpid())),
               ('set-option','-p','-t',pane,'@browser-input','browser')])
        sync_locked()
def unregister(pane):
    with lock():
        queue([('set-option','-pu','-t',pane,'@browser-viewer'),('set-option','-pu','-t',pane,'@browser-input')])
        sync_locked()
def toggle(pane,client=''):
    with lock():
        if not tm('show-options','-pqv','-t',pane,'@browser-viewer',check=False):return
        value=tm('show-options','-pqv','-t',pane,'@browser-input')
        tm('set-option','-p','-t',pane,'@browser-input','tmux' if value=='browser' else 'browser')
        sync_locked()
        if client:tm('display-message','-c',client,'-d','1200',('Tmux controls' if value=='browser' else 'Browser controls')+' · Ctrl+A Esc toggles back',check=False)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action');p.add_argument('--pane',default='');p.add_argument('--client',default='');a=p.parse_args()
    if a.action=='toggle':toggle(a.pane,a.client)
    else:sync()
