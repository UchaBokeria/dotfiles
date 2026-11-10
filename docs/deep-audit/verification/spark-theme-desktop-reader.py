import pathlib,json,sys
p=pathlib.Path('docs/deep-audit');q=p/'spark-theme-desktop.json';r=json.loads(q.read_text());last=p/'verification/spark-theme-desktop-last-batch.json'
if len(sys.argv)>1 and sys.argv[1]=='commit' and last.exists():
 for z in json.loads(last.read_text()):
  x=next(x for x in r if x['display_index']==z['index']);assert x['reviewed_chars']==z['start'];x['reviewed_chars']=z['end'];x['status']='read-sanitized' if z['end']==x['chars'] else 'pending'
 q.write_text(json.dumps(r,indent=2)+'\n');last.unlink()
s=(p/'verification/spark-theme-session-v3/review.txt').read_text();budget=25000;batch=[]
for x in r:
 if x['status']!='pending':continue
 text=s[x['review_start']:x['review_end']];st=x['reviewed_chars'];en=min(len(text),st+budget);print('DISPLAY',x['display_index'],'RANGE',st,en,'OF',len(text));print(text[st:en]);batch.append({'index':x['display_index'],'start':st,'end':en});budget-=en-st
 if not budget:break
last.write_text(json.dumps(batch));print('BATCH',len(batch))
