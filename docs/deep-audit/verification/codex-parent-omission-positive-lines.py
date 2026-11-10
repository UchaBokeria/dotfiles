import json,hashlib,collections
from pathlib import Path
p=Path(__file__).parent/'codex-frontier-v5-01a116cf-f6c4-7361-9891-935e9b2d3479';a=json.loads((p/'omission-recovery.json').read_text());t=(p/'omission-recovery-refined.txt').read_bytes().decode();v=(p/'review.txt').read_bytes().decode();fields=json.loads((p/'fields.json').read_text());index={}
for f in fields:
 if not f['status'].startswith('read-'):continue
 cursor=f['range'][0]
 for line in v[slice(*f['range'])].splitlines(True):
  if len(line)>8:index.setdefault(line,{'display':f['display'],'range':[cursor,cursor+len(line)],'sha256':hashlib.sha256(line.encode()).hexdigest()})
  cursor+=len(line)
chunks=[];off=0;proof=[]
for e in a:
 if e['status']!='pending-safe-context':continue
 lo,hi=e['refined_range']
 if hi<=176000:e['status']='read-sanitized-safe-context';e['read_refined_range']=[lo,hi];continue
 body=t[lo:hi];parts=[];run=[];runtext=[]
 def flush():
  global run,runtext
  s=''.join(runtext)
  if len(s)>300:
   proof.append({'entry':e['index'],'index':len(proof),'characters':len(s),'safe_span_sha256':hashlib.sha256(s.encode()).hexdigest(),'positive_line_refs':run});parts.append('[EXACT already-read safe lines, proof '+str(len(proof)-1)+', chars '+str(len(s))+']\n')
  else:parts.append(s)
  run=[];runtext=[]
 for line in body.splitlines(True):
  if line in index:run.append(index[line]);runtext.append(line)
  else:flush();parts.append(line)
 flush();view=''.join(parts);e['line_reduced_range']=[off,off+len(view)];e['line_reduced_sha256']=hashlib.sha256(view.encode()).hexdigest();off+=len(view);chunks.append(view)
(p/'omission-recovery-lines.txt').write_bytes(''.join(chunks).encode());(p/'omission-positive-line-proofs.json').write_text(json.dumps(proof,indent=2));(p/'omission-recovery.json').write_text(json.dumps(a,indent=2));print(json.dumps({'remaining_projection_chars':off,'positive_line_spans':len(proof),'original_unread_chars':len(t)-176000,'statuses':dict(collections.Counter(x['status'] for x in a))}))
