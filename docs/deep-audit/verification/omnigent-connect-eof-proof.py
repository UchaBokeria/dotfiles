"""Inert exact AST extraction: no Omnigent imports or network/process calls."""
import ast, asyncio, hashlib, json, struct
from pathlib import Path
source=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/harnesses/antigravity_native/rpc.py')
raw=source.read_bytes(); tree=ast.parse(raw.decode())
names={'stream_agent_state_updates','_connect_trailer_error','_encode_connect_envelope'}
selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
assert len(selected)==3
module=ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')],level=0),*selected],type_ignores=[])
class RpcError(Exception): pass
class Response:
 status_code=200
 def __init__(self,chunks):self.chunks=chunks
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 async def aiter_bytes(self):
  for chunk in self.chunks: yield chunk
class Client:
 def __init__(self,chunks):self.chunks=chunks
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 def stream(self,*args,**kwargs):return Response(self.chunks)
async def inert_to_thread(fn,*args):return fn(*args)
class InertAsyncio: to_thread=staticmethod(inert_to_thread)
ns={'asyncio':InertAsyncio,'json':json,'struct':struct,'AntigravityRpcError':RpcError,'_rpc_url':lambda *args:'https://inert.invalid/never-requested','_assert_loopback_url':lambda url:None,'_rpc_headers':lambda *args:{},'_METHOD_STREAM_AGENT_STATE_UPDATES':'fixture','_STREAM_TIMEOUT':None,'_FRAME_HEADER_LEN':5,'_FRAME_FLAG_COMPRESSED':1,'_FRAME_FLAG_TRAILER':2}
exec(compile(ast.fix_missing_locations(module),str(source),'exec'),ns)
def frame(flag,payload):return bytes([flag])+struct.pack('>I',len(payload))+payload
cases={'empty_eof':[], 'partial_header_eof':[b'\x00\x00'], 'partial_payload_eof':[bytes([0])+struct.pack('>I',100)+b'{'], 'malformed_trailer':[frame(2,b'not-json')], 'null_error_trailer':[frame(2,b'{"error":null}')], 'empty_error_trailer':[frame(2,b'{"error":{}}')], 'valid_success_trailer':[frame(2,b'{}')], 'actual_error_control':[frame(2,b'{"error":{"code":"unavailable"}}')], 'valid_data_and_end':[frame(0,b'{"update":{"fixture":true}}')+frame(2,b'{}')]}
async def run():
 out=[]
 for name,chunks in cases.items():
  ns['_async_client']=lambda timeout,c=chunks:Client(c)
  events=[];error=None
  try:
   async for item in ns['stream_agent_state_updates'](1,'fixture'):events.append(item)
  except Exception as exc:error=type(exc).__name__
  out.append({'case':name,'returned_cleanly':error is None,'exception':error,'events':events})
 return out
out=asyncio.run(run())
assert all(x['returned_cleanly'] for x in out if x['case']!='actual_error_control')
assert next(x for x in out if x['case']=='actual_error_control')['exception']=='RpcError'
result={'source':str(source),'raw_sha256':hashlib.sha256(raw).hexdigest(),'method':'Exact3ASTfunctions compiled with inert HTTP client/context/byte iterator and immediate offload seam; no Omnigent import, no network, no process, no user state writes','cases':out,'primary_protocol':'https://connectrpc.com/docs/protocol/#streaming-response'}
Path('docs/deep-audit/verification/omnigent-connect-eof-proof.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
