from pathlib import Path
import json,re,hashlib,sqlite3,datetime
SID='ses_eec9ae45cffeoFEz5dTk7a1295'
D=Path('docs/deep-audit');dest=D/'verification/hermes-infra';dest.mkdir(exist_ok=True)
source=(D/'verification/history-sqlite-renderer.py').read_text();source=source[:source.index("out=[];seen={};stats={}")]
ns={};exec(compile(source,'reviewed-history-renderer','exec'),ns)
redacted=[]
secretkey=re.compile(r'(?i)^(?:password|passwd|pwd|pass|client[_-]?secret|api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|authorization|secret|token|private[_-]?key|llm_[a-z0-9_]*)$')
secretline=re.compile(r'(?i)(?:sshpass|LLM_[A-Z0-9_]*|(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|passwd|pwd|authorization|auth[_-]?token|[A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET)[A-Z0-9_]*)[\"\x27` ]*\s*(?:=|:)|\bpass\s*(?:=|:)\s*|https?://[^/\s:]+:[^/\s]+@)')
oldredact=ns['redact']
def clean(v,loc):
 if isinstance(v,dict):
  out={}
  for k,x in v.items():
   if secretkey.match(k) and x is not None:
    out[k]='[CREDENTIAL-SHAPED FIELD VALUE WITHHELD]';redacted.append({'location':loc+'/'+k,'mechanism':'credential-shaped-field'})
   else:out[k]=clean(x,loc+'/'+k)
  return out
 if isinstance(v,list):return [clean(x,loc+'/'+str(i)) for i,x in enumerate(v)]
 if not isinstance(v,str):return v
 if re.search(r'-----BEGIN [^-]*PRIVATE KEY-----',v):
  redacted.append({'location':loc,'mechanism':'private-key-block'});return '[PRIVATE KEY BLOCK WITHHELD]'
 out=[]
 for i,line in enumerate(v.splitlines(keepends=True),1):
  if secretline.search(line) or re.search(r"api\.telegram\.org/bot[0-9]+:[A-Za-z0-9_-]+",line) or re.search(r"(?i)VNC password.*(?:printed|log)",line):
   redacted.append({'location':loc,'line':i,'mechanism':'credential-shaped-assignment-or-shell-auth-line'});out.append('[CREDENTIAL-SHAPED LINE WITHHELD]\n')
  else:out.append(oldredact(line))
 return ''.join(out)
def flatten(v,loc='$'):
 if isinstance(v,dict):return '\n'.join(flatten(x,loc+'.'+k) for k,x in v.items())
 if isinstance(v,list):return '\n'.join(flatten(x,loc+'['+str(i)+']') for i,x in enumerate(v))
 return loc+' = '+(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False))
rows=[];seen={};count=0
for part,mid,data in ns['c'].execute('select id,message_id,data from part where session_id=? order by time_created,id',(SID,)):
 d=json.loads(data);t=d.get('type');row={'session_id':SID,'part_id':part,'message_id':mid,'type':t,'raw_sha256':hashlib.sha256(data.encode()).hexdigest(),'raw_bytes':len(data.encode())}
 if t in ('step-start','step-finish'):
  row['status']='generated-structural';row['shape']={k:type(v).__name__ for k,v in d.items()};rows.append(row);continue
 st=d.get('state',{})
 if t=='tool' and isinstance(st.get('metadata'),dict):
  for k in list(st['metadata']):
   if k in ('output','preview') and st['metadata'][k]==st.get('output'):st['metadata'][k]='[EXACT duplicate state.output]'
 for k in ('id','sessionID','messageID','callID'):d.pop(k,None)
 projection=ns['replace'](d);start=len(redacted);projection=clean(projection,part);row['withheld']=redacted[start:];s=json.dumps(projection,ensure_ascii=False,sort_keys=True);sha=hashlib.sha256(s.encode()).hexdigest();row['projection_sha256']=sha
 if sha in seen:row['status']='exact-sanitized-part-reference';row['representative_part_id']=seen[sha]
 else:
  seen[sha]=part;p=dest/f'{count:03}.txt';p.write_text(flatten(projection)+'\n');row.update(status='pending',display_index=count,display_path=str(p),display_bytes=p.stat().st_size,display_sha256=hashlib.sha256(p.read_bytes()).hexdigest());count+=1
 rows.append(row)
(D/'hermes-infra-coverage.json').write_text(json.dumps(rows,indent=2)+'\n');(D/'hermes-infra-redactions.json').write_text(json.dumps(redacted,indent=2)+'\n');print('Parts',len(rows),'distinct displays',count,'display bytes',sum(r.get('display_bytes',0) for r in rows),'withheld markers',len(redacted));print('types',{t:sum(r['type']==t for r in rows) for t in sorted(set(r['type'] for r in rows))})
