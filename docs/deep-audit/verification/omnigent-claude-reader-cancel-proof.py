"""Inert exact AST cancel path: fake reader registry, no real fd registration."""
import ast,asyncio,contextlib,hashlib,json
from pathlib import Path
source=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/harnesses/claude_native/main.py');raw=source.read_bytes();node=next(n for n in ast.parse(raw.decode()).body if isinstance(n,ast.AsyncFunctionDef)and n.name=='_read_fd_with_reader')
mod=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[])
class NoIO:
 @staticmethod
 def read(*args):raise AssertionError('No OS read allowed')
ns={'contextlib':contextlib,'os':NoIO};exec(compile(ast.fix_missing_locations(mod),str(source),'exec'),ns)
class Loop:
 def __init__(self):self.readers={};self.removes=[];self.future=None
 def create_future(self):self.future=asyncio.get_running_loop().create_future();return self.future
 def add_reader(self,fd,callback):self.readers[fd]=callback
 def remove_reader(self,fd):self.removes.append(fd);self.readers.pop(fd,None)
async def run():
 loop=Loop();task=asyncio.create_task(ns['_read_fd_with_reader'](loop,12345));await asyncio.sleep(0)
 assert 12345 in loop.readers
 task.cancel()
 try:await task
 except asyncio.CancelledError:pass
 after_cancel=12345 in loop.readers
 loop.readers[12345]()
 return {'future_cancelled':loop.future.cancelled(),'reader_registered_after_cancel':after_cancel,'reader_registered_after_ready_callback':12345 in loop.readers,'remove_reader_calls':loop.removes}
out=asyncio.run(run());assert out['future_cancelled'] and out['reader_registered_after_cancel'] and out['reader_registered_after_ready_callback'] and not out['remove_reader_calls']
result={'source':str(source),'raw_sha256':hashlib.sha256(raw).hexdigest(),'method':'Exact one AST function, asyncio task/future plus fake loop reader registry and forbidden OS read; no Omnigent import, no real fd or process action','result':out,'limit':'Proves callback registration cleanup gap; actual selector load/live attachment not exercised'}
Path('docs/deep-audit/verification/omnigent-claude-reader-cancel-proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
