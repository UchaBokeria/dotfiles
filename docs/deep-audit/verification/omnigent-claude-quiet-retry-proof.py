"""Inert quiet-poll AST reproduction; no package imports or external effects."""
import ast,asyncio,hashlib,json
from pathlib import Path
from types import SimpleNamespace
p=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/harnesses/claude_native/forwarder.py');raw=p.read_bytes();tree=ast.parse(raw.decode());node=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef)and n.name=='_forward_available_items');m=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[])
calls=[]
async def to_thread(fn,*args):return fn(*args)
async def unexpected(*args,**kwargs):calls.append('unexpected downstream post/write')
state=SimpleNamespace(settled_response_id=None,pending_settled_response_id=None,line_cursor=10,byte_offset=100,transcript_path=Path('/inert/fixture'))
dedupe=SimpleNamespace(settled_response_id=None,pending_settled_response_id=None,observed_title='pending-title',posted_title=None,usage=None)
result=SimpleNamespace(items=[],line_cursor=10,byte_offset=100)
ns={'asyncio':SimpleNamespace(to_thread=to_thread),'_read_transcript_items_for_state':lambda *args:result,'_promote_pending_settle':lambda *args,**kwargs:False,'_post_title_change_if_new':unexpected,'_post_external_session_usage':unexpected,'_write_forward_state_async':unexpected}
exec(compile(ast.fix_missing_locations(m),str(p),'exec'),ns)
returned=asyncio.run(ns['_forward_available_items'](client=None,session_id='fixture',bridge_dir=None,agent_name='fixture',state=state,retry_tracker=None,dedupe=dedupe))
assert returned is state and not calls
out={'source':str(p),'raw_sha256':hashlib.sha256(raw).hexdigest(),'method':'Exact single AST async function with unchanged-cursor/no-items result and pending observed title; inert thread/read/post/write seams; no package import or external actions','fixture':{'line_cursor':10,'byte_offset':100,'observed_title':'pending-title','posted_title':None},'returned_same_state':returned is state,'downstream_post_or_write_calls':calls,'meaning':'Quiet-poll early return bypasses sticky title and usage retry paths; no preceding real failed HTTP simulated','fixture_correction':'Initial fixture omitted transcript_path attribute and raised AttributeError before outcome; corrected fixture supplies inert never-opened path.'}
Path('docs/deep-audit/verification/omnigent-claude-quiet-retry-proof.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
