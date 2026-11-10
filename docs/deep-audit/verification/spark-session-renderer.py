SID='ses_f20d082b3ffeqnsuw6bvqnFnBZ'
import json,pathlib,re,hashlib,sqlite3,difflib
c=sqlite3.connect('file:/home/scriptkid/.local/share/opencode/opencode.db?mode=ro',uri=True)
led=[json.loads(x) for x in pathlib.Path('docs/deep-audit/history-coverage.jsonl').read_text().splitlines()]
positive={}
def collect(v,loc):
 if isinstance(v,dict):
  for k,x in v.items():
   if k not in ('signature','encrypted_content','data'):collect(x,loc+'/'+k)
 elif isinstance(v,list):
  for i,x in enumerate(v):collect(x,loc+'/'+str(i))
 elif isinstance(v,str) and len(v)>1000:positive.setdefault(v,loc)
for e in led:
 if e['status']!='read':continue
 p=e['path']
 if p.startswith('sqlite:opencode.db:session:'):
  for i,d in c.execute('select id,data from part where session_id=?',(p.split(':')[-1],)):collect(json.loads(d),p+':'+i)
 elif p.startswith('/home/scriptkid/.claude/') and p.endswith('.jsonl') and pathlib.Path(p).is_file():
  for n,l in enumerate(pathlib.Path(p).read_text().splitlines(),1):
   try:o=json.loads(l)
   except:continue
   if o.get('type') in ('user','assistant'):collect(o.get('message',{}),p+':'+str(n))
# Exact text representatives from positively reviewed file/blob records, verified anew.
import subprocess
knownsha=set()
for e in led:
 if e['status']!='read' or not isinstance(e.get('sha256'),str) or e.get('bytes',0) is None or e.get('bytes',0)>1000000:continue
 p=e['path']
 if p.startswith('sqlite:') or p.startswith('archive-'):continue
 try:
  if p.startswith('git:'):
   oid=p.split(':')[1]
   if not re.fullmatch('[0-9a-f]{40}',oid):continue
   data=subprocess.check_output(['git','cat-file','blob',oid],stderr=subprocess.DEVNULL)
  else:
   q=pathlib.Path(p)
   if not q.is_file():continue
   data=q.read_bytes()
  sha=hashlib.sha256(data).hexdigest()
  if sha!=e['sha256'] or sha in knownsha:continue
  knownsha.add(sha);txt=data.decode()
  if len(txt)>1000:positive.setdefault(txt,p+' verified-sha256='+sha)
 except (OSError,UnicodeError,subprocess.SubprocessError):continue
def redact(s):
 s=re.sub(r'(?i)(\\?"(?:password|apiKey|access_token|refresh_token|key)\\?"\s*:\s*\\?")[^"\\\s]+',r'\1[REDACTED]',s)
 s=re.sub(r'(?:LLM_|sk-|gh[pousr]_|gsk_|nvapi-|wk-)[A-Za-z0-9_.-]+','[REDACTED]',s)
 s=re.sub(r'(?i)(authorization:\s*bearer\s+)[^\s"\\]+',r'\1[REDACTED]',s)
 s=re.sub(r'(?i)((?:password|passwd)\s+(?:set to|is|=)\s*)[^\s,;]+',r'\1[REDACTED]',s)
 s=re.sub(r'(?i)([?&](?:token|edge_token)=[^&\s"\\]*)','[REDACTED QUERY TOKEN]',s)
 s=re.sub(r'(?i)(still has\s+)[A-Za-z0-9_-]{8,}',r'\1[REDACTED]',s)
 s=re.sub(r'(?i)(PASSWORD=)[^\s\\";]+',r'\1[REDACTED]',s)
 return s
