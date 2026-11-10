"""Exact AST usage loop, fake HTTP and storage; no package import or live effects."""
import ast,asyncio,contextlib,hashlib,json,sys,types
from pathlib import Path
p=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/harnesses/cursor_native/usage.py')
raw=p.read_bytes();tree=ast.parse(raw.decode());names={'_coerce_int','_UsageAccumulator','_usage_post_body','forward_cursor_usage_to_session'}
nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name in names]
from dataclasses import dataclass,field
calls=[];writes=[];ticks=0
class StopFixture(BaseException):pass
class Client:
 async def post(self,*a,**k):calls.append(k['json']);raise OSError('synthetic transport failure')
@contextlib.asynccontextmanager
async def open_server_client(*a,**k):yield Client()
async def to_thread(f,*a):return f(*a)
async def sleep(*a):
 global ticks
 ticks+=1
 if ticks>=3:raise StopFixture()
mod=types.ModuleType('omnigent.cli_auth');mod.open_server_client=open_server_client
sys.modules['omnigent.cli_auth']=mod
httpx=types.ModuleType('httpx');httpx.Timeout=lambda *a,**k:None;sys.modules['httpx']=httpx
ns={'dataclass':dataclass,'field':field,'asyncio':types.SimpleNamespace(to_thread=to_thread,sleep=sleep,CancelledError=asyncio.CancelledError),'_DEFAULT_POLL_INTERVAL_S':.7,'_POST_TIMEOUT_S':30,'_logger':types.SimpleNamespace(exception=lambda *a,**k:None),'_read_usage_lines':lambda *a:[{'generation_id':'fixture-one','input_tokens':10,'output_tokens':2,'cache_read_tokens':3,'model':'public-fixture'}],'_write_usage_state':lambda *a:writes.append('persisted')}
m=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+nodes,type_ignores=[])
exec(compile(ast.fix_missing_locations(m),str(p),'exec'),ns)
ns['_read_usage_state']=lambda *a:ns['_UsageAccumulator']()
async def run():
 try:await ns['forward_cursor_usage_to_session'](base_url='https://inert.invalid',headers={},session_id='fixture',bridge_dir=Path('/inert'))
 except StopFixture:pass
asyncio.run(run())
assert ticks==3 and len(calls)==1 and not writes
out={'source':str(p),'raw_sha256':hashlib.sha256(raw).hexdigest(),'method':'Four exact AST definitions; fake client always raises before response, fixed one-line usage snapshot, three fake poll sleeps, fake storage. No native hook/store or server used.','fixture_correction':'Initial run stopped at absent httpx import before any loop execution; replaced with inert Timeout-only fake module.', 'polls':ticks,'post_attempts':len(calls),'state_writes':writes,'first_post':calls[0],'result':'Accumulator marks generation seen before failed POST; subsequent unchanged polls never retry. New generation or supervisor restart changes conditions.'}
Path('docs/deep-audit/verification/omnigent-cursor-usage-retry-proof.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
