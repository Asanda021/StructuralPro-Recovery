import sys, tempfile, multiprocessing as mp, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.platform.application import StructuralProApp
from tests.test_recovery_13_finishes_five_floors import CODES, explicit_inputs

def worker(root, floor, barrier, result):
    app = StructuralProApp(root)
    barrier.wait(timeout=30)
    retries = 0
    try:
        for code in CODES:
            for attempt in range(100):
                try:
                    app.add_assembly_takeoff('p', code, explicit_inputs(code), floor_id=f'طبقه {floor}', location_id='موقعیت نمونه')
                    break
                except RuntimeError as exc:
                    if 'project changed since write began' not in str(exc): raise
                    retries += 1
            else: raise AssertionError('Retry budget exhausted')
        result.put({'floor':floor, 'ok':True, 'retries':retries})
    except Exception as exc:
        result.put({'floor':floor, 'ok':False, 'error':repr(exc)})
    finally: app.store.close()

def test_five_processes_preserve_all_finishing_quantities():
    ctx = mp.get_context('spawn')
    with tempfile.TemporaryDirectory() as d:
        app = StructuralProApp(d); app.create_project('پروژه مصنوعی چندپردازشی', 'p'); app.store.close()
        barrier = ctx.Barrier(5); queue = ctx.Queue()
        children = [ctx.Process(target=worker, args=(d, floor, barrier, queue)) for floor in range(1,6)]
        for child in children: child.start()
        results = [queue.get(timeout=60) for child in children]
        for child in children:
            child.join(timeout=10); assert child.exitcode == 0
        assert all(r['ok'] for r in results), results
        app = StructuralProApp(d); p = app.open_project('p')
        assert len(p['takeoff_assemblies']) == 65
        assert len(p['takeoffs']) == 195
        assert len(p['boq']) == 13
        assert all(row['item_code'].endswith('_work') for row in p['boq'])
        bycode = {row['item_code']:row for row in p['boq']}
        from tests.test_recovery_13_finishes_five_floors import WALL, HORIZONTAL
        for code in CODES:
            expected = (10*3-2)*5 if code in WALL else ((5*4-1)*5 if code in HORIZONTAL else (7-1)*5)
            assert abs(bycode[code+'_work']['quantity']-expected) < 1e-9
        assert len({r['source_id'] for r in p['takeoffs']}) == 195
        assert len({(r['assembly_code'], r['floor_id'], r['location_id']) for r in p['takeoff_assemblies']}) == 65
        assert app.store.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        app.store.close()
        print(json.dumps({'status':'PASS', 'platform':'Linux', 'processes':5, 'assemblies':65, 'takeoffs':195, 'payable_boq':13, 'workers':results}, ensure_ascii=False))
