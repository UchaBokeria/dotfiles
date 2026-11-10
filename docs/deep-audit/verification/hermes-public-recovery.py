from pathlib import Path
import json,sqlite3,re,hashlib
D=Path('docs/deep-audit');c=sqlite3.connect('file:/home/scriptkid/.local/share/opencode/opencode.db?mode=ro',uri=True);out=[];seen=set();ledger=[]
for r in json.loads((D/'hermes-infra-coverage.json').read_text()):
 if not r.get('withheld'):continue
 d=json.loads(c.execute('select data from part where id=?',(r['part_id'],)).fetchone()[0])
 if d.get('tool')!='webfetch':continue
 for e in r['withheld']:
  v=d
  for k in e['location'].split('/')[1:]:v=v[int(k)] if isinstance(v,list) else v[k]
  if not isinstance(v,str) or not e.get('line'):continue
  line=v.splitlines()[e['line']-1];sha=hashlib.sha256(line.encode()).hexdigest()
  # Public primary docs examples, keep placeholder configuration semantics; vendor/key shapes still withheld.
  s=re.sub(r'(?<![A-Za-z0-9])(?:LLM_|nvapi-|gsk_|sk-)[A-Za-z0-9_.-]+|[0-9]{8,12}:[A-Za-z0-9_-]{25,}','[CREDENTIAL-SHAPE WITHHELD]',line)
  if sha not in seen:out.append(f'PUBLIC {len(out)} display={r.get("display_index")} line={e["line"]}\n{s}\n');seen.add(sha)
  ledger.append({'part_id':r['part_id'],'location':e['location'],'line':e['line'],'source_line_sha256':sha,'status':'pending-public-line-read'})
(D/'verification/hermes-infra-public-recovery.txt').write_text('\n'.join(out));(D/'hermes-infra-public-recovery.json').write_text(json.dumps(ledger,indent=2)+'\n');print(len(out),sum(map(len,out)))
