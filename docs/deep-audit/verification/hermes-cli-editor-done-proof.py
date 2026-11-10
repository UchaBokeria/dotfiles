"""Exact AST editor wrapper with fake completed task/buffer; no editor/application import."""
import ast, hashlib, json, sys, types
from pathlib import Path
p=Path('/home/scriptkid/.hermes/hermes-agent/hermes_cli/cli_modal_mixin.py');raw=p.read_bytes();tree=ast.parse(raw)
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CLIModalMixin');fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_open_external_editor')
fake=types.ModuleType('cli');fake._DIM=fake._RST='';fake._cprint=lambda *a:None;sys.modules['cli']=fake
ns={'t':lambda *a,**k:'fixture'};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(p),'exec'),ns)
class FailedTask:
 def add_done_callback(self,cb): cb(self)
 def result(self):raise RuntimeError('synthetic editor failure')
class Buffer:
 text='existing unsubmitted draft'
 def open_in_editor(self,**kwargs):return FailedTask()
class State:
 _command_running=False
 _sudo_state=_secret_state=_approval_state=_slash_confirm_state=_clarify_state=_connection_state=None
 def __init__(self):self._app=types.SimpleNamespace(current_buffer=Buffer());self.submitted=[]
 def _inline_pastes(self,b):pass
 def _submit_editor_buffer(self,b):self.submitted.append(b.text)
s=State();opened=ns['_open_external_editor'](s)
assert opened and s.submitted==['existing unsubmitted draft']
result={'source':str(p),'raw_sha256':hashlib.sha256(raw).hexdigest(),'application_imported':False,'editor_processes':0,'callback_invoked_without_task_result_check':True,'submitted_existing_draft':bool(s.submitted),'dependency_evidence':'Installed system and Omnigent prompt_toolkit buffer.open_in_editor leaves buffer unchanged when editor success False; task completion still invokes done callback. Active Hermes interpreter not proven.'}
print(json.dumps(result,indent=2));Path('docs/deep-audit/verification/hermes-cli-editor-done-proof.json').write_text(json.dumps(result,indent=2)+'\n')
