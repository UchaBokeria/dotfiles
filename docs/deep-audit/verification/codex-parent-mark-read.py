import json,collections
from pathlib import Path
p=Path(__file__).parent/'codex-frontier-v5-01a116cf-f6c4-7361-9891-935e9b2d3479'
a=json.loads((p/'fields.json').read_text());s=json.loads((p/'next-block.json').read_text());b=json.loads((p/'read-blocks.json').read_text())
for x in s:
 f=a[x['display']];f.setdefault('read_ranges',[]).append([x['start'],x['end']]);f['next_offset']=x['end'];f['status']='read-sanitized' if x['end']==x['full_end'] else 'partial'
for x in s:
 if x.get('positive_delta'):
  f=a[x['display']];f['status']='read-exact-positive-baseline-delta';f['positive_delta']=x['positive_delta'];q=Path(x['positive_delta']['proof']);d=json.loads(q.read_text());d['status']='read';q.write_text(json.dumps(d,indent=2))

for f in a:
 if f.get('query_credential_exclusions') and f['status'].startswith('read-'):
  f['status']='read-sanitized-with-query-credential-exclusions';f['query_credential_exclusions']['surrounding_context_status']='read'
for f in a:
 if f.get('encoded_image_exclusions') and f['status'].startswith('read-'):
  f['status']='read-sanitized-with-encoded-image-exclusions'

b.append({'segments':s,'method':'bounded actual tool output read; encoded image spans classified structurally with visual coverage separate'})
(p/'fields.json').write_text(json.dumps(a,indent=2));(p/'read-blocks.json').write_text(json.dumps(b,indent=2));g=json.loads((p/'progress.json').read_text());g['statuses']=dict(collections.Counter(f['status'] for f in a));f=next(f for f in a if f['status'] in ('pending','partial'));g['next_display']=f['display'];g['next_character_offset']=f.get('next_offset',f['range'][0]);(p/'progress.json').write_text(json.dumps(g,indent=2));print(g['next_display'],g['next_character_offset'])
