from pathlib import Path
import json,os,subprocess
repo=Path('/home/ricecheck/clone with spaces')
state=Path.home()/'.local/state/blackwall-installer/session.json'
assert Path('/tmp/blackwall-vm-apply.exit').read_text().strip()=='0'
assert (repo/'fixture-offline.done').exists()
assert (Path.home()/'.config/hypr').resolve()==repo/'hypr'
assert (Path.home()/'.config/.dotfiles/blackwall').resolve()==repo
assert state.exists() and json.loads(state.read_text())['state']=='pending'
assert not (repo/'fixture-session.done').exists()
assert 'session-finalize.py' in (repo/'hypr/lua/machine.lua').read_text()
bindir=Path.home()/'.local/bin';bindir.mkdir(parents=True,exist_ok=True)
probe=bindir/'hyprctl';probe.write_text('#!/bin/sh\nprintf \'[{"width":1280,"height":720}]\\n\'\n');probe.chmod(0o755)
env=dict(os.environ,HYPRLAND_INSTANCE_SIGNATURE='vm-fixture-session',WAYLAND_DISPLAY='wayland-fixture',PATH=str(bindir)+':'+os.environ['PATH'])
cmd=['python3',str(repo/'installer/helpers/session-finalize.py'),'run']
for _ in range(2):subprocess.run(cmd,env=env,check=True)
assert json.loads(state.read_text())['state']=='complete'
assert (repo/'fixture-session.done').read_text().count('session-run')==1
print('PASS: real wrapper bootstrap, engine apply, spaced checkout, canonical alias, machine block, pending queue, simulated first-login completion and idempotence')
steps=repo/'installer/data/steps.toml'
steps.write_text(steps.read_text()+'''\n[[step]]
id="fixture-required-fail"
title="Required failure"
run=["false"]
check="false"
optional=false
''')
with Path('/tmp/blackwall-vm-required-failure.log').open('w') as log:
 result=subprocess.run([str(repo/'install'),'--apply'],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
assert result.returncode!=0
print('PASS: required failure exits',result.returncode)
print(Path('/tmp/blackwall-vm-required-failure.log').read_text()[-2200:])
