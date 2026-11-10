"""Inert extracted gate-order proof; no installed package import or service action."""
import ast, asyncio, hashlib, json
from pathlib import Path
SOURCE=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/runner/app.py')
raw=SOURCE.read_bytes(); tree=ast.parse(raw)
# Exact gate statements6493–6501, and the exact original finally6656–6659.
assign=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and n.lineno==6493)
owner=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and n.lineno==6467) if False else None
all_lists=[v for n in ast.walk(tree) for _,v in ast.iter_fields(n) if isinstance(v,list) and assign in v]
body=all_lists[0]; start=body.index(assign)
gate=body[start:start+6]
assert [n.lineno for n in gate]==[6493,6494,6495,6496,6499,6502]
original_try=gate.pop()
assert isinstance(original_try,ast.Try) and original_try.finalbody
# Replace only protected business logic with a fake wait. Gate and finally unchanged.
original_try.body=ast.parse('await release.wait()').body
fn=ast.AsyncFunctionDef(name='gate',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='conversation_id'),ast.arg(arg='release')],kwonlyargs=[],kw_defaults=[],defaults=[]),body=gate+[original_try],decorator_list=[])
mod=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]))
ns={'asyncio':asyncio,'_ingest_next_seq':{},'_ingest_now_serving':{},'_ingest_cond':{}}
exec(compile(mod,'<isolated-exact-gate>','exec'),ns)
async def main():
    first_release=asyncio.Event(); later_release=asyncio.Event()
    first=asyncio.create_task(ns['gate']('fake',first_release)); await asyncio.sleep(0)
    cancelled=asyncio.create_task(ns['gate']('fake',later_release)); await asyncio.sleep(0)
    cancelled.cancel(); await asyncio.gather(cancelled,return_exceptions=True)
    first_release.set(); await first
    later=asyncio.create_task(ns['gate']('fake',later_release)); await asyncio.sleep(0)
    result={'next_seq':dict(ns['_ingest_next_seq']),'now_serving':dict(ns['_ingest_now_serving']),'later_ticket_waiting':not later.done(),'expected_later_ticket':2,'abandoned_ticket':1}
    later.cancel(); await asyncio.gather(later,return_exceptions=True)
    return result
result=asyncio.run(main()); assert result['later_ticket_waiting'] and result['now_serving']['fake']==1
out={'source':str(SOURCE),'sha256':hashlib.sha256(raw).hexdigest(),'source_ranges':[[6493,6502],[6656,6659]],'method':'AST gate and finally unchanged; protected business logic replaced by Event wait; isolated dicts/asyncio only','result':result}
Path('docs/deep-audit/verification/omnigent-ingest-ticket-cancel-proof.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
