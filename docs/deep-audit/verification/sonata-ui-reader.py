import pathlib,json,hashlib,sys
D=pathlib.Path('docs/deep-audit');P=D/'sonata-ui-coverage.jsonl';B=D/'verification/sonata-ui-last-batch.json'
if not P.exists():
 x=[dict(a, status='pending',reviewed_chars=0) for a in map(json.loads,(D/'sonata-source-coverage.jsonl').read_text().splitlines()) if a['owner']=='desktop_source'];P.write_text(''.join(json.dumps(a)+'\n' for a in x))
x=list(map(json.loads,P.read_text().splitlines()))
if len(sys.argv)>1 and B.exists():
 for j,end in json.loads(B.read_text()):
  x[j]['reviewed_chars']=end;x[j]['status']='read' if end==len(pathlib.Path(x[j]['path']).read_text()) else 'partial'
 P.write_text(''.join(json.dumps(a)+'\n' for a in x))
rem=24000;b=[]
for j,a in enumerate(x):
 s=pathlib.Path(a['path']).read_text();assert hashlib.sha256(s.encode()).hexdigest()==a['sha256'];start=a['reviewed_chars']
 if start==len(s):continue
 end=min(len(s),start+rem); print('\nFILE',j,a['relative_path'],'CHARS',start,end,'OF',len(s),'\n'+s[start:end]);b.append([j,end]);rem-=end-start
 if rem<=0:break
B.write_text(json.dumps(b));print('BATCH',len(b))
