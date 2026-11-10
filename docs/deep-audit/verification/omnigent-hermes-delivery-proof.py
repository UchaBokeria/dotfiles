"""Exact AST Hermes acceptance gate; fake SQLite only, no vendor DB opened."""
import ast,hashlib,json,types
from pathlib import Path
p=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/harnesses/hermes_native/bridge.py');raw=p.read_bytes();tree=ast.parse(raw.decode())
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in {'_max_message_id','_await_new_message'}]
queries=[];readings=iter([10,11])
class FakeConnection:
 def execute(self,sql):queries.append(sql);self.value=next(readings);return self
 def fetchone(self):return (self.value,)
 def close(self):pass
fake=types.SimpleNamespace(connect=lambda *a,**k:FakeConnection(),Error=RuntimeError)
ns={'sqlite3':fake,'time':types.SimpleNamespace(monotonic=lambda:0,sleep=lambda _:None),'_DELIVERY_POLL_INTERVAL_S':.3}
m=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+nodes,type_ignores=[])
exec(compile(ast.fix_missing_locations(m),str(p),'exec'),ns)
baseline=ns['_max_message_id'](Path('/inert'))
accepted=ns['_await_new_message'](Path('/inert'),baseline,0)
assert accepted and queries==['SELECT MAX(id) FROM messages']*2
out={'source':str(p),'raw_sha256':hashlib.sha256(raw).hexdigest(),'method':'Two exact AST helpers with fake SQLite global MAX values10→11, zero-timeout fake clock; no DB/file/native terminal actions. Fixture labels new row as unrelated-session tool result; helper never queries those fields.','baseline':baseline,'new_global_max':11,'new_row_fixture':{'session':'different-session','role':'tool','content':'unrelated result'},'queries':queries,'reported_accepted':accepted,'meaning':'Any global message increase satisfies confirmation, independent of injected message identity. Actual concurrent activity not observed.'}
Path('docs/deep-audit/verification/omnigent-hermes-delivery-proof.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
