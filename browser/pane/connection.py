#!/usr/bin/env python3
"""Wake/focus the existing Chrome; return connection data only to its owner."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

def prepare(url=None):
    subprocess.run(['systemctl','--user','start','cloud-chrome.service'],check=True)
    for attempt in range(50):
        try:
            urllib.request.urlopen('http://127.0.0.1:9222/json/version',timeout=2).close();break
        except OSError:
            import time
            time.sleep(.2)
    if url:
        if '://' not in url and not url.startswith('about:'):url='https://'+url
        req=urllib.request.Request('http://127.0.0.1:9222/json/new?'+urllib.parse.quote(url,safe=''),method='PUT')
        urllib.request.urlopen(req,timeout=10).close()
    env={**os.environ,'DISPLAY':':99'}
    subprocess.run([str(Path(__file__).resolve().parents[1]/'ensure-window.sh')],env=env,stdout=subprocess.DEVNULL,check=False)
    windows=subprocess.check_output(['xdotool','search','--onlyvisible','--class','Google-chrome'],env=env,text=True).splitlines()
    if windows:subprocess.run(['xdotool','windowactivate',windows[-1]],env=env,stdout=subprocess.DEVNULL,check=False)
    return {'host':'127.0.0.1','port':5900,'password':(Path.home()/'.config/.claude-chrome-vncpw.txt').read_text().strip()}

if __name__=='__main__':print(json.dumps(prepare(sys.argv[1] if len(sys.argv)>1 else None)))
