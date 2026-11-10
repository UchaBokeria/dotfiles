import json,pathlib,hashlib,subprocess,sys
p=pathlib.Path('docs/deep-audit');f=p/'opencode-desktop-edit-write-source-matches.jsonl';a=[json.loads(s) for s in f.read_text().splitlines()];ids=set([x['part_id'] for x in a if x['status']!='read'][:int(sys.argv[1])]);dpath=p/'opencode-desktop-write-deltas.jsonl';ds=[json.loads(s) for s in dpath.read_text().splitlines()]
for x in ds:
 if x['part_id'] in ids:
  ref=x['baseline_ref'];b=subprocess.check_output(['git','cat-file','blob',ref.split(':')[1]]) if ref.startswith('git:') else pathlib.Path(ref).read_bytes();assert hashlib.sha256(b).hexdigest()==x['baseline_sha256'];x['status']='read'
for x in a:
 if x['part_id'] in ids:x.update(status='read',review_method='Full sanitized unmatched source operands, action wrapper and output read; verified positive source fields inherited; full baseline plus complete delta for selected writes; omitted credential lines excluded. No action executed.')
f.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in a));dpath.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in ds));raw=p/'opencode-desktop-session-coverage.jsonl';r=[json.loads(s) for s in raw.read_text().splitlines()]
for x in r:
 if (x.get('representative') or x['part_id']) in ids:x.update(status='read',notes='Historical action full sanitized source operands/wrapper/output reviewed; verified source baselines and full deltas inherited where recorded in edit-write ledger. Credential omissions excluded; no action executed.')
raw.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in r));print('credited',len(ids))
c={x['part_id']:x for x in map(json.loads,(p/'opencode-desktop-session-content.jsonl').read_text().splitlines())};dm={x['part_id']:x for x in ds};g=[x for x in a if x['status']!='read'];total=0;shown=0
for i,x in enumerate(g):
 v=json.loads(json.dumps(c[x['part_id']]['content']));inp=v.get('input',{})
 if isinstance(inp,dict):
  for k in x.get('fields',{}):
   if k in inp:inp[k]='[SOURCE SEMANTICS INHERITED: verified positive baseline in per-field ledger]'
  if x['part_id'] in dm:
   z=dm[x['part_id']];inp['content']={'baseline_ref':z['baseline_ref'],'baseline_sha256':z['baseline_sha256'],'complete_delta':z['delta']}
 s=json.dumps(v,ensure_ascii=False)
 if total+len(s)>23500 and i:break
 print(i,x['part_id'],s);total+=len(s);shown+=1
print('DISPLAYED',shown,'CHARS',total,'REMAINING',len(g))
