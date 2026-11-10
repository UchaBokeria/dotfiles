"""Exact AST forwarder methods, inert fake HTTP500; no package imports/server."""
import ast,asyncio,hashlib,json,types
from pathlib import Path
from collections import OrderedDict
from dataclasses import dataclass,field
from urllib.parse import quote
p=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/harnesses/opencode_native/forwarder.py');raw=p.read_bytes();t=ast.parse(raw.decode());c=next(n for n in t.body if isinstance(n,ast.ClassDef)and n.name=='OpenCodeNativeForwarder');names={'_response_id','_key','_post_event','_post_assistant_text','_flush_pending_text'};nodes=[n for n in c.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))and n.name in names];nodes+=[next(n for n in t.body if isinstance(n,ast.ClassDef)and n.name=='OpenCodeForwarderState')]
ns={'dataclass':dataclass,'field':field,'OrderedDict':OrderedDict,'_MAX_DEDUPE_KEYS':8192,'quote':quote,'_AGENT_NAME':'opencode','_EXTERNAL_ITEM':'external_conversation_item','httpx':types.SimpleNamespace(HTTPError=RuntimeError),'_logger':types.SimpleNamespace(warning=lambda *a,**k:None)}
m=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+nodes,type_ignores=[]);exec(compile(ast.fix_missing_locations(m),str(p),'exec'),ns)
calls=[]
async def post(*a,**k):calls.append(k['json']);return types.SimpleNamespace(status_code=500)
obj=types.SimpleNamespace(_session_id='fixture-owner',_opencode_session_id='fixture-native',_server=types.SimpleNamespace(post=post),state=ns['OpenCodeForwarderState'](),_pending_text={'part-public':('message-public','public fixture text')})
for name in names:setattr(obj,name,types.MethodType(ns[name],obj))
async def run():await obj._flush_pending_text();await obj._flush_pending_text()
asyncio.run(run());assert len(calls)==1 and not obj._pending_text and obj.state.seen
out={'source':str(p),'raw_sha256':hashlib.sha256(raw).hexdigest(),'method':'Exact AST five forwarder methods plus state class, fake HTTP always500, two flushes, in-memory pending text only; no package import/server/native state.','fixture_correction':'Initial fixture lacked _response_id; added the exact method before successful proof.', 'flushes':2,'post_attempts':len(calls),'response_status':500,'pending_after':obj._pending_text,'seen_keys':list(obj.state.seen),'meaning':'Pending text removed and dedupe key marked before rejected post; no retry/error on unchanged second flush.'}
Path('docs/deep-audit/verification/omnigent-opencode-post-loss-proof.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
