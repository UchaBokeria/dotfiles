"""Exact AST method: fake singleton/pool only. No real files/auth imports."""
import ast, hashlib, json, sys, types
from pathlib import Path
source=Path('/home/scriptkid/.hermes/hermes-agent/hermes_cli/auth_oauth_grants.py'); raw=source.read_bytes(); tree=ast.parse(raw)
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_HealPass')
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='heal_profile_singleton')
module=types.ModuleType('hermes_cli.auth'); module._is_same_auth_store=lambda *a:False
parent=types.ModuleType('hermes_cli'); parent.__path__=[]
sys.modules['hermes_cli']=parent; sys.modules['hermes_cli.auth']=module
scope={'_singleton_as_row':lambda p:{'access_token':'synthetic-profile','refresh_token':'synthetic-profile-r'},'_is_oauth_pool_payload':lambda row:True,'_is_pkce_row':lambda row:False,'logger':types.SimpleNamespace(debug=lambda *a,**k:None)}
code=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),method],type_ignores=[])
exec(compile(ast.fix_missing_locations(code),str(source),'exec'),scope)
class FakePath:
 name='.anthropic_oauth.json'
 def __init__(self):self.deleted=False
 def exists(self):return True
 def unlink(self):self.deleted=True
class State:pass
state=State(); state.root_singleton=None; state.root_singleton_row=None; state.r_oauth=[{'source':'unrelated-oauth'}]; state.r_rows=state.r_oauth; state.summary={'adopted':False,'files':[]}; state.profile_changed=False; state.root_changed=False
path=FakePath(); scope['heal_profile_singleton'](state,path)
dirty=bool(state.profile_changed or state.root_changed or state.summary['adopted'])
assert path.deleted and not dirty
result={'source':str(source),'raw_sha256':hashlib.sha256(raw).hexdigest(),'real_file_operations':0,'application_imported':False,'profile_singleton_deleted':path.deleted,'adoption_attempted':False,'dirty':dirty,'summary':state.summary,'scope':'Synthetic root OAuth rows contain no PKCE row; profile singleton unrelated, helper still unlinks and leaves dirty false.'}
print(json.dumps(result,indent=2)); Path('docs/deep-audit/verification/hermes-oauth-singleton-heal-proof.json').write_text(json.dumps(result,indent=2)+'\n')
