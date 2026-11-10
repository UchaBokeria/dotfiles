from pathlib import Path
import json,hashlib,re,sys
L=Path('docs/deep-audit/hermes-runtime-desktop-coverage.json');B=Path('docs/deep-audit/verification/hermes-desktop-last-batch.json');doc=json.loads(L.read_text());rows=doc['records']
def merge(rs):
 out=[]
 for a,b in sorted(rs):
  if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
  else:out.append([a,b])
 return out
if len(sys.argv)>1 and sys.argv[1] in ('commit','commit-only') and B.exists():
 for b in json.loads(B.read_text()):
  r=next(x for x in rows if x['path']==b['path']);raw=Path(r['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==b['raw_sha256'];s=raw.decode();r['reviewed_char_ranges']=merge(r.get('reviewed_char_ranges',[])+[b['range']]);r['status']='read-sanitized' if not s or r['reviewed_char_ranges']==[[0,len(s)]] else 'partial-read';r.setdefault('display_evidence',[]).append(b);r['notes']='Only explicit bounded ranges semantically read; no imports/app/test execution; omissions retain separate disposition.'
 L.write_text(json.dumps(doc,indent=2)+'\n');B.unlink()
if len(sys.argv)>1 and sys.argv[1]=='commit-only':raise SystemExit(0)
meta=[];budget=18000
priority={'web':0,'tui_gateway':1,'ui-tui':2,'gateway':3}
focus=('web/src/main.tsx','web/src/pages/ChatPage.tsx','web/src/lib/pty-attach-token.ts','web/src/lib/pty-reconnect.ts','web/src/lib/pty-resume-sanitizer.ts','web/src/lib/api.ts','web/src/lib/gatewayClient.ts','web/src/lib/eventsFeedClient.ts','tui_gateway/entry.py','tui_gateway/event_publisher.py','ui-tui/src/gatewayClient.ts')
for r in sorted(rows,key=lambda x:((focus.index(x['relative_path'])-100 if x['relative_path'] in focus else priority.get(x['relative_path'].split('/')[0],9)),x['relative_path'])):
 if r['status'] not in ('pending-semantic-classification','partial-read') or r['suffix'] in ('.woff2','.jpg','.ico'):continue
 raw=Path(r['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['sha256'];s=raw.decode();start=0;rs=merge(r.get('reviewed_char_ranges',[]))
 for a,b in rs:
  if a>start:break
  start=max(start,b)
 end=min([start+budget,len(s)]+[a for a,b in rs if a>start]);v=s[start:end];v,n=re.subn(r'(?:sk-|ghp_|gsk_|LLM_)[A-Za-z0-9_./+\-=]{8,}','[TOKEN-SHAPED LITERAL OMITTED]',v);v,m=re.subn(r'https?://[^\s/\"\'<>]*:[^\s/\"\'<>]*@','https://[USERINFO OMITTED]@',v);q={'path':r['path'],'raw_sha256':r['sha256'],'range':[start,end],'display_sha256':hashlib.sha256(v.encode()).hexdigest(),'token_shape_omissions':n,'url_auth_omissions':m};meta.append(q);print(json.dumps(q));print(v);budget-=end-start
 if budget<=0 or len(meta)>=12:break
B.write_text(json.dumps(meta,indent=2)+'\n');print('BATCH_FILES',len(meta))
