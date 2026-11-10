import json,hashlib,difflib,collections,re
from pathlib import Path
p=Path(__file__).parent/'codex-frontier-v5-01a116cf-f6c4-7361-9891-935e9b2d3479'
a=json.loads((p/'fields.json').read_text());t=(p/'review.txt').read_bytes().decode();budget=12000;seg=[]
pos=[f for f in a if f['status'].startswith('read-') and f['range'][1]-f['range'][0]>1500 and '\x00' not in t[slice(*f['range'])]]
inv=collections.defaultdict(set)
for f in pos:
 for line in set(t[slice(*f['range'])].splitlines(True)):
  if len(line)>30:inv[line].add(f['display'])
for f in a:
 if f['status'] not in ('pending','partial'):continue
 start=f.get('next_offset',f['range'][0]);end=min(f['range'][1],start+budget);overlay=None
 if f['range'][1]-start>2500 and '\x00' not in t[slice(*f['range'])]:
  target=t[slice(*f['range'])];lines=target.splitlines(True);scores=collections.Counter()
  for line in set(lines):
   for idx in inv.get(line,()):
    if idx<f['display']:scores[idx]+=len(line)
  for idx,score in scores.most_common(3):
   if score<len(target)*.6:continue
   base=t[slice(*a[idx]['range'])];bl=base.splitlines(True);sm=difflib.SequenceMatcher(None,bl,lines,autojunk=False);ops=sm.get_opcodes();rebuilt=''.join(''.join(bl[i:j]) if tag=='equal' else ''.join(lines[k:l]) for tag,i,j,k,l in ops);assert rebuilt==target
   changes=[];proof=[]
   for tag,i,j,k,l in ops:
    proof.append([tag,i,j,k,l])
    if tag!='equal':changes.append(f'[{tag}: baseline lines {i}:{j}, target lines {k}:{l}]\n'+''.join('- '+x for x in bl[i:j])+''.join('+ '+x for x in lines[k:l]))
   view=f'\nDISPLAY {f["display"]} EXACT BASELINE+EVERY DELTA against read display {idx}; equal line spans inherited, all removed/new lines below.\n'+''.join(changes)
   if len(view)<len(target)*.6 and len(view)<=budget:
    od=p/'positive-deltas';od.mkdir(exist_ok=True);fp=od/f'{f["display"]}.json';metadata={'display':f['display'],'baseline':idx,'baseline_status':a[idx]['status'],'baseline_presentation_sha256':hashlib.sha256(base.encode()).hexdigest(),'target_presentation_sha256':hashlib.sha256(target.encode()).hexdigest(),'opcodes':proof,'delta_view':view,'status':'pending'};fp.write_text(json.dumps(metadata,indent=2));overlay={'proof':str(fp),'chars':len(view)};print(view,end='');end=f['range'][1];budget-=len(view);break
 if overlay is None:
  assets=json.loads((p/'embedded-images.json').read_text())
  hits=[r for r in assets if r['range'][0]<end and r['range'][1]>start]
  if hits:
   end=max(end,max(r['range'][1] for r in hits));parts=[];cursor=start
   for r in hits:
    left,right=r['range'];parts.append(t[cursor:max(cursor,left)]);parts.append('\n[ENCODED IMAGE STRUCTURAL ONLY; decoded SHA256='+r['decoded_sha256']+'; bytes='+str(r['bytes'])+'; visual disposition='+r['status']+'; exact span '+str(r['range'])+']\n');cursor=right
   parts.append(t[cursor:end]);view=''.join(parts);print(view,end='');budget-=len(view);f.setdefault('encoded_image_exclusions',[])
   for r in hits:
    if r not in f['encoded_image_exclusions']:f['encoded_image_exclusions'].append(r)
  else:print(t[start:end],end='');budget-=end-start
 seg.append({'display':f['display'],'start':start,'end':end,'full_end':f['range'][1],**({'positive_delta':overlay} if overlay else {})})
 if budget<=0:break
(p/'next-block.json').write_text(json.dumps(seg))

(p/'fields.json').write_text(json.dumps(a,indent=2))
