import sqlite3,json,pathlib,hashlib,re,base64,io
from PIL import Image
P=pathlib.Path('docs/deep-audit'); O=P/'verification/remoteadb';O.mkdir(exist_ok=True)
SID='ses_ee1fc8c8bffe2UuA1x2iEpmmTz'; c=sqlite3.connect('file:/home/scriptkid/.local/share/opencode/opencode.db?mode=ro',uri=True)
rows=c.execute('select id,message_id,data from part where session_id=? order by time_created,id',(SID,)).fetchall();manifest=json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode();assert hashlib.sha256(manifest).hexdigest()=='3d1443c13445ff55b6eda913a6724c9d8fbb58a6c6e320dfe7337dde7e370ec4'
secret=re.compile(r'''(?ix)(?:LLM_[A-Za-z0-9_-]+|sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]+|gsk_[A-Za-z0-9_-]+|-----BEGIN\s+(?:OPENSSH|RSA|EC|PRIVATE)|(?:password|passwd|passphrase|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|private[_ -]?key|client[_-]?secret|CF-Access-Client-(?:Secret|Id))\s*[=:]\s*\S+|(?:PASSWORD|TOKEN|SECRET|API_KEY)\s*=\s*\S+|https?://[^\s/@:]+:[^\s/@]+@|[?&](?:token|key|secret|auth|code)=[^&\s]+)''')
seen={};ledger=[];images=[];fields=[]
def safe(s):
 out=[]
 credential_extra=re.compile(r'''(?ix)(?:[\"']?(?:password|passwd|passphrase|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|private[_ -]?key|client[_-]?secret)[\"']?\s*[=:]\s*\S+|adb\s+pair\s+\S+\s+\d{6}|pairing\s+(?:code|PIN)\s*[=:]\s*\d+|Bearer\s+[A-Za-z0-9_.-]{12,})''')
 for line in s.splitlines():
  if secret.search(line) or credential_extra.search(line) or re.search(r'(?<![A-Za-z0-9])\d{6}(?![A-Za-z0-9])',line):out.append('[CREDENTIAL-SHAPED LINE OMITTED]')
  else:out.append(line)
 return '\n'.join(out)
def flatten(v,path='$'):
 if isinstance(v,dict):
  for k,x in v.items():
   if 'encrypt' in k.lower() or k in ('signature',):yield path+'.'+k,'[OPAQUE CRYPTOGRAPHIC FIELD CLASSIFIED]';continue
   yield from flatten(x,path+'.'+k)
 elif isinstance(v,list):
  for i,x in enumerate(v):yield from flatten(x,path+'['+str(i)+']')
 elif isinstance(v,str):
  if v.startswith('data:image/') and ';base64,' in v:
   b=base64.b64decode(v.split(';base64,',1)[1]);im=Image.open(io.BytesIO(b));im.load();sh=hashlib.sha256(b).hexdigest();images.append({'part_id':pid,'field':path,'sha256':sh,'bytes':len(b),'format':im.format,'size':list(im.size),'status':'pending-privacy-and-visual-review'});yield path,'[EMBEDDED IMAGE decodedSHA256='+sh+' dimensions='+str(im.size)+' separate private/visual review]'
  elif 'data:image/' in v:
   # No unhandled inline payload may enter the text view.
   yield path,'[INLINE IMAGE STRING WITHHELD pending structural review]'
  else:yield path,safe(v)
 else:yield path,json.dumps(v,ensure_ascii=False)
for n,(pid,mid,data) in enumerate(rows):
 obj=json.loads(data);typ=obj.get('type');entry={'session_id':SID,'part_id':pid,'message_id':mid,'raw_sha256':hashlib.sha256(data.encode()).hexdigest(),'raw_bytes':len(data.encode()),'type':typ}
 if typ in ('step-start','step-finish'):
  entry.update(status='generated-classified',notes='Lifecycle snapshot/cost/token bookkeeping; field keys/types inventoried separately, not assistant/tool content');ledger.append(entry);continue
 chunks=[];ranges=[];pos=0
 for field,value in flatten(obj):
  valuehash=hashlib.sha256(value.encode()).hexdigest();key=(type(value).__name__,value)
  if len(value)>100 and key in seen:display='[EXACT PREVIOUS SANITIZED FIELD '+str(seen[key])+']'
  else:
   display=value
   if len(value)>100:seen[key]={'part_id':pid,'field':field,'sanitized_sha256':valuehash}
  text=field+' = '+display+'\n';chunks.append(text);ranges.append({'field':field,'start':pos+len(field)+3,'end':pos+len(text)-1,'sanitized_value_sha256':valuehash,'reference':seen.get(key) if display!=value else None});pos+=len(text)
 text=''.join(chunks);i=len(fields);path=O/f'{i:03}.txt';path.write_text(text);entry.update(status='pending',display_index=i,display_path=str(path),display_sha256=hashlib.sha256(text.encode()).hexdigest(),field_ranges=ranges,display_chars=len(text),reviewed_chars=0);fields.append(entry);ledger.append(entry)
(P/'remoteadb-session-coverage.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in ledger));(P/'remoteadb-images.json').write_text(json.dumps(images,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'session_id':SID,'raw_parts':len(rows),'raw_tuple_bytes':len(manifest),'raw_tuple_sha256':hashlib.sha256(manifest).hexdigest(),'display_count':len(fields),'display_chars':sum(r['display_chars'] for r in fields),'unique_images':len({x['sha256'] for x in images}),'image_occurrences':len(images)},indent=2)+'\n');print((O/'manifest.json').read_text())
