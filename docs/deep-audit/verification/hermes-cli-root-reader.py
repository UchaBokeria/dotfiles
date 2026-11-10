from pathlib import Path
import json,hashlib,re,sys
L=Path('docs/deep-audit/hermes-cli-root-coverage.json');B=Path('docs/deep-audit/verification/hermes-cli-root-last-batch.json');rows=json.loads(L.read_text())
def merge(rs):
 out=[]
 for a,b in sorted(rs):
  if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
  else:out.append([a,b])
 return out
if len(sys.argv)>1 and sys.argv[1]in('commit','commit-only')and B.exists():
 for b in json.loads(B.read_text()):
  r=next(x for x in rows if x['path']==b['path']);raw=Path(r['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==b['raw_sha256'];s=raw.decode();r['reviewed_char_ranges']=merge(r.get('reviewed_char_ranges',[])+[b['range']]);r['status']='read-sanitized'if not s or r['reviewed_char_ranges']==[[0,len(s)]]else'partial-read';r['notes']='All and only explicit bounded ranges semantic source read; no package import; token-shaped omissions tracked per display';r.setdefault('display_reviews',[]).append(b)
 L.write_text(json.dumps(rows,indent=2)+'\n');B.unlink()
if len(sys.argv)>1 and sys.argv[1]=='commit-only':raise SystemExit(0)
meta=[];budget=4000;count=0
priority=['AGENTS.md','urllib_security.py','runtime_provider.py','runtime_provider_custom.py','plugin_isolation.py','model_switch.py','lifecycle.py','plugins_dispatch.py','pty_bridge.py','win_pty_bridge.py','pty_session.py','voice.py']
for r in sorted(rows,key=lambda x:(priority.index(Path(x['path']).name) if Path(x['path']).name in priority else len(priority),x['relative_path'])):
 if r['status']not in('pending','partial-read'):continue
 raw=Path(r['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['sha256'];s=raw.decode();rs=merge(r.get('reviewed_char_ranges',[]));start=0
 for a,b in rs:
  if a>start:break
  start=max(start,b)
 end=min([start+budget,len(s)]+[a for a,b in rs if a>start]);v,n=re.subn(r'(?<![A-Za-z0-9_])(?:sk-|ghp_|gsk_|LLM_)[A-Za-z0-9_./+\-=]{8,}','[TOKEN-SHAPED LITERAL OMITTED]',s[start:end]);m={'path':r['path'],'raw_sha256':r['sha256'],'range':[start,end],'display_sha256':hashlib.sha256(v.encode()).hexdigest(),'token_shape_omissions':n};meta.append(m);print(json.dumps(m));print(v);budget-=end-start;count+=1
 if budget<=0 or count>=12:break
B.write_text(json.dumps(meta,indent=2)+'\n');print('BATCH_FILES',len(meta))
