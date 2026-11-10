"""Exact AST Pi CLI transport resolver; fake configuration/SDK imports only."""
import ast,hashlib,json,sys,types
from pathlib import Path
p=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/harnesses/pi_native/credentials.py');raw=p.read_bytes();tree=ast.parse(raw.decode());n=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='_cli_config_databricks_transport');logs=[]
ambient=types.ModuleType('omnigent.onboarding.ambient');ambient._codex_config_path=lambda:Path('/inert/config.toml');ambient.codex_config_provider_transport=lambda *a:types.SimpleNamespace(base_url='https://public-fixture.invalid',auth_command=None)
execmod=types.ModuleType('omnigent.inner.codex_executor');execmod._databricks_codex_auth_command=lambda *a:'public-fixture-command'
sys.modules[ambient.__name__]=ambient;sys.modules[execmod.__name__]=execmod
class Logger:
 def info(self,*a,**k):
  exc=sys.exception();logs.append({'message_template':a[0],'active_exception':type(exc).__name__ if exc else None})
ns={'_is_databricks_ai_gateway_url':lambda *a:True,'resolve_databricks_workspace':lambda *a:types.SimpleNamespace(host='https://public-fixture.invalid'),'_LOGGER':Logger()}
m=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),n],type_ignores=[]);exec(compile(ast.fix_missing_locations(m),str(p),'exec'),ns)
result=ns['_cli_config_databricks_transport'](types.SimpleNamespace(cli='codex',model_provider='public-fixture',name='public-fixture'));assert result is None and logs[-1]['active_exception']=='NameError'
out={'source':str(p),'raw_sha256':hashlib.sha256(raw).hexdigest(),'method':'Exact AST resolver with fake ambient/SDK module functions, fake workspace credentials, logger captures exception type; no package import/config/auth command/network.','result':result,'caught_exception':logs[-1]['active_exception'],'meaning':'Missing runtime CodexConfigTransport class makes successful SDK-derived auth path decline as unavailable.'};Path('docs/deep-audit/verification/omnigent-pi-transport-name-proof.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
