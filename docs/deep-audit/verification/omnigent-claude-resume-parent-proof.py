"""Exact source parent-graph reconstruction with inert text-only dependency seams."""
import ast,hashlib,json,uuid
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
source=Path('/home/scriptkid/.local/share/uv/tools/omnigent/lib/python3.13/site-packages/omnigent/harnesses/claude_native/main.py');raw=source.read_bytes();names={'_claude_transcript_records_from_session_items','_claude_transcript_record_from_session_item','_synthetic_claude_transcript_uuid','_transcript_items_equal_ignoring_envelope','_json_object','_json_object_from_string','_claude_assistant_content_from_api_blocks','_claude_text_blocks_from_api_content','_claude_user_content_from_api_blocks'}
nodes=[n for n in ast.parse(raw.decode()).body if isinstance(n,ast.FunctionDef)and n.name in names];assert len(nodes)==len(names)
ns={'json':json,'uuid':uuid,'datetime':datetime,'timezone':timezone,'_claude_attachment_text_blocks_from_api_content':lambda *args:[],'strip_unparseable_image_output':lambda x:x,'tool_result_content_blocks':lambda x:SimpleNamespace(blocks=None,dropped_oversized_image=False),'_tool_use_result_for_content':lambda output,*args:json.dumps(output)}
mod=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[]);exec(compile(ast.fix_missing_locations(mod),str(source),'exec'),ns)
items=[{'id':'prompt','type':'message','role':'user','content':[{'type':'input_text','text':'fixture'}]},{'id':'callA','type':'function_call','call_id':'A','name':'Read','arguments':'{}'},{'id':'callB','type':'function_call','call_id':'B','name':'Read','arguments':'{}'},{'id':'resultA','type':'function_call_output','call_id':'A','output':'text-A'},{'id':'resultB','type':'function_call_output','call_id':'B','output':'text-B'},{'id':'final','type':'message','role':'assistant','content':[{'type':'output_text','text':'done'}]}]
records=ns['_claude_transcript_records_from_session_items'](items,session_id='fixture-conv',external_session_id='fixture-native',cwd=Path('/inert/fixture'),bridge_dir=Path('/inert/bridge'))
labels={r['uuid']:i['id']for r,i in zip(records,items,strict=True)};by_id={r['uuid']:r for r in records};leaf=records[-1]['uuid'];chain=[]
while leaf:
 r=by_id[leaf];chain.append(labels[leaf]);leaf=r.get('parentUuid')
chain.reverse();assert chain==['prompt','callA','callB','resultB','final']
out={'source':str(source),'raw_sha256':hashlib.sha256(raw).hexdigest(),'method':'Exact9AST source functions, ordinary text-only fixture, attachment/image dependencies inert identity/empty seams; stdlib UUID/time only; no package import or files outside audit written','input_order':[x['id']for x in items],'generated_parent_graph':[{'item':labels[r['uuid']],'parent':labels.get(r.get('parentUuid')),'message_id_present':'id'in r['message']}for r in records],'latest_leaf_parent_chain':chain,'off_chain':['resultA'],'limit':'Parent-graph omission shown; installed SDK/native CLI orphan recovery is a separate prerequisite, no upstream CLI launch'}
Path('docs/deep-audit/verification/omnigent-claude-resume-parent-proof.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
