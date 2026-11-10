"""Exact AST start_continuous; synthetic recorder creation failure; no audio/import/app."""
import ast,hashlib,json,pathlib,threading
p=pathlib.Path('/home/scriptkid/.hermes/hermes-agent/hermes_cli/voice.py');raw=p.read_bytes();tree=ast.parse(raw.decode());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='start_continuous');ns={'_continuous_lock':threading.Lock(),'_continuous_active':True,'_continuous_stopping':False,'_continuous_callbacks':('old',),'_debug':lambda *a:None}
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),fn],type_ignores=[])),str(p),'exec'),ns)
assert ns['start_continuous'](lambda s:None) is True and ns['_continuous_callbacks']==('old',)
ns['_continuous_active']=False;ns['_continuous_stopping']=True
assert ns['start_continuous'](lambda s:None) is False and ns['_continuous_callbacks']==('old',)
ns['_continuous_stopping']=False;ns['_continuous_recorder']=None
ns['create_audio_recorder']=lambda:(_ for _ in ()).throw(RuntimeError('synthetic factory failure'))
try:ns['start_continuous'](lambda s:None)
except RuntimeError:pass
else:raise AssertionError('expected factory failure')
assert ns['_continuous_active'] is True and ns['_continuous_recorder'] is None
result={'sha256':hashlib.sha256(raw).hexdigest(),'already_active_returns_true_keeps_old_callbacks':True,'stopping_returns_false_keeps_old_callbacks':True,'factory_exception_leaves_active_true_without_recorder':True,'scope':'Exact AST synthetic memory only; no audio dependency imports, microphone, recording, network, app or provider action.'}
pathlib.Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
