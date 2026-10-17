from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp
from test_manual_formula_persistence import data

def setup(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مبدأ','P');s.create_project('مقصد','Q');s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول');s.save_manual_formula('P','B',data(source_id='B',member='C2',expression='base*2',variables={},references={'base':'A'}),expected_revision=0,reason='وابسته');return s

def test_move_preserves_ids_versions_dependencies_and_copy_new_identity(tmp_path):
 s=setup(tmp_path);assert callable(getattr(s,'relocate_manual_formulas',None)), 'انتقال کنترل‌شده پیاده نشده'
 dest={'project_id':'P','block':'بلوک۲','floor':'دوم','location':'آکسA'}
 s.relocate_manual_formulas('P',['A','B'],destination=dest,mode='move',expected_revisions={'A':1,'B':1},reason='انتقال مستند')
 reg=s.load_manual_formulas('P');assert reg['A']['revision']==2 and reg['A']['data']['source_id']=='manual:test:A';assert reg['A']['data']['block']=='بلوک۲';assert reg['B']['data']['references']['base']=='A'
 dest.update(floor='سوم');mapping=s.relocate_manual_formulas('P',['A','B'],destination=dest,mode='copy',expected_revisions={'A':2,'B':2},reason='کپی اعضای مستقل')
 reg=s.load_manual_formulas('P');assert reg[mapping['B']]['data']['references']['base']==mapping['A'];assert reg[mapping['A']]['data']['source_id']!='manual:test:A';s.store.close()

def test_cross_project_requires_explicit_scope_and_no_partial_write(tmp_path):
 s=setup(tmp_path);assert callable(getattr(s,'relocate_manual_formulas',None)), 'انتقال امن وجود ندارد';before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):s.relocate_manual_formulas('P',['A','B'],destination={'project_id':'Q','block':'بلوک۱','floor':'اول','location':'A'},mode='move',expected_revisions={'A':1,'B':1},reason='بین پروژه')
 assert s.open_project('P')==before and not s.load_manual_formulas('Q');s.store.close()

def test_move_cas_reopen_undo_and_committed_block(tmp_path):
 s=setup(tmp_path);dest={'project_id':'P','block':'B','floor':'۲','location':'آکس۲'}
 s.relocate_manual_formulas('P',['A','B'],destination=dest,mode='move',expected_revisions={'A':1,'B':1},reason='انتقال')
 with pytest.raises(RuntimeError):s.relocate_manual_formulas('P',['A','B'],destination={**dest,'floor':'۳'},mode='move',expected_revisions={'A':1,'B':1},reason='کهنه')
 s.store.close();s=StructuralProApp(tmp_path);assert s.load_manual_formulas('P')['A']['data']['floor']=='۲';s.undo_manual_formulas('P');assert s.load_manual_formulas('P')['A']['data']['floor']=='اول'
 r=s.load_manual_formulas('P')['A'];s.review_manual_formula('P','A',expected_revision=r['revision'],reviewer='بازبین',note='کنترل');s.commit_manual_formula('P','A',expected_revision=r['revision'])
 with pytest.raises(ValueError):s.relocate_manual_formulas('P',['A'],destination=dest,mode='move',expected_revisions={'A':r['revision']},reason='قطعی')
 s.store.close()

def test_copy_deductions_requires_new_documented_geometry_source(tmp_path):
 s=setup(tmp_path)
 s.set_manual_formula_deduction('P','A',{'id':'volume:old','source_id':'volume:old','variable':'حفره','quantity':'1','unit':'m3','basis':'حجم صریح'},expected_revision=1,reason='کسر')
 reg=s.load_manual_formulas('P');versions={k:reg[k]['revision'] for k in ['A','B']};dest={'project_id':'P','block':'بلوک۳','floor':'سوم','location':'آکس۳'}
 with pytest.raises(ValueError):s.relocate_manual_formulas('P',['A','B'],destination=dest,mode='copy',expected_revisions=versions,reason='کپی بدون منبع')
 mapping=s.relocate_manual_formulas('P',['A','B'],destination=dest,mode='copy',expected_revisions=versions,reason='کپی با هویت صریح',deduction_sources={'A':{'volume:old':'volume:new'}})
 copied=s.load_manual_formulas('P')[mapping['A']];assert copied['quantity']==5 and copied['data']['deductions'][0]['source_id']=='volume:new';s.store.close()

def _move_worker(path,event,queue):
 s=StructuralProApp(path);event.wait()
 try:s.relocate_manual_formulas('P',['A','B'],destination={'project_id':'P','block':'بلوک۲','floor':'دوم','location':'آکس۲'},mode='move',expected_revisions={'A':1,'B':1},reason='انتقال هم‌زمان');queue.put('MOVED')
 except (RuntimeError,ValueError):queue.put('BLOCKED')
 finally:s.store.close()

def test_two_process_location_cas_one_winner(tmp_path):
 import multiprocessing as mp
 s=setup(tmp_path);s.store.close();ctx=mp.get_context('spawn');event=ctx.Event();queue=ctx.Queue();ps=[ctx.Process(target=_move_worker,args=(str(tmp_path),event,queue)) for _ in range(2)]
 for p in ps:p.start()
 event.set();results=[queue.get(timeout=15) for p in ps]
 for p in ps:p.join(15);assert p.exitcode==0
 assert sorted(results)==['BLOCKED','MOVED'];s=StructuralProApp(tmp_path);assert s.load_manual_formulas('P')['A']['revision']==2;s.store.close()
