import json,hashlib
from pathlib import Path
p=Path(__file__).parent/'codex-frontier-v5-01a116cf-f6c4-7361-9891-935e9b2d3479';a=json.loads((p/'omission-recovery.json').read_text());t=(p/'omission-recovery.txt').read_bytes().decode();v=(p/'review.txt').read_bytes().decode();f=json.loads((p/'fields.json').read_text());chunks=[];off=0
H=lambda x:hashlib.sha256(x.encode()).hexdigest()
for e in a:
 if e['status']!='pending-safe-context':continue
 view=t[slice(*e['range'])];body=view.split('\n',2)[2][:-1];refs=[]
 def flatten(x,path='$'):
  if isinstance(x,dict):return '\n'.join(flatten(y,path+'.'+k) for k,y in x.items()) or path+' = {}'
  if isinstance(x,list):return '\n'.join(flatten(y,path+'['+str(i)+']') for i,y in enumerate(x)) or path+' = []'
  if isinstance(x,str) and len(x)>100:
   loc=v.find(x)
   if loc>=0:
    base=next((z for z in f if z['status'].startswith('read-') and z['range'][0]<=loc and loc+len(x)<=z['range'][1]),None)
    if base:
     r={'path':path,'display':base['display'],'range':[loc,loc+len(x)],'sha256':H(x)};refs.append(r);return path+' = [EXACT fully read substring display '+str(base['display'])+' SHA '+H(x)+']'
  return path+' = '+(x if isinstance(x,str) else json.dumps(x))
 try:d=json.loads(body)
 except:d=None
 if isinstance(d,(dict,list)):
  candidate=flatten(d)
  if len(candidate)<len(body):body='[Lossless JSON leaf projection; every key/leaf retained]\n'+candidate
  else:refs=[]
 view=f'\n===== OMISSION {e["index"]} source {e["source_line"]} =====\n'+body+'\n';e.update(refined_range=[off,off+len(view)],positive_substring_references=refs,refined_presentation_sha256=H(view));off+=len(view);chunks.append(view)
(p/'omission-recovery-refined.txt').write_bytes(''.join(chunks).encode());(p/'omission-recovery.json').write_text(json.dumps(a,indent=2));print('pending safe chars',off,'positive substring refs',sum(len(e.get('positive_substring_references',[])) for e in a))
