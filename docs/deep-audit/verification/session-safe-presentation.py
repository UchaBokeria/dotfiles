import pathlib,json,re,hashlib,sys
p=pathlib.Path(sys.argv[1]);a=json.loads((p/'records.json').read_text());seen={};omissions=[];ranges=[]
def conv(v,idx,field='$'):
 if isinstance(v,dict):
  st=v.get('state')
  if isinstance(st,dict):
   md=st.get('metadata')
   if isinstance(md,dict):
    for k in ['output','preview']:
     if isinstance(md.get(k),str) and md[k]==st.get('output'):md[k]='[EXACT same state.output]'
   if st.get('title')==st.get('input',{}).get('command'):st['title']='[EXACT input.command]'
  return {k:('[CREDENTIAL FIELD WITHHELD]' if re.fullmatch(r'(?i)(?:password|passwd|pwd|api[_-]?key|access_token|refresh_token|client_secret)',k) else conv(x,idx,field+'.'+k)) for k,x in v.items()}
 if isinstance(v,list):return [conv(x,idx,field+f'[{j}]') for j,x in enumerate(v)]
 if not isinstance(v,str):return v
 if len(v)>300:
  sh=hashlib.sha256(v.encode()).hexdigest()
  if sh in seen:return '[EXACT earlier reviewed field '+str(seen[sh])+' SHA256='+sh+']'
  seen[sh]=(idx,field)
 out=[]
 for no,line in enumerate(v.splitlines(),1):
  if re.search(r'(?i)(?:\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization)\b\s*[:=]|sshpass\s+-p|BEGIN .*PRIVATE KEY|\beyJ[A-Za-z0-9_-]+\.)',line):
   omissions.append({'index':idx,'field':field,'line':no,'sha256':hashlib.sha256(line.encode()).hexdigest(),'chars':len(line)});out.append('[CONSERVATIVE CREDENTIAL-SHAPED LINE WITHHELD]')
  else:out.append(line)
 return '\n'.join(out)
def flatten(v,field='$'):
 if isinstance(v,dict):return '\n'.join(flatten(x,field+'.'+k) for k,x in v.items())
 if isinstance(v,list):return '\n'.join(flatten(x,field+f'[{j}]') for j,x in enumerate(v))
 return field+' = '+(v if isinstance(v,str) else json.dumps(v))
texts=[];pos=0
for i,r in enumerate(a):
 d=conv(r['content'],i);t=f'\n===== DISPLAY {i} PART {r["part_id"]} =====\n'+flatten(d)+'\n';texts.append(t);ranges.append({'index':i,'start':pos,'end':pos+len(t),'sha256':hashlib.sha256(t.encode()).hexdigest()});pos+=len(t)
(p/'review.txt').write_text(''.join(texts));(p/'omissions.json').write_text(json.dumps(omissions,indent=2)+'\n');(p/'ranges.json').write_text(json.dumps(ranges,indent=2)+'\n');print('chars',pos,'displays',len(texts),'omissions',len(omissions))
