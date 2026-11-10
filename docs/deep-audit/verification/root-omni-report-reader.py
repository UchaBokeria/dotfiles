from pathlib import Path
import json,hashlib
p=Path("docs/deep-audit/verification/root-omnigent-runtime-report-review.json");r=json.loads(p.read_text());b=Path(r["path"]).read_bytes();assert hashlib.sha256(b).hexdigest()==r["sha256"];s=b.decode();a,z=r["displayed_range"];r["reviewed_ranges"].append([a,z]);n=min(len(s),z+6000);r["displayed_range"]=[z,n];p.write_text(json.dumps(r,indent=2)+"\n");print(s[z:n])
