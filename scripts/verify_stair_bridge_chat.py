"""Preview an explicit artificial stair document without writing project data."""
from pathlib import Path
from json import loads,dumps
from core.takeoff.stair_bridge_chat import compile_preview
src=Path(__file__).resolve().parents[1]/'examples'/'stair_chat_example.json'
data=loads(src.read_text(encoding='utf-8'))
project={'id':data['metadata']['project_id'],'takeoffs':[],'boq':[]}
print(dumps(compile_preview(data,project,source_id='STAI-R1',reviewer='بازبین جدید',
                            ownership_reference='صورتجلسه مصنوعی مالکیت حجمی'),ensure_ascii=False,indent=2))
