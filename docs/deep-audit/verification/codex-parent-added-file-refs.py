import json,hashlib,collections
from pathlib import Path
p=Path(__file__).parent/'codex-frontier-v5-01a116cf-f6c4-7361-9891-935e9b2d3479';a=json.loads((p/'fields.json').read_text());t=(p/'review.txt').read_text();idx={}
for f in a:
 if not f['status'].startswith('read-'):continue
 body=t[slice(*f['range'])];needle='tools.apply_patch(';at=body.find(needle)
 if at<0:continue
 try:patch,_=json.JSONDecoder().raw_decode(body[at+len(needle):])
 except (ValueError,TypeError):continue
 if not isinstance(patch,str):continue
 lines=patch.splitlines(True);i=0
 while i<len(lines):
  if not lines[i].startswith('*** Add File: '):i+=1;continue
  path=lines[i].strip()[14:];i+=1;out=[]
  while i<len(lines) and not lines[i].startswith('*** '):
   if lines[i].startswith('+'):out.append(lines[i][1:])
   else:break
   i+=1
  content=''.join(out)
  for value in (content,content[:-1] if content.endswith('\n') else content):idx[hashlib.sha256(value.encode()).hexdigest()]={'baseline_patch_display':f['display'],'baseline_status':f['status'],'added_path':path,'source_chars':len(value),'source_sha256':hashlib.sha256(value.encode()).hexdigest(),'method':'JSON string decoded inertly from full-read apply_patch input; exact Add File plus-prefix removed; optional terminal LF identity checked'}
proof=[]
for f in a:
 if f['status'] not in ('pending','partial'):continue
 if f['raw_string_sha256'] in idx:
  d={'display':f['display'],'source_line':f['source_line'],'field':f['field'],**idx[f['raw_string_sha256']]};proof.append(d);f['status']='read-exact-added-file-from-read-patch';f['exact_added_file_proof']=d
(p/'fields.json').write_text(json.dumps(a,indent=2));q=p/'all-added-file-refs.json';old=json.loads(q.read_text()) if q.exists() else [];q.write_text(json.dumps(old+proof,indent=2));g=json.loads((p/'progress.json').read_text());g['statuses']=dict(collections.Counter(f['status'] for f in a));f=next(f for f in a if f['status'] in ('pending','partial'));g['next_display']=f['display'];g['next_character_offset']=f.get('next_offset',f['range'][0]);(p/'progress.json').write_text(json.dumps(g,indent=2));print('new exact refs',len(proof),'chars',sum(d['source_chars'] for d in proof),'next',f['display'])
