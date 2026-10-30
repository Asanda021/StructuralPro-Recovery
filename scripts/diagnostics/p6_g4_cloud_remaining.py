"""Bounded evidence harness; original application/tests are unchanged."""
from __future__ import annotations
import datetime as dt
import importlib.metadata as md
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import psutil

OUT = Path('g4-evidence')
OUT.mkdir(exist_ok=True)

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()

def execute(name, command, timeout):
    start = now(); clock = time.monotonic()
    with (OUT / (name+'.log')).open('w', encoding='utf-8') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        proc = psutil.Process(child.pid); rss = 0; cpu = 0; timed_out = False
        while child.poll() is None:
            if time.monotonic()-clock > timeout:
                timed_out = True
                for p in proc.children(recursive=True):
                    try: p.kill()
                    except psutil.Error: pass
                child.kill(); break
            total_rss = 0; total_cpu = 0
            for p in [proc]+proc.children(recursive=True):
                try:
                    total_rss += p.memory_info().rss
                    c = p.cpu_times(); total_cpu += c.user+c.system
                except psutil.Error: pass
            rss = max(rss, total_rss); cpu = max(cpu, total_cpu)
            time.sleep(.1)
        code = child.wait()
    result = dict(start_utc=start, end_utc=now(), elapsed_seconds=time.monotonic()-clock,
                  exit_code=code, timeout=timed_out, timeout_seconds=timeout,
                  peak_sampled_process_tree_rss_bytes=rss, maximum_sampled_tree_cpu_seconds=cpu,
                  memory_measurement='100ms process-tree samples, not leak proof', command=command)
    (OUT/(name+'.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result

TESTS = [
 'tests/test_recovery_ui_export_runtime.py',
 'tests/test_recovery_office_export_contract.py',
 'tests/test_phase1_manual_report_formats.py',
 'tests/test_manual_formula_reports.py',
 'tests/test_phase6_p3_four_view_final.py',
 'tests/test_phase6_p3_full_verified_boq.py',
 'tests/test_phase6_p2_background_loader.py',
 'tests/test_phase6_p2_member_batches.py',
 'tests/test_phase6_g2_integrated_batch_switch.py',
 'tests/test_phase5_backup_recovery.py',
 'tests/test_phase4_sqlite_windows_native.py',
 'tests/test_recovery_concurrent_takeoff.py',
 'tests/test_real_pdf_vector_takeoff.py',
 'tests/test_pdf_graphical_calibration.py',
 'tests/test_phase1_contract_ui_integration.py::test_pile_unsaved_close_warns_and_cancel_preserves_input',
]
versions = {x:md.version(x) for x in ['PySide6','PyMuPDF','openpyxl','python-docx','ifcopenshell','pytest','psutil']}
import sqlite3
versions.update(python=sys.version, sqlite=sqlite3.sqlite_version, platform=platform.platform(),
                source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                qt_backend=os.getenv('QT_QPA_PLATFORM'), qt_logical_scale=os.getenv('QT_SCALE_FACTOR','1'),
                dwg_converter=os.getenv('STRUCTURALPRO_DWG_CONVERTER'),
                office_desktop_approval=False, physical_hardware_tested=False)
(OUT/'versions.json').write_text(json.dumps(versions,indent=2),encoding='utf-8')
r = execute('original-tests', [sys.executable,'-m','pytest','-q','-o','faulthandler_timeout=0',
    '--junitxml=g4-evidence/original-tests.xml','--basetemp=g4-evidence/test-temp',*TESTS], 420)
root=ET.parse(OUT/'original-tests.xml').getroot()
cases=root.findall('.//testcase')
counts=dict(tests=len(cases), failures=len(root.findall('.//failure')), errors=len(root.findall('.//error')), skipped=len(root.findall('.//skipped')))
counts['passed']=counts['tests']-counts['failures']-counts['errors']-counts['skipped']
(OUT/'junit-summary.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
# LibreOffice is a real additional rendering engine, not Microsoft Office UAT.
soffice = shutil.which('soffice') or str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'LibreOffice/program/soffice.exe')
render_results=[]
for fmt in ('docx','xlsx'):
    source=next(OUT.rglob('persian_quantities.'+fmt),None)
    if not source or not Path(soffice).is_file():
        render_results.append(dict(format=fmt,status='BLOCKED_ENVIRONMENT',reason='source or LibreOffice unavailable'));continue
    dest=OUT/('libreoffice-'+fmt);dest.mkdir(exist_ok=True)
    res=execute('render-'+fmt,[soffice,'--headless','--convert-to','pdf','--outdir',str(dest.resolve()),str(source.resolve())],90)
    target=dest/(source.stem+'.pdf')
    res.update(format=fmt, renderer='LibreOffice headless', status='FAIL_REPRODUCED')
    if res['exit_code']==0 and not res['timeout'] and target.is_file():
        import pymupdf
        with pymupdf.open(target) as doc:
            texts=[p.get_text() for p in doc]
            assert texts and all(t.strip() for t in texts)
            for i in sorted({0,len(doc)-1}):
                doc[i].get_pixmap(matrix=pymupdf.Matrix(1,1)).save(dest/f'page-{i+1}.png')
            (dest/'extracted.txt').write_text('\n'.join(texts),encoding='utf-8')
            res.update(status='PASS_REAL_WINDOWS_AUTOMATED',pages=len(doc),nonempty_text_pages=len(texts),
                       visual_human_approval=False, content_assertion='nonempty rendered pages; numeric/RTL source validation in original export probe')
    render_results.append(res)
(OUT/'render-summary.json').write_text(json.dumps(render_results,indent=2),encoding='utf-8')
assert r['exit_code']==0 and not r['timeout'] and cases and not any(counts[k] for k in ['failures','errors','skipped']), counts
assert all(x['status']!='FAIL_REPRODUCED' for x in render_results),render_results
