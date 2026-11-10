"""Isolated exact async exchange with fake blocking function; no socket/package import."""
import ast,asyncio,hashlib,json,threading
from pathlib import Path
from typing import Any
p=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/runtime/harnesses/_harness_zygote_client.py');raw=p.read_bytes();tree=ast.parse(raw)
f=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='_exchange');f.decorator_list=[]
ns={'asyncio':asyncio,'Any':Any,'ZygoteHarnessUnavailable':type('ZygoteHarnessUnavailable',(Exception,),{})}
exec(compile(ast.fix_missing_locations(ast.Module(body=[f],type_ignores=[])),'<exact-exchange>','exec'),ns)
class Fake:
    _exchange=ns['_exchange']
    def __init__(self):
        self._lock=asyncio.Lock();self._sock=object();self.release=threading.Event();self.started=[threading.Event(),threading.Event()];self.guard=threading.Lock();self.active=0;self.maximum=0
    def _exchange_blocking(self,sock,request):
        with self.guard:self.active+=1;self.maximum=max(self.active,self.maximum)
        self.started[request['n']].set();self.release.wait(2)
        with self.guard:self.active-=1
        return {'fake':True}
async def main():
    fake=Fake();first=asyncio.create_task(fake._exchange({'n':0}));await asyncio.to_thread(fake.started[0].wait,1)
    first.cancel();await asyncio.gather(first,return_exceptions=True)
    second=asyncio.create_task(fake._exchange({'n':1}));await asyncio.to_thread(fake.started[1].wait,1)
    fake.release.set();await second
    return {'max_simultaneous_fake_blocking_exchanges':fake.maximum,'no_socket_created':True}
result=asyncio.run(main());assert result['max_simultaneous_fake_blocking_exchanges']==2
out={'source':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'method_lines':[f.lineno,f.end_lineno],'method':'Exact _exchange AST, isolated Fake state and blocking function; only local thread Events/asyncio','result':result}
Path('docs/deep-audit/verification/omnigent-zygote-exchange-cancel-proof.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
