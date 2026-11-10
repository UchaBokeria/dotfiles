"""Pure AST predicate plus Node WHATWG URL parsing, no HTTP/browser/app action."""
import ast,hashlib,json,pathlib,subprocess
p=pathlib.Path('/home/scriptkid/.hermes/hermes-agent/hermes_cli/dashboard_auth/request_utils.py');raw=p.read_bytes();tree=ast.parse(raw.decode());f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='is_safe_next_path');ns={'_NEXT_DENY_PREFIXES':('/login','/auth/','/api/auth/')};exec(compile(ast.Module(body=[f],type_ignores=[]),str(p),'exec'),ns)
values=['/sessions','/\\synthetic.invalid/landing','//synthetic.invalid/landing']
js='const v=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write(JSON.stringify(v.map(s=>new URL(s,"https://gateway.invalid/login").href)))'
r=subprocess.run(['node','-e',js],input=json.dumps(values),text=True,capture_output=True,check=True);parsed=json.loads(r.stdout)
out=[{'input':v,'predicate_accepts':ns['is_safe_next_path'](v),'whatwg_url':url} for v,url in zip(values,parsed)]
assert out[1]['predicate_accepts'] is True and out[1]['whatwg_url'].startswith('https://synthetic.invalid/')
route=pathlib.Path('/home/scriptkid/.hermes/hermes-agent/hermes_cli/dashboard_auth/routes.py');rr=route.read_bytes();rt=ast.parse(rr.decode());wanted={'_validate_post_login_target','_externalize_post_login_target'}
from urllib.parse import unquote
ns['unquote']=unquote
exec(compile(ast.Module(body=[n for n in rt.body if isinstance(n,ast.FunctionDef) and n.name in wanted],type_ignores=[]),str(route),'exec'),ns)
landing=ns['_validate_post_login_target'](values[1]);target=ns['_externalize_post_login_target'](landing,'');assert target==values[1]
result={'source_sha256':hashlib.sha256(raw).hexdigest(),'routes_sha256':hashlib.sha256(rr).hexdigest(),'password_non_native_empty_prefix_target':target,'cases':out,'primary_reference':'https://url.spec.whatwg.org/','scope':'Pure synthetic predicate/parser mismatch only; Full routes tail and password JSON/form script source traced; actual provider/password/browser acceptance not exercised; no requests/navigation.'}
pathlib.Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
