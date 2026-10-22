import gc,json,time,traceback
from pathlib import Path
import pytest

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    if not item.nodeid.endswith('test_async_responsiveness_and_oracle[100000]'):
        yield;return
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    ticks=[];events=[];starts={};current={'phase':'fixture'}
    def callback(phase,info):
        t=time.monotonic();gen=info['generation']
        if phase=='start':
            starts[gen]=(t,current['phase'],traceback.format_stack(limit=8) if gen==2 else [])
        else:
            start,status,stack=starts.pop(gen,(t,'unknown',[]))
            events.append({'generation':gen,'start':start,'end':t,'duration':t-start,'phase':status,'stack':stack})
    def beat():
        live=[w for w in QApplication.topLevelWidgets() if hasattr(w,'cad_loading') and w.cad_loading]
        status=live[-1].status.text() if live else 'idle'
        current['phase']=status;ticks.append((time.monotonic(),status))
    timer=QTimer();timer.timeout.connect(beat);timer.start(10);gc.callbacks.append(callback)
    try:yield
    finally:
        timer.stop();gc.callbacks.remove(callback)
        gaps=[{'start':a[0],'end':b[0],'seconds':b[0]-a[0],'before':a[1],'after':b[1]} for a,b in zip(ticks,ticks[1:])]
        Path('/workspace/scratch/61dce18379e6/p5-evidence/full-cad-trace.json').write_text(json.dumps({'ticks':ticks,'gaps':sorted(gaps,key=lambda x:x['seconds'],reverse=True)[:20],'gc':events},ensure_ascii=False,indent=2))
