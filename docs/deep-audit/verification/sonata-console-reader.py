import pathlib,json,hashlib,sys
D=pathlib.Path('docs/deep-audit');P=D/'sonata-console-history-coverage.json';B=D/'verification/sonata-console-last-batch.json';s=(D/'verification/sonata-root/source.txt').read_text();x=json.loads(P.read_text())
if len(sys.argv)>1 and B.exists():
 for i,e in json.loads(B.read_text()):x[i]['reviewed_chars']=e;x[i]['status']='read-sanitized' if e==x[i]['read_range'][1]-x[i]['read_range'][0] else 'partial'
 P.write_text(json.dumps(x,indent=2)+'\n')
rem=24000;b=[]
for i,a in enumerate(x):
 t=s[slice(*a['read_range'])];assert hashlib.sha256(t.encode()).hexdigest()==a['sanitized_sha256'];assert hashlib.sha256(pathlib.Path(a['path']).read_bytes()).hexdigest()==a['sha256'];st=a['reviewed_chars'];en=min(len(t),st+rem)
 if en==st:continue
 print('\nDESIGN',i,a['relative_path'],'CHARS',st,en,'OF',len(t),'ABS',a['read_range'][0]+st,a['read_range'][0]+en,'\n'+t[st:en]);b.append([i,en]);rem-=en-st
 if rem<=0:break
B.write_text(json.dumps(b));print('BATCH',len(b))
