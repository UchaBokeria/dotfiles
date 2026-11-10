"""Exact-source AST extraction; synthetic gzip response only, no application import/network."""
import ast, gzip, hashlib, json, sys
from pathlib import Path
from typing import Iterator
site=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages')
sys.path.insert(0,str(site))
import httpx
source=Path('/home/scriptkid/.hermes/hermes-agent/hermes_cli/auth_codex.py')
raw=source.read_bytes(); tree=ast.parse(raw)
names={'_capped_byte_stream_class','_cap_codex_response_body'}
selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
assert len(selected)==2
scope={'httpx':httpx,'Iterator':Iterator,'_CODEX_AUTH_BODY_MAX_BYTES':1024*1024,'_codex_err':lambda *a,**k:ValueError(a[0])}
exec(compile(ast.Module(body=selected,type_ignores=[]),str(source),'exec'),scope)
payload=b'{"padding":"'+b'x'*(2*1024*1024)+b'"}'
wire=gzip.compress(payload)
response=httpx.Response(200,headers={'content-encoding':'gzip'},stream=httpx.ByteStream(wire),request=httpx.Request('GET','https://synthetic.invalid/auth'))
scope['_cap_codex_response_body'](response)
body=response.read()
assert body==payload and len(wire)<1024*1024<len(body)
result={'application_imported':False,'network_requests':0,'source':str(source),'raw_sha256':hashlib.sha256(raw).hexdigest(),'httpx_version':httpx.__version__,'httpx_source':str(Path(httpx.__file__).parent),'wire_bytes':len(wire),'decoded_bytes':len(body),'configured_cap':1024*1024,'cap_raised':False,'conclusion':'Wire-byte cap does not cap decompressed response body. Fixture dependency is installed Omnigent HTTPX, not proven Hermes active interpreter.'}
print(json.dumps(result,indent=2))
Path('docs/deep-audit/verification/hermes-codex-body-cap-proof.json').write_text(json.dumps(result,indent=2)+'\n')
