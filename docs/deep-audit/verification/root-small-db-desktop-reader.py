import pathlib,json,sys
p=pathlib.Path('docs/deep-audit');f=p/'root-small-db-desktop.json';a=json.loads(f.read_text());last=p/'verification/root-small-db-desktop-last-batch.json'
if len(sys.argv)>1 and sys.argv[1]=='commit' and last.exists():
 for span in json.loads(last.read_text()):
  x=next(x for x in a if x['display_index']==span['index']);assert x['reviewed_chars']==span['start'];x['reviewed_chars']=span['end'];x['status']='read'if span['end']==len(x['review_text'])else'pending'
 f.write_text(json.dumps(a,ensure_ascii=False,indent=2))
budget=22000;spans=[]
for x in a:
 if x['status']=='read':continue
 start=x['reviewed_chars'];end=min(start+budget,len(x['review_text']));s=x['review_text'][start:end];header='DISPLAY '+str(x['display_index'])+' PART '+x['part_id']+' RANGE '+str(start)+':'+str(end)+'/'+str(len(x['review_text']))+'\n';print(header+s);budget-=len(s)+len(header);spans.append({'index':x['display_index'],'start':start,'end':end})
 if budget<=100:break
last.write_text(json.dumps(spans));print('BATCH',spans)
