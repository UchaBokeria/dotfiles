from pathlib import Path
import json,re,hashlib,collections
script=Path(__file__).parent/'codex-parent-omission-recover.py';prefix=script.read_text().split('for i,e in enumerate(om):')[0];exec(compile(prefix,str(script),'exec'))
a=json.loads((P/'omission-recovery.json').read_text());items=[];seen={};safevalues={'','; ','Bearer ','no-key-required','not-needed','invalid','wrong-password','fixture','fixture-only','<redacted>','YOUR_KEY','${VAR}','{env:VAR}'}
for e in a:
 if not e.get('exclusions'):continue
 rr=json.loads(records[e['source_line']-1]);zs=[]
 for v in walk(rr):
  for z in v.splitlines():
   if H(z)==e['raw_sha256']:zs.append(z)
 assert zs,(e['index'],'missing')
 z=zs[0]
 def save(kind,val):
  h=H(val);public=False;reason=None
  if kind=='literal-auth-value-conservative':
   if val in safevalues:public=True;reason='known public code literal'
   elif 'getpass.getpass' in val or ('confirm = ' in val and 'getpass' in val):public=True;reason='getpass prompt/code overspan'
   elif re.search(r'(?i)owner.{0,30}(?:request|authoriz|setup|approved)|(?:request|authoriz).{0,30}owner',val):public=True;reason='owner authorization provenance prose, not a credential'
  else:
   if val=='LLM_1234567890123456_fixture-SENSITIVE-tail' or 'fixture-session-token' in val:public=True;reason='explicit regression fixture'
   elif val.startswith('Bearer ') and ('BEARER-sensitive' in val or 'a'*20 in val):public=True;reason='assembled regression fixture'
   elif val.lower().startswith('basic ') and all(w in {'access','refresh','revocation','logout','session','sessions','revoke','tokens','token','cookie','stateless'} for w in re.split(r'[/_-]',val[6:].lower())):public=True;reason='public Basic token-lifecycle prose'
  rec={'kind':kind,'sha256':h,'chars':len(val),'entry':e['index'],'source_line':e['source_line'],'status':'public-restoration-pending-read' if public else 'credential-or-unclassified-value-withheld'}
  if public:rec.update(public_value=val,reason=reason)
  if (kind,h) in seen:rec['representative']=seen[(kind,h)]
  else:seen[(kind,h)]=len(items)
  items.append(rec)
 for pat in patterns:
  def sub(m):save('credential-shaped-span',m.group());return '[CREDENTIAL-SHAPED VALUE EXCLUDED]'
  z=re.sub(pat,sub,z)
 def ass(m):save('literal-auth-value-conservative',m.group(2));return m.group(1)+'"[AUTH VALUE EXCLUDED]"'
 assignment.sub(ass,z)
(P/'omission-exclusion-values.json').write_text(json.dumps(items,indent=2));print('counts',dict(collections.Counter(x['status'] for x in items)),'unique',len(seen))
for i,x in enumerate(items):
 if 'representative' in x:continue
 if 'public_value' in x:print('PUBLIC',i,'entry',x['entry'],x['reason'],json.dumps(x['public_value']))
 else:print('WITHHELD',i,'entry',x['entry'],x['kind'],'chars',x['chars'])
