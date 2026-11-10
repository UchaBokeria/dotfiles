import json,pathlib,sys
p=pathlib.Path('docs/deep-audit');q=p/'remoteadb-session-coverage.jsonl';a=[json.loads(l) for l in q.read_text().splitlines()];last=p/'verification/remoteadb-last-batch.json'
if len(sys.argv)>1 and sys.argv[1]=='commit' and last.exists():
 for r in json.loads(last.read_text()):
  x=next(v for v in a if v['part_id']==r['part_id']);assert x['reviewed_chars']==r['start'];x['reviewed_chars']=r['end'];x['status']='read-sanitized' if r['end']==x['display_chars'] else 'pending'
 q.write_text(''.join(json.dumps(v)+'\n' for v in a));last.unlink()
remaining=25000;batch=[]
for x in a:
 if x['status']!='pending':continue
 s=pathlib.Path(x['display_path']).read_text();st=x['reviewed_chars'];end=min(len(s),st+remaining);print('\nDISPLAY',x['display_index'],'PART',x['part_id'],'RANGE',f'{st}:{end}/{len(s)}');print(s[st:end]);batch.append({'part_id':x['part_id'],'start':st,'end':end});remaining-=end-st
 if not remaining:break
last.write_text(json.dumps(batch));print('BATCH',len(batch))
