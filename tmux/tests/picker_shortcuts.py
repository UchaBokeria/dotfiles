#!/usr/bin/env python3
"""Real key dispatch: window numbers, workspace shortcuts and previous-workspace toggle."""
import fcntl,json,os,pty,select,struct,subprocess,tempfile,termios,time
from pathlib import Path
from contextlib import ExitStack
ROOT=Path(__file__).resolve().parents[1]

def main():
 with tempfile.TemporaryDirectory(prefix='tmux-shortcuts-') as folder, ExitStack() as cleanup:
  path=Path(folder);sock=str(path/'socket');state=path/'state.json'
  env={**os.environ,'TERM':'xterm-256color','TMUX_WORKSPACES_STATE':str(state)}
  def tm(*args):return subprocess.check_output(['tmux','-S',sock,*args],env=env,text=True).rstrip('\n')
  tm('-f','/dev/null','new-session','-d','-s','anchor','sleep 600');server=tm('display-message','-p','#{pid}')
  cleanup.callback(subprocess.run,['tmux','-S',sock,'kill-server'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  env['TMUX']=sock+','+server+',0';tm('set-option','-g','default-shell','/bin/sh');tm('set-option','-g','assume-paste-time','0')
  for n in range(1,10):tm('new-window','-d','-t','anchor:'+str(n),'sleep 600')
  for name in ('a2','b1','b2'):tm('new-session','-d','-s',name,'sleep 600')
  tm('new-window','-d','-t','b2:2','sleep 600');tm('split-window','-d','-t','b2:2','sleep 600')
  original=set(tm('list-panes','-a','-F','#{pane_id}:#{pane_pid}').splitlines())
  helper=str(ROOT/'scripts/workspaces.py')
  def call(action,**values):
   argv=[helper,action,'--pane',tm('display-message','-p','-t','anchor','#{pane_id}')]
   if 'client' in locals_context:argv+=['--client',locals_context['client'],'--pane',tm('list-clients','-F','#{pane_id}')]
   for k,v in values.items():argv+=['--'+k,str(v)]
   result=subprocess.run(argv,env=env,text=True,capture_output=True)
   assert result.returncode==0,(argv,result.stderr,result.stdout)
  locals_context={};call('init');call('layout',kind='custom')
  call('apply-name',workspace='general',kind='create',name='Personal',quiet='1')
  data=lambda:json.loads(state.read_text())
  personal=next(k for k,v in data()['workspaces'].items() if v['name']=='Personal')
  for name in ('b1','b2'):call('assign',session=name,destination=personal,quiet='1')
  call('apply-name',workspace=personal,kind='child',name='Nested',quiet='1')
  nested=next(k for k,v in data()['workspaces'].items() if v['name']=='Nested')
  conf=path/'keys.conf';conf.write_text((ROOT/'scripts/session-picker.conf').read_text().replace('~/.config/tmux/scripts/',str(ROOT/'scripts')+'/'))
  tm('source-file',str(conf));tm('set-option','-g','prefix','C-b')
  master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',42,160,0,0))
  proc=subprocess.Popen(['tmux','-S',sock,'attach-session','-t','anchor'],env=env,stdin=slave,stdout=slave,stderr=slave);os.close(slave)
  def drain(seconds=.15):
   end=time.monotonic()+seconds
   while time.monotonic()<end:
    if select.select([master],[],[],.01)[0]:
     try:os.read(master,262144)
     except OSError:return
  def wait(check):
   end=time.monotonic()+6
   while time.monotonic()<end:
    if check():return True
    drain(.05)
   return check()
  def key(value):os.write(master,value);drain()
  def current():return tm('list-clients','-F','#{session_name}:#{window_index}.#{pane_index}')
  def switch(name):tm('switch-client','-c',client,'-t',name);drain(.1);call('focus')
  def opened():
   tm('send-keys','-K','-c',client,'C-b','s')
   assert wait(lambda:tm('show-options','-pqv','-t',tm('list-clients','-F','#{pane_id}'),'@workspace-picker-pid').isdigit())
  try:
   drain(.5);client=tm('list-clients','-F','#{client_name}');locals_context['client']=client
   switch('b1');switch('b2');tm('select-window','-t','b2:2');tm('select-pane','-t','b2:2.1');call('focus');switch('anchor');switch('a2');switch('anchor')
   for n in '0123456789':
    tm('send-keys','-K','-c',client,'C-b',n)
    assert wait(lambda:current()=='anchor:'+n+'.0'),current()
   bindings=tm('list-keys')
   assert 'M-S-6' in bindings and 'M-S-2' not in bindings
   key(b'\x1b2');assert wait(lambda:current()=='b2:2.1'),current()
   key(b'\x1b1');assert wait(lambda:current()=='anchor:9.0'),current()
   print('PASS: Prefix 0-9 selects windows; Alt+numbers jumps workspace last focus.',flush=True)
   opened();pane=tm('list-clients','-F','#{pane_id}')
   def view():return tm('show-options','-pqv','-t',pane,'@workspace-active')
   key(b'^');assert wait(lambda:view()==personal)
   assert current()=='anchor:9.0'
   key(b'^');assert wait(lambda:view()=='general')
   assert current()=='anchor:9.0'
   key(b'\x022');assert wait(lambda:view()==personal)
   key(b'\x1b1');assert wait(lambda:view()==nested)
   key(b'^');assert wait(lambda:view()==personal)
   key(b'^');assert wait(lambda:view()==nested)
   assert current()=='anchor:9.0'
   key(b'q');assert wait(lambda:tm('show-options','-pqv','-t',pane,'@workspace-picker-open')!='1')
   drain(.5)  # Wait for the popup tty to close after its flags are cleared.
   key(b'\x1b^');assert wait(lambda:current()=='b2:2.1'),current()
   key(b'\x1b^');assert wait(lambda:current()=='anchor:9.0'),current()
   switch('a2');key(b'\x1b^');assert wait(lambda:current()=='b2:2.1'),current()
   key(b'\x1b^');assert wait(lambda:current()=='a2:0.0'),current()
   # Extended modifier encoding must dispatch the same action.
   tm('send-keys','-K','-c',client,'M-S-6')
   assert wait(lambda:current()=='b2:2.1'),current()
   key(b'\x1b^');assert wait(lambda:current()=='a2:0.0'),current()
   print('PASS: ^ browses without opening sessions; Alt+Shift+6 toggles saved session/window/pane.',flush=True)
   call('layout',kind='native');pane=tm('list-clients','-F','#{pane_id}');call('open',workspace='general')
   assert wait(lambda:tm('display-message','-p','-t',pane,'#{pane_mode}')=='tree-mode')
   key(b'^');assert wait(lambda:view()==personal)
   call('focus');assert current()=='a2:0.0'
   key(b'^');assert wait(lambda:view()=='general')
   call('focus');assert current()=='a2:0.0'
   key(b'q');assert wait(lambda:tm('display-message','-p','-t',pane,'#{pane_mode}')=='')
   key(b'^');assert current()=='a2:0.0'
   key(b'\x1b^');assert wait(lambda:current()=='b2:2.1'),current()
   assert set(tm('list-panes','-a','-F','#{pane_id}:#{pane_pid}').splitlines())==original
   assert tm('display-message','-p','#{pid}')==server
   print('PASS: native ^ browse toggle; outside ^ passes through; all pane/server identities retained.',flush=True)
  finally:
   tm('kill-server');proc.wait(timeout=5);os.close(master)

if __name__=='__main__':main()
