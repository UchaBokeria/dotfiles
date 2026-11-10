import ast,dataclasses,json,hashlib
from pathlib import Path
from types import SimpleNamespace as R
root=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent')
pp=root/'spec/parser.py';tp=root/'spec/types.py';sp=root/'spec/skill_sources.py'
pt=ast.parse(pp.read_text());tt=ast.parse(tp.read_text());st=ast.parse(sp.read_text())
def evaluate(nodes,ns):
 module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[])
 exec(compile(ast.fix_missing_locations(module),'inert-source-extract','exec'),ns)
ns={'dataclass':dataclasses.dataclass,'field':dataclasses.field}
cs=[n for n in tt.body if isinstance(n,ast.ClassDef) and n.name in ['RetryPolicy','LLMConfig']]
evaluate(cs,ns)
llm=ns['LLMConfig']('primary',fallback_models=['backup'])
f=next(n for n in pt.body if isinstance(n,ast.FunctionDef) and n.name=='parse');nodes=[n for n in f.body if n.lineno in [252,268,299,306,313]]
ns.update(llm=llm,executor=R(model=None,connection=None,reasoning_effort=None),raw={'spawn':'no','timers':'off','async':'false'})
evaluate(nodes,ns)
fallback={'input':['backup'],'output':ns['llm'].fallback_models,'exact_parse_ranges':[[n.lineno,n.end_lineno] for n in nodes]}
fn=next(n for n in st.body if isinstance(n,ast.FunctionDef) and n.name=='devin_host_skills')
calls=[]
class Proc:
 SubprocessError=RuntimeError
 @staticmethod
 def run(*a,**kw):
  calls.append({'argv':a[0]});return R(returncode=0,stdout='[{"name":"public-skill","description":"fixture"}]')
from collections.abc import Mapping
skns={'subprocess':Proc,'json':json,'Path':Path,'Mapping':Mapping,'SkillSpec':R,'_log':R(debug=lambda *a:None)}
evaluate([fn],skns)
r=skns['devin_host_skills'](R(is_native=True,roots=(),home=Path('/nonexistent-inert'),skills_filter='none'))
o={'method':'Exact AST classes/functions with inert helper records and fake subprocess; no installed package import, filesystem config access or actual command/provider execution','sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [pp,tp,sp]},'fallback_models':fallback,'boolean_conversion':{'input':ns['raw'],'output':{k:ns[k] for k in ['spawn','timers','async_enabled']}},'devin_filter':{'exact_range':[fn.lineno,fn.end_lineno],'input_skills_filter':'none','fake_subprocess_calls':calls,'returned_names':[x.name for x in r]}}
Path('docs/deep-audit/verification/omnigent-parser-source-proof.json').write_text(json.dumps(o,indent=2));print(json.dumps(o,indent=2))