local_strings={}
def replace(v):
 if isinstance(v,str) and v.startswith('data:image/') and ';base64,' in v:
  import base64
  b=base64.b64decode(v.split(';base64,',1)[1]);return '[EMBEDDED IMAGE separate visual review; decodedbytes='+str(len(b))+' sha256='+hashlib.sha256(b).hexdigest()+']'
 if isinstance(v,str) and v in positive:return '[EXACT FULLY-READ '+positive[v]+' sha256='+hashlib.sha256(v.encode()).hexdigest()+']'
 if isinstance(v,str) and '<content>\n' in v:
  pre,body=v.split('<content>\n',1);body,sep,tail=body.partition('</content>')
  ls=body.splitlines();ns=[re.match(r'^(\d+): (.*)$',l) for l in ls];src='\n'.join(m[2] for m in ns if m)
  for candidate in (src,src+'\n'):
   if candidate in positive:
    return pre+'<content>[EXACT numbered source '+positive[candidate]+' sha256='+hashlib.sha256(candidate.encode()).hexdigest()+']</content>'+tail+' NONNUMBERED '+repr([l for l,m in zip(ls,ns) if not m])
 if isinstance(v,str) and '<content>\n' in v and len(src)>1000:
  for full,loc in positive.items():
   if src in full:
    return pre+'<content>[EXACT SOURCE FRAGMENT fully-read '+loc+' fragment-sha256='+hashlib.sha256(src.encode()).hexdigest()+']</content>'+tail+' NONNUMBERED '+repr([l for l,m in zip(ls,ns) if not m])
 if isinstance(v,str) and len(v)>10000:
  matches=[(full,loc) for full,loc in positive.items() if full[:1000]==v[:1000] and len(full)>1000]
  best=None
  for full,loc in matches:
   lo,hi=1000,min(len(full),len(v))
   while lo<hi:
    m=(lo+hi+1)//2
    if full[:m]==v[:m]:lo=m
    else:hi=m-1
   prelen=lo;suflen=0;lo,hi=0,min(len(full)-prelen,len(v)-prelen)
   while lo<hi:
    m=(lo+hi+1)//2
    if full[-m:]==v[-m:]:lo=m
    else:hi=m-1
   suflen=lo
   if best is None or prelen+suflen>best[0]+best[1]:best=(prelen,suflen,full,loc)
  if best and best[0]+best[1]>len(v)*.7:
   prelen,suflen,full,loc=best;end=len(v)-suflen
   return '[EXACT fully-read prefix chars='+str(prelen)+' and suffix chars='+str(suflen)+' representative='+loc+' targetsha256='+hashlib.sha256(v.encode()).hexdigest()+'] MIDDLE EVERY CHANGED CHAR:\n'+v[prelen:end]
 if isinstance(v,str) and len(v)>1000:
  sh=hashlib.sha256(v.encode()).hexdigest()
  if sh in local_strings:return '[EXACT earlier string '+sh+']'
  local_strings[sh]=1
 if isinstance(v,dict):return {k:replace(x) for k,x in v.items() if k not in ('signature','encrypted_content') and 'encrypt' not in k.lower()}
 if isinstance(v,list):return [replace(x) for x in v]
 return v
out=[];seen={};stats={}
for i,mid,data in c.execute('select id,message_id,data from part where session_id=? order by time_created,id',(SID,)):
 d=json.loads(data);t=d.get('type');stats[t]=stats.get(t,0)+1
 if t in ('step-start','step-finish'):continue
 if t=='tool':
  st=d.get('state',{})
  if isinstance(st.get('metadata'),dict):
   for k in list(st['metadata']):
    if k in ('output','preview') and st['metadata'][k]==st.get('output'):st['metadata'][k]='[EXACT duplicate state.output]'
 for k in ('id','sessionID','messageID','callID'):d.pop(k,None)
 s=json.dumps(replace(d),ensure_ascii=False,sort_keys=True)
 if s in seen:out.append(i+' [EXACT same-session part '+seen[s]+']');continue
 seen[s]=i;out.append(i+' '+redact(s))
z='\n'.join(out)

# Conservative final line projection; actual token values never copied.
def strict(text):
 text=re.sub(r'data:image/[^;\s]+;base64,[A-Za-z0-9+/=]+','[EMBEDDED IMAGE inline; separate structural/visual frontier]',text)
 text=re.sub(r'(?i)(https?://)[^/@\s:]+:[^/@\s]+@',r'\1[WITHHELD USERINFO]@',text)
 text=re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~-]{10,}',r'\1[WITHHELD]',text)
 return text
z=strict(z)
root=pathlib.Path('docs/deep-audit/verification/spark-theme-session');root.mkdir(exist_ok=True)
# Expand JSON string escapes as decoded fields, retain complete bookkeeping.
records=[]
for row in z.splitlines():
 pid,_,body=row.partition(' ')
 try:d=json.loads(body)
 except:d=body
 records.append({'part_id':pid,'content':d})
(root/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
manifestrows=list(c.execute('select id,message_id,data from part where session_id=? order by time_created,id',(SID,)))
encoded=json.dumps(manifestrows,ensure_ascii=False,separators=(',',':')).encode()
assert len(encoded)==3142673 and hashlib.sha256(encoded).hexdigest()=='84e0c6715536d061485fac4dc1ba09884c6032a5ba5fe3a0743916bb8b2934f9'
manifest={'session_id':SID,'raw_parts':len(manifestrows),'bytes':len(encoded),'sha256':hashlib.sha256(encoded).hexdigest(),'types':stats,'supplied_representatives':len(records),'sanitized_chars':len(z),'status':'pending-semantic-read'}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))
