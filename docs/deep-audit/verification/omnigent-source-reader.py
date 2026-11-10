from pathlib import Path
import json,hashlib,re,sys
LEDGER=Path('docs/deep-audit/omnigent-runtime-coverage.json')
BATCH=Path('docs/deep-audit/verification/omnigent-last-batch.json')
rows=json.loads(LEDGER.read_text())
def merge(rs):
 out=[]
 for a,b in sorted(rs):
  if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
  else:out.append([a,b])
 return out
if len(sys.argv)>1 and sys.argv[1]=='commit' and BATCH.exists():
 old=json.loads(BATCH.read_text());r=next(r for r in rows if r['path']==old['path'])
 assert r['sha256']==old['raw_sha256']==hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()
 r['reviewed_char_ranges']=merge(r.get('reviewed_char_ranges',[])+[old['range']]);s=Path(r['path']).read_text()
 r['status']='read-sanitized'if r['reviewed_char_ranges']==[[0,len(s)]]else'partial-read'
 r['notes']='All and only listed character ranges semantically read; token-shaped literal masking logged per display; package never imported'
 LEDGER.write_text(json.dumps(rows,indent=2)+'\n');BATCH.unlink()
candidates=sorted((r for r in rows if r['path'].endswith('.py')and r['status']in('pending','partial-read')),key=lambda r:({'cli.py':0,'host/connect.py':1,'runner/_entry.py':2,'server/auth.py':3}.get(r['relative_path'],4),r['relative_path']))
if not candidates:print('NO PYTHON PENDING');raise SystemExit
r=candidates[0];p=Path(r['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'];s=p.read_text();ranges=merge(r.get('reviewed_char_ranges',[]));start=0
for a,b in ranges:
 if a>start:break
 start=max(start,b)
end=min(start+24000,len(s));end=min([a for a,b in ranges if a>start]+[end]);raw=s[start:end]
safe,n=re.subn(r'(?:sk-|ghp_|gsk_|LLM_)[A-Za-z0-9_./+\-=]{8,}','[TOKEN-SHAPED LITERAL OMITTED]',raw)
meta={'path':r['path'],'raw_sha256':r['sha256'],'range':[start,end],'display_sha256':hashlib.sha256(safe.encode()).hexdigest(),'token_shape_omissions':n}
BATCH.write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta));print(safe)
