import ast,json,hashlib
from pathlib import Path
p=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/spec/omnigent.py');s=p.read_text();tree=ast.parse(s)
n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_agent_tool_to_sub_spec')
class Rec:
 def __init__(self,**kw):self.__dict__.update(kw)
class AgentTool(Rec):pass
class FunctionTool(Rec):pass
class CancellableFunctionTool(Rec):pass
class MCPTool(Rec):pass
class Ex(Rec):pass
ns={'__builtins__':__builtins__,'AgentTool':AgentTool,'FunctionTool':FunctionTool,'CancellableFunctionTool':CancellableFunctionTool,'OmniExecutorSpec':Ex,'AgentSpec':Rec,'ToolsConfig':Rec,'_SYNTHETIC_SPEC_VERSION':1,'_resolve_inline_agent_tool_os_env':lambda t,p:None,'_translate_llm_from_def':lambda *a,**k:Rec(extra={}), '_translate_executor_from_def':lambda *a,**k:Rec(raw_passed='raw_executor' in k)}
m=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),n],type_ignores=[])
exec(compile(ast.fix_missing_locations(m),str(p),'exec'),ns)
t=AgentTool(executor=None,tools={'search':MCPTool(url='https://public.example.invalid/mcp')},description=None,prompt=None,pass_history=False,pass_histories=None,max_sessions=None)
r=ns['_agent_tool_to_sub_spec']('child',t)
o={'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'exact_function_range':[n.lineno,n.end_lineno],'fixture':'inert records/helper stubs; no package imports/application/HTTP','input_nested_tool_names':list(t.tools),'output_fields':list(r.__dict__),'output_local_tools':r.local_tools,'output_mcp_servers_field_present':'mcp_servers' in r.__dict__,'executor_raw_yaml_passed':r.executor.raw_passed}
Path('docs/deep-audit/verification/omnigent-inline-agent-translation-proof.json').write_text(json.dumps(o,indent=2));print(json.dumps(o,indent=2))
