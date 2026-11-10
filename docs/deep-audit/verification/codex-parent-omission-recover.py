import json,re,hashlib,collections
from pathlib import Path
P=Path(__file__).parent/'codex-frontier-v5-01a116cf-f6c4-7361-9891-935e9b2d3479';source=Path('/home/scriptkid/.codex/sessions/2026/10/07/rollout-2026-10-07T18-41-30-01a116cf-f6c4-7361-9891-935e9b2d3479.jsonl');raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()=='29e2e724a4f54022c429f078c226b069ba5428f8f3ca517a672e5dc3869359b2'
H=lambda s:hashlib.sha256(s.encode()).hexdigest();records=raw.decode().splitlines();om=json.loads((P/'omissions.json').read_text());safe_seen={};out=[];ledger=[];offset=0
patterns=[r'\bLLM_\d{6,}_[A-Za-z0-9_-]{12,}',r'(?i)((?:[?&]|%26)token(?:=|%3d))([A-Za-z0-9_%+./=-]{20,})',r'(?i)(OPENCLAW_GATEWAY_TOKEN\s*=\s*)([A-Za-z0-9_-]{16,})',r'\b(?:sk|ghp|gho|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{15,}',r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)?',r'(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9_+/.=-]{15,}',r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----',r'(?i)(sshpass\s+(?:-|\\x2d|\\u002d)+p\s+)(?:\\?["\x27][^\n]*?\\?["\x27]|[^\s;]+)']
# Replace literal-looking authentication values, retaining key names and code context.
assignment=re.compile(r'''(?ix)(\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|cookie|signing[_-]?secret|token)\b[\\"'\s]*[:=]\s*)(?:\\?["'])([^\n]*?)(?:\\?["'])''')
def mask(s):
 events=[]
 for pat in patterns:
  def sub(m):
   events.append({'kind':'credential-shaped-span','sha256':H(m.group()),'chars':len(m.group())});return '[CREDENTIAL-SHAPED VALUE EXCLUDED]'
  s=re.sub(pat,sub,s)
 def ass(m):
  events.append({'kind':'literal-auth-value-conservative','sha256':H(m.group(2)),'chars':len(m.group(2))});return m.group(1)+'"[AUTH VALUE EXCLUDED]"'
 s=assignment.sub(ass,s)
 # Large data image bodies cannot be reconstructed from truncated wrappers.
 s=re.sub(r'data:image/[^;,\s]+;base64,[A-Za-z0-9+/=]+',lambda m:'[ENCODED IMAGE BODY EXCLUDED; sha256='+H(m.group())+'; chars='+str(len(m.group()))+']',s)
 return s,events
def walk(v):
 if isinstance(v,str):yield v
 elif isinstance(v,dict):
  for v1 in v.values():yield from walk(v1)
 elif isinstance(v,list):
  for v1 in v:yield from walk(v1)
for i,e in enumerate(om):
 r=json.loads(records[e['source_line']-1]);found=[]
 for v in walk(r):
  for line in v.splitlines():
   if H(line)==e['raw_sha256']:found.append(line)
 if not found:
  ledger.append(dict(e,index=i,status='pending-raw-line-locator'));continue
 z=found[0];assert all(x==z for x in found)
 if e['classification']=='opaque-encoded-content':
  ledger.append(dict(e,index=i,status='asset-separate',note='Complete image originals separately inventoried images.json'));continue
 s,events=mask(z);h=H(s);rec=dict(e,index=i,safe_sha256=h,exclusions=events)
 if h in safe_seen:rec.update(status='pending-exact-safe-reference',representative=safe_seen[h]);ledger.append(rec);continue
 safe_seen[h]=i;view=f'\n===== OMISSION {i} display {e.get("display")} source {e["source_line"]} field {e["field"]} line {e.get("line")} =====\n{s}\n';rec.update(status='pending-safe-context',range=[offset,offset+len(view)]);offset+=len(view);out.append(view);ledger.append(rec)
(P/'omission-recovery.txt').write_bytes(''.join(out).encode());(P/'omission-recovery.json').write_text(json.dumps(ledger,indent=2));print(json.dumps({'source_sha256':hashlib.sha256(raw).hexdigest(),'entries':len(ledger),'statuses':dict(collections.Counter(x['status'] for x in ledger)),'review_chars':offset,'excluded_spans':sum(len(x.get('exclusions',[])) for x in ledger)}))
