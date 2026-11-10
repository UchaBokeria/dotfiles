"""Execute only AST-extracted state/consumer fragments with inert local objects."""
import ast
import asyncio
import enum
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
p = Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/repl/_repl.py')
raw = p.read_bytes()
s = raw.decode()
tree = ast.parse(s)
classes = [next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name) for name in ('_ApprovalVerdict','_ApprovalState')]
render = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_render_session_event')
branch = next(n for n in render.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'isinstance(event, ElicitationResolvedEvent)')
fn = ast.FunctionDef(name='consume_resolution', args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='event')], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[branch], decorator_list=[])
module = ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0), *classes, fn], type_ignores=[])
ast.fix_missing_locations(module)
class Resolution: pass
class Text:
    @staticmethod
    def from_markup(value): return value
outputs=[]
ns={'asyncio':asyncio, 'enum':enum,'ElicitationResolvedEvent':Resolution,'Text':Text,'fmt':SimpleNamespace(muted='dim'),'host':SimpleNamespace(output=outputs.append),'tape_entry':None}
exec(compile(module,'<inert exact Omnigent AST fragments>','exec'),ns)
async def prove():
    state=ns['_ApprovalState']()
    ns['approval_state']=state
    first=state.begin('child-A-policy','tool_call')
    second=state.begin('child-B-policy','tool_call')
    event=Resolution()
    event.elicitation_id='elicitation-A'
    event.action='decline'
    event.reason=None
    ns['consume_resolution'](event)
    return {'first_prompt_result':await first,'second_prompt_result':await second,'event_id':'elicitation-A','event_action':'decline','second_prompt_identity':'child-B-policy/tool_call','result_to_accept_mapping':'accept' if second.result() else 'decline','output_count':len(outputs)}
result=asyncio.run(prove())
assert result['first_prompt_result'] is False and result['second_prompt_result'] is True
out={'source_path':str(p),'source_sha256':hashlib.sha256(raw).hexdigest(),'fragments':[{'name':n.name if hasattr(n,'name') else 'ElicitationResolvedEvent branch','lines':[n.lineno,n.end_lineno]} for n in [*classes,branch]],'method':'Exact parsed class definitions and exact consumer if-branch compiled in isolation; standard-library event loop, inert fake event/Text/host. No package import, SDK, HTTP, server, terminal, config or real approval actions. POST sink only statically traced, not executed.','result':result}
Path('docs/deep-audit/verification/omnigent-repl-approval-correlation-proof.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
