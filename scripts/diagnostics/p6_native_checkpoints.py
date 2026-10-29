"""Bounded, no-debugger operational checkpoints for the unchanged five-floor oracle."""
from __future__ import annotations
import argparse
import functools
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.diagnose_windows_native_crash import atomic_json, append_jsonl, junit_counts, TEST

class Checkpoints:
    def __init__(self, directory, repetition):
        self.directory=Path(directory); self.repetition=repetition
        self.sequence=0; self.row=0; self.operation=0; self.keys={}; self.originals=[]; self.operations={}; self.labels={}
    def emit(self, event, completed, call_id=None):
        self.sequence+=1
        data=dict(run_id=os.environ.get('GITHUB_RUN_ID','local'), repetition=self.repetition,
                  sequence=self.sequence, row_index=self.row, operation_index=self.operation,
                  event=event, monotonic_ns=time.perf_counter_ns(), completed=completed, call_id=call_id)
        append_jsonl(self.directory/'events.jsonl', data)
        atomic_json(self.directory/'last.json', data)
    def pytest_collection_modifyitems(self, items):
        from core.platform.application import StructuralProApp
        for method,event in [('load_manual_formulas','READ'),('review_manual_formula','REVIEW'),('commit_manual_formula','COMMIT')]:
            original=getattr(StructuralProApp,method); self.originals.append((StructuralProApp,method,original))
            def wrap(fn,label):
                @functools.wraps(fn)
                def measured(*args,**kwargs):
                    call=self.sequence+1; self.emit(label+'_ENTER',False,call)
                    try: result=fn(*args,**kwargs)
                    except BaseException:
                        self.emit(label+'_ERROR',False,call); raise
                    if label=='READ' and isinstance(result,dict):
                        for ordinal,(key,row) in enumerate(result.items(),1):
                            self.keys[key]=ordinal
                            self.operations[key]=self.labels.get(row.get('data',{}).get('title'),0)
                    self.emit(label+'_EXIT',True,call); return result
                return measured
            setattr(StructuralProApp,method,wrap(original,event))
        module=items[0].module
        self.labels={case[0]:i for i,case in enumerate(module.CASES,1)}
        original=module.select_key; self.originals.append((module,'select_key',original))
        @functools.wraps(original)
        def select(dialog,key,qt):
            result=original(dialog,key,qt)
            if key not in self.keys: self.keys[key]=len(self.keys)+1
            self.row=self.keys[key];self.operation=self.operations.get(key,0)
            self.emit('ROW_SELECTED',True)
            return result
        module.select_key=select
    def pytest_runtest_call(self, item): self.emit('CASE_START',False)
    def pytest_sessionfinish(self, session, exitstatus):
        # Original test includes Decimal BOQ oracles, final SQLite reopen, and reports.
        # Do not emit verification success unless the original test actually passed.
        if exitstatus==0:
            import sqlite3
            databases=list((self.directory/'pytest').rglob('projects.db'))
            if len(databases)!=1: raise RuntimeError('Expected one original scenario database')
            with sqlite3.connect(databases[0].as_uri()+'?mode=ro',uri=True) as db:
                if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
                    raise RuntimeError('SQLite integrity check failed')
            self.emit('SQLITE_VERIFY',True);self.emit('BOQ_VERIFY',True);self.emit('CASE_DONE',True)
        for obj,name,original in reversed(self.originals):setattr(obj,name,original)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--repetition',type=int,required=True);p.add_argument('--child',action='store_true');a=p.parse_args()
    directory=Path(a.output).resolve();directory.mkdir(parents=True,exist_ok=True)
    if a.child:
        import pytest
        raise SystemExit(pytest.main(['-q',TEST,'--basetemp='+str(directory/'pytest'),'--junitxml='+str(directory/'junit.xml')],plugins=[Checkpoints(directory,a.repetition)]))
    start=time.perf_counter();timed_out=False
    with (directory/'pytest.log').open('w',encoding='utf-8') as log:
        try:
            result=subprocess.run([sys.executable,__file__,'--child','--output',str(directory),'--repetition',str(a.repetition)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
            code=result.returncode
        except subprocess.TimeoutExpired:code=124;timed_out=True
    counts=junit_counts(directory/'junit.xml');last=json.loads((directory/'last.json').read_text()) if (directory/'last.json').exists() else None
    events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()] if (directory/'events.jsonl').exists() else []
    active={}
    for e in events:
        if e['event'].endswith('_ENTER'):active[e['call_id']]=e
        elif e['event'].endswith(('_EXIT','_ERROR')):active.pop(e['call_id'],None)
    summary=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),repetition=a.repetition,elapsed_seconds=time.perf_counter()-start,exit_code=code,timed_out=timed_out,access_violation=(code & 0xffffffff)==0xc0000005,junit=counts,last_checkpoint=last,unfinished=list(active.values()),sqlite='valid' if any(e['event']=='SQLITE_VERIFY' for e in events) else 'not_verified',boq='valid' if any(e['event']=='BOQ_VERIFY' for e in events) else 'not_verified')
    atomic_json(directory/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False))
    raise SystemExit(0 if code==0 and counts and counts.get('passed')==1 and last and last['event']=='CASE_DONE' else 1)
if __name__=='__main__':main()
