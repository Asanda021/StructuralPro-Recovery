"""Run the unchanged 100k test repeatedly, then examine idle reclamation."""
import gc,json,resource,time
from pathlib import Path
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from core.drawings.dwg_takeoff import DWGEntity

root=Path(__file__).resolve().parent
original=gc.get_threshold(); enabled=gc.isenabled();results=[];events=[];starts={}
def callback(phase,info):
    now=time.monotonic();generation=info['generation']
    if phase=='start':starts[generation]=now
    elif generation==2:events.append({'generation':generation,'start':starts.get(generation,now),'end':now,'seconds':now-starts.get(generation,now)})
gc.callbacks.append(callback)
try:
    for i in range(3):
        before=len(events);start=time.monotonic();base=root/f'repeat-{i}'
        code=pytest.main(['-q','tests/test_phase2_priority4_closure.py::test_async_responsiveness_and_oracle[100000]','--basetemp='+str(base)])
        assert gc.get_threshold()==original and gc.isenabled()==enabled
        assert code==0
        responsiveness=json.loads(next(base.rglob('responsiveness.json')).read_text())
        # Stability phase after the unchanged test has stopped its timer/closed.
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        if QApplication.instance():QApplication.processEvents()
        gc.collect(2)
        retained=sum(isinstance(x,DWGEntity) for x in gc.get_objects())
        assert retained==0, retained
        results.append({'iteration':i,'exit_code':int(code),'elapsed_s':time.monotonic()-start,'responsiveness':responsiveness,'full_gc':events[before:],'retained_source_entities_after_idle_collection':retained,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'thresholds_restored':True,'gc_enabled_unchanged':True})
finally:
    gc.callbacks.remove(callback)
    (root/'repeat-cad.json').write_text(json.dumps(results,indent=2))
