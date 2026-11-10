"""Exact AST functions only; synthetic memory, no application imports or files changed."""
import ast, contextlib, hashlib, json, logging, pathlib, re, sys
source=pathlib.Path('/home/scriptkid/.hermes/hermes-agent/hermes_cli/config.py')
raw=source.read_bytes(); tree=ast.parse(raw.decode())
names={'resolve_turn_limit','save_env_value','_last_known_good_fallback'}
selected=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names]
assert len(selected)==3
ns={'sys':sys,'logger':logging.getLogger('inert'), 'TURN_LIMIT_UNLIMITED':sys.maxsize,
 '_UNLIMITED_SPELLINGS':frozenset({'none','null','unlimited','infinite','infinity','inf','∞','-1','0'}),
 '_env_write_blocked':lambda *a:False,'validate_env_var_name_for_write':lambda x:None,
 '_check_non_ascii_credential':lambda k,v:v,'ensure_hermes_home':lambda:None,
 '_env_write_lock':lambda p:contextlib.nullcontext(), '_read_env_lines':lambda p:list(lines),
 '_quote_env_value':lambda v:v,'_env_line_defines_key':lambda line,key:line.partition('=')[0]==key,
 '_write_env_lines':lambda p,new,**kw:written.extend(new), '_publish_env_value':lambda *a:None,
 'invalidate_env_cache':lambda:None}
class MemoryPath:
 def exists(self):return True
ns['get_env_path']=lambda:MemoryPath()
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+selected,type_ignores=[])),str(source),'exec'),ns)
limits={}
for label,value in [('nan_float',float('nan')),('inf_float',float('inf')),('infinity_string','infinity'),('positive_inf_string','+inf'),('bool',True),('zero',0)]:
 try:limits[label]={'value':ns['resolve_turn_limit'](value)}
 except Exception as e:limits[label]={'error':type(e).__name__}
lines=['SYNTHETIC_TOKEN=old-first\n','SYNTHETIC_TOKEN=old-last\n'];written=[]
ns['save_env_value']('SYNTHETIC_TOKEN','replacement')
assert written==['SYNTHETIC_TOKEN=replacement\n','SYNTHETIC_TOKEN=old-last\n']
assert limits['nan_float']['error']=='ValueError' and limits['inf_float']['error']=='OverflowError'
# LKG branch bypasses backup imports with a nonempty synthetic in-memory value.
import copy
class Failed(dict):
 def __init__(self,v,*,error):super().__init__(v);self.read_error=error
ns.update(copy=copy,FailedConfigRead=Failed,_LAST_EXPANDED_CONFIG_BY_PATH={'synthetic':{'api_key':'synthetic-old-expanded'}},
 _expand_env_vars=lambda x:x,_warn_config_parse_failure=lambda *a,**k:None,_LOAD_CONFIG_CACHE={})
result=ns['_last_known_good_fallback'](None,'synthetic',(1,2,3,4,5,6,7,8),ValueError('synthetic'))
assert result['api_key']=='synthetic-old-expanded' and ns['_LOAD_CONFIG_CACHE']['synthetic'][-1]=={}
report={'source_sha256':hashlib.sha256(raw).hexdigest(),'functions':sorted(names),'limit_results':limits,
 'duplicate_env_assignments_retained':len(written),'lkg_keeps_expanded_value_and_empty_env_snapshot':True,
 'scope':'Exact AST functions, synthetic in-memory dependencies, no application import, no actual secrets/config/network/provider/terminal actions.'}
pathlib.Path(__file__).with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
