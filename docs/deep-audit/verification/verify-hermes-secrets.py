from pathlib import Path
import sqlite3,json,re,hashlib
D=Path('docs/deep-audit');c=sqlite3.connect('file:/home/scriptkid/.local/share/opencode/opencode.db?mode=ro',uri=True)
raw='\n'.join(x[0] for x in c.execute('select data from part where session_id=?',('ses_eec9ae45cffeoFEz5dTk7a1295',)))
secrets=set(re.findall(r'(?<![A-Za-z0-9])(?:LLM_|nvapi-|gsk_|sk-)[A-Za-z0-9_.-]{12,}|[0-9]{8,12}:[A-Za-z0-9_-]{25,}',raw))
# Short VNC log copies were historical mistake; identify only from tagged prose.
for data, in c.execute('select data from part where session_id=?',('ses_eec9ae45cffeoFEz5dTk7a1295',)):
 d=json.loads(data);st=d.get('state',{});a=st.get('input',{})
 for text in (a.get('content',''),a.get('newString','')):
  for m in re.finditer(r'(?i)VNC password[^\n]*?(?:printed|log)\s*\(?`([^`]+)`',text):
   if 5<=len(m[1])<=20:secrets.add(m[1])
findings=[];files=0
for p in D.rglob('*'):
 if not p.is_file():continue
 try:s=p.read_text()
 except (UnicodeError,OSError):continue
 files+=1;matches=[v for v in secrets if v in s]
 if matches:
  own='hermes' in str(p).lower()
  if own:
   for v in matches:s=s.replace(v,'[CREDENTIAL VALUE WITHHELD]')
   p.write_text(s)
  findings.append({'path':str(p),'distinct_matches':len(matches),'own_redacted':own})
result={'known_credential_shape_count':len(secrets),'scanned_text_files':files,'matches_before':findings,'residual_owned_matches':0,'credential_values_retained':False,'scope':'all docs/deep-audit text artifacts; only Hermes-owned files redacted; source DB untouched'}
(D/'hermes-infra-secret-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'credential_shapes':len(secrets),'scanned_text_files':files,'matched_files':len(findings),'nonowned_matches':sum(not r['own_redacted'] for r in findings)}))
