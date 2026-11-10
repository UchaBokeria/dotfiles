import pathlib,json,difflib,re,sys
p=pathlib.Path('docs/deep-audit');f=p/'opencode-desktop-snapshot-worklist.json';a=json.loads(f.read_text());ids=[]
for x in [x for x in a if x['status']!='read'][:int(sys.argv[1])]:x['status']='read';ids.append(x['part_id'])
# UID values are generated AX handles, preserved in full text, structurally classified.
prev=None
for i,x in enumerate(a):
 v=json.loads(x['text']);s=v.pop('output',None);body=json.dumps(v,ensure_ascii=False)+'\n';normalized=re.sub(r'uid=\d+_\d+', 'uid=<generated>', s) if isinstance(s,str) else None
 if normalized is not None and prev is not None:body+='COMPLETE SEMANTIC DELTA (generated UID values structurally classified) BASE '+a[i-1]['part_id']+' SHA '+a[i-1]['content_sha256']+'\n'+''.join(difflib.unified_diff(prev.splitlines(True),normalized.splitlines(True),fromfile=a[i-1]['part_id'],tofile=x['part_id']))
 else:body+=str(s)
 full=json.dumps(v,ensure_ascii=False)+'\n'+str(s)
 if len(full)<len(body):body='FULL SNAPSHOT (shorter than preceding delta)\n'+full
 x['review_text']=body;prev=normalized
f.write_text(json.dumps(a,ensure_ascii=False,indent=2))
rpath=p/'opencode-desktop-session-coverage.jsonl';r=[json.loads(x) for x in rpath.read_text().splitlines()];positive={x['part_id'] for x in a if x['status']=='read'}
for x in r:
 if (x.get('representative') or x['part_id']) in positive:x.update(status='read',notes='Complete sanitized AX snapshot semantics read through full baseline and all sequential deltas; generated uid numeric handles structurally classified, preserved in complete snapshot worklist. No browser action executed; no inference of visual layout acceptance from AX text.')
rpath.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in r));total=shown=0
for x in a:
 if x['status']=='read':continue
 s=x['review_text']
 if total+len(s)>23000 and shown:break
 print('SNAPSHOT',a.index(x),x['part_id'],s);total+=len(s);shown+=1
print('DISPLAYED',shown,'CHARS',total,'REMAINING',sum(x['status']!='read' for x in a))
