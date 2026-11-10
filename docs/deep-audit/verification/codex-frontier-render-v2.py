import json,pathlib,hashlib,re,collections
D=pathlib.Path('docs/deep-audit');ROOT=pathlib.Path('/home/scriptkid/.codex/sessions')
SIDS=['01a0b0f2-b105-7860-976c-392002a601c1','01a11d10-ce96-7561-9e33-a15feb94b01e','01a116cf-f6c4-7361-9891-935e9b2d3479']
H=lambda s:hashlib.sha256(s.encode()).hexdigest()
secret=re.compile(r'(?i)(?:\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|cookie)\b[\\"\s]*[:=]|sshpass\s+(?:-|\\x2d|\\u002d)+p|BEGIN .*PRIVATE KEY|\beyJ[A-Za-z0-9_-]{10,}\.|\b(?:sk|ghp|gho|github_pat|xox[baprs])[-_][A-Za-z0-9_\\-]{15,}|(?:Bearer|Basic)\s+[A-Za-z0-9_+/.=-]{15,})')
structural_keys={'id','call_id','turn_id','root_turn_id','first_window_id','previous_window_id','window_id','compaction_response_id','timestamp','session_id','message_id','creator_user_id','creator_account_id','encrypted_content','internal_chat_message_metadata_passthrough'}
for sid in SIDS:
 p=next(ROOT.rglob('*'+sid+'*.jsonl'));O=D/'verification'/('codex-frontier-v2-'+sid);O.mkdir(exist_ok=True);seen={};safe_seen=[];records=[];fields=[];om=[];text=[];offset=0
 def walk(v,loc,line,field='$'):
  global offset
  if isinstance(v,dict):
   for k,x in v.items():
    if k in structural_keys:continue
    if re.fullmatch(r'(?i)(?:password|passwd|pwd|api[_-]?key|access_token|refresh_token|client_secret)',k):
     om.append({'source_line':line,'field':field+'.'+k,'classification':'sensitive-key-value-withheld','raw_sha256':H(json.dumps(x,ensure_ascii=False))});continue
    walk(x,loc,line,field+'.'+k)
  elif isinstance(v,list):
   for j,x in enumerate(v):walk(x,loc,line,field+'['+str(j)+']')
  elif isinstance(v,str) and v:
   h=H(v)
   if h in seen:
    loc['references'].append({'field':field,'sha256':h,'representative':seen[h]});return
   idx=len(fields);seen[h]=idx;out=[]
   for n,z in enumerate(v.splitlines(),1):
    if re.search(r'OPENCLAW_GATEWAY_TOKEN\s*=\s*[A-Za-z0-9_-]{16,}',z):
     om.append({'display':idx,'source_line':line,'field':field,'line':n,'chars':len(z),'raw_sha256':H(z),'classification':'service-environment-credential-value-withheld'});z=re.sub(r'(OPENCLAW_GATEWAY_TOKEN\s*=\s*)([A-Za-z0-9_-]{16,})',lambda m:m.group(1)+'X'*len(m.group(2)),z)
    if re.search(r'(?i)(?:[?&]|%26)token(?:=|%3d)[A-Za-z0-9_%+./=-]{20,}',z):
     om.append({'display':idx,'source_line':line,'field':field,'line':n,'chars':len(z),'raw_sha256':H(z),'classification':'URL-query-credential-value-withheld'});z=re.sub(r'(?i)((?:[?&]|%26)token(?:=|%3d))([A-Za-z0-9_%+./=-]{20,})',lambda m:m.group(1)+'X'*len(m.group(2)),z)
    if re.search(r'\bLLM_\d{6,}_[A-Za-z0-9_-]{12,}',z):
     om.append({'display':idx,'source_line':line,'field':field,'line':n,'chars':len(z),'raw_sha256':H(z),'classification':'Meta-credential-spans-withheld'});z=re.sub(r'\bLLM_\d{6,}_[A-Za-z0-9_-]{12,}','[META CREDENTIAL VALUE WITHHELD]',z)
    if secret.search(z):om.append({'display':idx,'source_line':line,'field':field,'line':n,'chars':len(z),'raw_sha256':H(z),'classification':'conservative-line-withheld'});out.append('[CONSERVATIVE CREDENTIAL-SHAPED LINE WITHHELD]')
    elif z.startswith('data:image/') or len(z)>1000000 and re.fullmatch('[A-Za-z0-9+/=]+',z):out.append('[OPAQUE ENCODED CONTENT STRUCTURAL ONLY]');om.append({'display':idx,'source_line':line,'field':field,'line':n,'chars':len(z),'raw_sha256':H(z),'classification':'opaque-encoded-content'})
    else:out.append(z)
   safe='\n'.join(out);fullsafe=safe;delta=None
   if len(safe)>1000:
    best=(0,None,0,0)
    for previous,pi in safe_seen[-60:]:
     limit=min(len(previous),len(safe));lo=0;hi=limit
     while lo<hi:
      m=(lo+hi+1)//2
      if previous[:m]==safe[:m]:lo=m
      else:hi=m-1
     pre=lo;lo=0;hi=limit-pre
     while lo<hi:
      m=(lo+hi+1)//2
      if previous[len(previous)-m:]==safe[len(safe)-m:]:lo=m
      else:hi=m-1
     suf=lo
     if pre+suf>best[0]:best=(pre+suf,pi,pre,suf)
    score,pi,pre,suf=best
    if score>1000 and score>=len(safe)*0.60:
     delta={'representative_display':pi,'prefix_chars':pre,'suffix_chars':suf,'full_safe_sha256':H(safe)}
     end=len(safe)-suf if suf else len(safe)
     safe='[EXACT SANITIZED PREFIX chars='+str(pre)+' AND SUFFIX chars='+str(suf)+' FROM EARLIER DISPLAY '+str(pi)+'; full-safe-SHA256='+H(fullsafe)+']\nEVERY DIFFERING CHARACTER:\n'+safe[pre:end]
    safe_seen.append((fullsafe,idx))
   fr='\n===== DISPLAY '+str(idx)+' SOURCE LINE '+str(line)+' FIELD '+field+' =====\n'+safe+'\n';fields.append({'display':idx,'source_line':line,'field':field,'raw_string_sha256':h,'raw_chars':len(v),'range':[offset,offset+len(fr)],'presentation_sha256':H(fr),'status':'pending','safe_delta':delta,'full_safe_sha256':H(fullsafe)});text.append(fr);offset+=len(fr);loc['fields'].append(idx)
 raw=p.read_bytes()
 for no,z in enumerate(raw.decode().splitlines(),1):
  r=json.loads(z);e={'source_line':no,'raw_sha256':H(z),'raw_bytes':len(z.encode()),'type':r.get('type'),'fields':[],'references':[],'status':'structural-with-semantic-fields-pending'};walk(r.get('payload'),e,no);records.append(e)
 (O/'review.txt').write_text(''.join(text));(O/'fields.json').write_text(json.dumps(fields,indent=2)+'\n');(O/'records.json').write_text(json.dumps(records,indent=2)+'\n');(O/'omissions.json').write_text(json.dumps(om,indent=2)+'\n');m={'source':str(p),'source_bytes':len(raw),'source_sha256':hashlib.sha256(raw).hexdigest(),'records':len(records),'unique_fields':len(fields),'review_chars':offset,'omissions':len(om),'rule':'All nonempty non-structural string leaves exact SHA dedup; IDs/opaque encrypted contents/numeric lifecycle metadata structural only; conservative line omissions remain pending recovery.'};(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(m))
