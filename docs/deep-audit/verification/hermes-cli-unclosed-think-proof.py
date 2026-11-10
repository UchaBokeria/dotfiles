"""Exact AST methods with synthetic stream and fake sinks; no application imports/TTY."""
from pathlib import Path
import ast,sys,types,json,hashlib
source=Path('/home/scriptkid/.hermes/hermes-agent/hermes_cli/cli_stream_mixin.py')
raw=source.read_bytes();tree=ast.parse(raw)
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CLIStreamMixin')
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'_stream_delta','_flush_stream'}]
assert len(methods)==2
fakecli=types.ModuleType('cli')
for name in ('_ACCENT','_RST'):setattr(fakecli,name,'')
fakecli._cprint=lambda *args:None
fakecli._strip_markdown_syntax=lambda text:text
sys.modules['cli']=fakecli
for name in ('agent','agent.markdown_tables'):sys.modules[name]=types.ModuleType(name)
sys.modules['agent.markdown_tables'].is_table_divider=lambda text:False
sys.modules['agent.markdown_tables'].looks_like_table_row=lambda text:False
ns={'_OPEN_TAGS':('<think>',),'_CLOSE_TAGS':('</think>',),'_MAX_CLOSE_TAG_LEN':len('</think>')}
for method in methods:
 exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(source),'exec'),ns)
class Sink:
 def __init__(self):
  self.show_reasoning=False;self.emitted=[];self._stream_buf='';self._stream_box_opened=False;self._stream_table_buf=[]
 def _emit_stream_text(self,text):self.emitted.append(text)
 def _close_reasoning_box(self):pass
 def _release_held_status_lines(self):pass
s=Sink();s._stream_delta=types.MethodType(ns['_stream_delta'],s)
s._stream_delta('<think>SYNTHETIC_REASONING_WITHOUT_CLOSING_TAG')
before=list(s.emitted)
ns['_flush_stream'](s)
assert before==[] and s.emitted==['SING_TAG'],(before,s.emitted)
result={'source_sha256':hashlib.sha256(raw).hexdigest(),'methods':{m.name:[m.lineno,m.end_lineno] for m in methods},'show_reasoning':False,'before_flush':before,'ordinary_text_after_flush':s.emitted,'qualification':'Synthetic unclosed tag only; no provider, actual reasoning, app import or terminal output'}
Path('docs/deep-audit/verification/hermes-cli-unclosed-think-proof.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
