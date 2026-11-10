import json,re,pathlib,hashlib
base=pathlib.Path('docs/deep-audit/verification');pr=json.loads((base/'codex-parent-query-all-text-recheck-latest.json').read_text());raws={}
for sid,day in [('01a116cf-f6c4-7361-9891-935e9b2d3479','07'),('01a11d10-ce96-7561-9e33-a15feb94b01e','08')]:
 p=next(pathlib.Path('/home/scriptkid/.codex/sessions/2026/10/'+day).glob('*'+sid+'*.jsonl'));raws[sid]=[json.loads(z) for z in p.open()]
def strings(v):
 if isinstance(v,str):
  yield v
  try:d=json.loads(v)
  except Exception:return
  if isinstance(d,(dict,list)):yield from strings(d)
 elif isinstance(v,dict):
  for x in v.values():yield from strings(x)
 elif isinstance(v,list):
  for x in v:yield from strings(x)
result=[]
for item in pr['changed_files']:
 p=pathlib.Path(item['path'])
 if p.name!='review.txt':continue
 fs=json.loads(p.with_name('fields.json').read_text());s=p.read_bytes().decode();ms=list(re.finditer(r'\n===== DISPLAY (\d+) SOURCE LINE',s));parts=[];fixed=[]
 sid=next(k for k in raws if k in str(p))
 for j,m in enumerate(ms):
  i=int(m[1]);f=fs[i];end=ms[j+1].start() if j+1<len(ms) else len(s);t=s[m.start():end];need=f['range'][1]-f['range'][0]-len(t)
  if need:
   candidates=list(strings(raws[sid][f['source_line']-1].get('payload')));positions=set()
   for z in candidates:
    if '\r' not in z:continue
    norm=z.replace('\r\n','\n').replace('\r','\n');at=t.find(norm)
    if at<0:continue
    off=0;k=0
    while k<len(z):
     if z[k:k+2]=='\r\n':positions.add(at+off);k+=2;off+=1
     else:k+=1;off+=1
   assert len(positions)==need,(p.name,i,need,len(positions))
   for at in sorted(positions,reverse=True):t=t[:at]+'\r'+t[at:]
   fixed.append({'display':i,'CRLF_restored':need,'expected_presentation_matches':hashlib.sha256(t.encode()).hexdigest()==f.get('presentation_sha256')})
  parts.append(t)
 repaired=''.join(parts);assert len(repaired)==fs[-1]['range'][1]
 p.write_bytes(repaired.encode());result.append({'path':str(p),'fields':fixed,'chars':len(repaired),'sha256':hashlib.sha256(repaired.encode()).hexdigest()})
(base/'codex-query-coordinate-repair.json').write_text(json.dumps({'reason':'Python universal-newline normalization during exact-value scan; CRLF restored from exact raw nested strings without restoring credential values.','files':result},indent=2));print(json.dumps([{'path':x['path'],'fields_restored':len(x['fields'])} for x in result]))
