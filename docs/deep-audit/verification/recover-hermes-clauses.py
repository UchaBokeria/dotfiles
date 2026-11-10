from pathlib import Path
import json,re,sqlite3,hashlib
D=Path('docs/deep-audit');rows=json.loads((D/'hermes-infra-coverage.json').read_text());c=sqlite3.connect('file:/home/scriptkid/.local/share/opencode/opencode.db?mode=ro',uri=True)
# Recover operation/intent around conservative whole-line omissions. Actual values remain withheld.
rx=re.compile(r'''(?ix)(?:[A-Z0-9_]*(?:API_KEY|TOKEN|PASSWORD|SECRET|PASSWD|AUTHKEY)[A-Z0-9_]*|apiKey|api_key|password|passwd|pwd|pass|client_secret|authorization|LLM_[A-Z0-9_]*)["'` ]*\s*(?:=|:)\s*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s;,}\]]+)''')
opaque=re.compile(r'(?<![A-Za-z0-9])[A-Za-z0-9_./+-]{28,}(?:={0,2})')
secrets=[]
# Known short inline credential shapes are collected only in memory, never stored.
for r in rows:
 if r.get('display_index') not in (469,488):continue
 d=json.loads(c.execute('select data from part where id=?',(r['part_id'],)).fetchone()[0])
 for text in [d.get('state',{}).get('input',{}).get('content',''),d.get('state',{}).get('input',{}).get('newString','')]:
  for m in re.finditer(r'(?i)VNC password[^\n]*?(?:printed|log)\s*\(?`([^`]+)`',text):
   if 5<=len(m[1])<=20:secrets.append(m[1])
def safe(s):
 for x in secrets:s=s.replace(x,'[CREDENTIAL VALUE WITHHELD]')
 s=re.sub(r'https?://api\.telegram\.org/bot[^/\s"\']+', 'https://api.telegram.org/bot[CREDENTIAL WITHHELD]',s)
 s=re.sub(r'https?://[^/\s:]+:[^/\s]+@','[URL USERINFO WITHHELD]@',s)
 s=re.sub(r'(?i)(sshpass\s+-p\s+)(?:"[^"]*"|\'[^\']*\'|\S+)',r'\1[CREDENTIAL WITHHELD]',s)
 s=rx.sub(lambda m:re.split(r'\s*(?:=|:)\s*',m[0],maxsplit=1)[0]+'=[VALUE SPAN WITHHELD]',s)
 s=re.sub(r'(?i)(authorization\s*:\s*bearer\s+)\S+',r'\1[VALUE WITHHELD]',s)
 s=opaque.sub('[LONG OPAQUE OR SOURCE TOKEN WITHHELD]',s)
 return s
out=[];seen={};ledger=[]
for r in rows:
 if not r.get('withheld'):continue
 d=json.loads(c.execute('select data from part where id=?',(r['part_id'],)).fetchone()[0])
 for e in r['withheld']:
  v=d
  try:
   for k in e['location'].split('/')[1:]:v=v[int(k)] if isinstance(v,list) else v[k]
  except (KeyError,IndexError,TypeError):
   ledger.append({'part_id':r['part_id'],'location':e['location'],'status':'unresolved-projection-location'});continue
  if e['mechanism']=='private-key-block' or not isinstance(v,str):
   ledger.append({'part_id':r['part_id'],'location':e['location'],'status':'credential-value-structural-classification'});continue
  if 'line' in e:
   ls=v.splitlines();v=ls[e['line']-1] if e['line']<=len(ls) else ''
  else:v='[ENTIRE CREDENTIAL FIELD VALUE WITHHELD]'
  sha=hashlib.sha256(v.encode()).hexdigest();s=safe(v)
  if sha in seen:idx=seen[sha]
  else:idx=len(out);seen[sha]=idx;out.append(f'RECOVERY {idx} display={r.get("display_index")} part={r["part_id"]} location={e["location"]} line={e.get("line")}\n{s}\n')
  ledger.append({'part_id':r['part_id'],'location':e['location'],'line':e.get('line'),'source_line_sha256':sha,'recovery_index':idx,'status':'pending-sanitized-clause-read'})
(D/'verification/hermes-infra-recovery.txt').write_text('\n'.join(out));(D/'hermes-infra-recovery.json').write_text(json.dumps(ledger,indent=2)+'\n');print('Recovery unique',len(out),'chars',sum(map(len,out)),'unresolved',sum(x['status'].startswith('unresolved') for x in ledger))
