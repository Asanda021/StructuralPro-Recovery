"""Preserve only actual XML from the already-running pre--junit runner snapshot."""
from pathlib import Path
import json,time,hashlib,xml.etree.ElementTree as ET
report=Path('/tmp/structuralpro_qa_result_bhj4wntr/result.xml')
out=Path(__file__).resolve().parent
result={'observed_original_report':str(report),'copied':False,'synthetic_xml':False}
while report.parent.exists():
    try:
        data=report.read_bytes()
        ET.fromstring(data)
    except (OSError,ET.ParseError):
        time.sleep(0.05)
        continue
    (out/'current-final-observed.xml').write_bytes(data)
    result.update(copied=True,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    break
(out/'current-final-junit-observation.json').write_text(json.dumps(result,indent=2)+'\n')
print(result)
