from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp
from test_manual_formula_persistence import data

def base(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول');s.review_manual_formula('P','A',expected_revision=1,reviewer='مهندس اولیه',note='کنترل');s.commit_manual_formula('P','A',expected_revision=1);return s

def ready(s):assert callable(getattr(s,'create_manual_formula_amendment',None)), 'اصلاحیه ردیف قطعی وجود ندارد'

def proposal():return data(variables={'length':'5','width':'0.2','height':'3'})

def test_amendment_independent_review_original_immutable_reopen(tmp_path):
 s=base(tmp_path);ready(s);before=deepcopy(s.open_project('P'));a=s.create_manual_formula_amendment('P','A',proposal(),expected_revision=1,created_by='سازنده',reason='اصلاح طول با ورودی صریح')
 assert s.open_project('P')['boq']==before['boq']
 with pytest.raises(ValueError):s.apply_manual_formula_amendment('P',a['id'],expected_revision=1)
 with pytest.raises(ValueError):s.review_manual_formula_amendment('P',a['id'],expected_revision=1,reviewer='سازنده',note='کنترل')
 s.review_manual_formula_amendment('P',a['id'],expected_revision=1,reviewer='بازبین مستقل',note='طول و واحد بررسی شد');s.apply_manual_formula_amendment('P',a['id'],expected_revision=1)
 p=s.open_project('P');assert p['takeoffs']==before['takeoffs'];assert p['manual_formula_register']['A']==before['manual_formula_register']['A'];assert len(p['boq'])==1 and p['boq'][0]['quantity']==3
 assert s.load_manual_formulas('P')['A']['revision']==2;assert s.load_manual_formulas('P')['A']['quantity']==3
 with pytest.raises(ValueError):s.apply_manual_formula_amendment('P',a['id'],expected_revision=1)
 s.store.close();s=StructuralProApp(tmp_path);assert s.load_manual_formulas('P')['A']['quantity']==3;assert s.open_project('P')['boq'][0]['quantity']==3;s.store.close()

@pytest.mark.parametrize('scope',['statement_periods','estimate','contract','financial_requests'])
def test_financial_scope_blocks_without_modifying_issued_basis(tmp_path,scope):
 s=base(tmp_path);ready(s);p=s.open_project('P');p[scope]=[{'issued':'synthetic'}] if scope=='statement_periods' else {'synthetic':True};s.store.save('P',p)
 a=s.create_manual_formula_amendment('P','A',proposal(),expected_revision=1,created_by='سازنده',reason='اصلاح');s.review_manual_formula_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):s.apply_manual_formula_amendment('P',a['id'],expected_revision=1)
 assert s.open_project('P')==before;s.store.close()

def test_stale_amendment_and_direct_store_tamper_blocked(tmp_path):
 s=base(tmp_path);ready(s);ids=[]
 for _ in range(2):
  a=s.create_manual_formula_amendment('P','A',proposal(),expected_revision=1,created_by='سازنده',reason='اصلاح');s.review_manual_formula_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');ids.append(a['id'])
 s.apply_manual_formula_amendment('P',ids[0],expected_revision=1)
 with pytest.raises(RuntimeError):s.apply_manual_formula_amendment('P',ids[1],expected_revision=1)
 p=s.open_project('P');p['manual_formula_applied']['A']=ids[1]
 with pytest.raises(ValueError):s.store.save('P',p)
 s.store.close()

def _race_worker(path,aid,event,queue):
 s=StructuralProApp(path);event.wait()
 try:s.apply_manual_formula_amendment('P',aid,expected_revision=1);queue.put('APPLIED')
 except (RuntimeError,ValueError):queue.put('BLOCKED')
 finally:s.store.close()

def test_two_processes_apply_one_cas_winner(tmp_path):
 import multiprocessing as mp
 s=base(tmp_path);a=s.create_manual_formula_amendment('P','A',proposal(),expected_revision=1,created_by='سازنده',reason='اصلاح');s.review_manual_formula_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.store.close()
 ctx=mp.get_context('spawn');event=ctx.Event();queue=ctx.Queue();processes=[ctx.Process(target=_race_worker,args=(str(tmp_path),a['id'],event,queue)) for _ in range(2)]
 for p in processes:p.start()
 event.set();answers=[queue.get(timeout=15) for _ in processes]
 for p in processes:p.join(15);assert p.exitcode==0
 assert sorted(answers)==['APPLIED','BLOCKED'];s=StructuralProApp(tmp_path);assert s.open_project('P')['boq'][0]['quantity']==3;assert len(s.open_project('P')['boq'])==1;s.store.close()

def test_direct_boq_and_original_takeoff_tamper_blocked(tmp_path):
 s=base(tmp_path);p=deepcopy(s.open_project('P'));p['boq'][0]['quantity']=999
 with pytest.raises(ValueError):s.store.save('P',p)
 p=deepcopy(s.open_project('P'));p['takeoffs'][0]['quantities'][0]['amount']=999
 with pytest.raises(ValueError):s.store.save('P',p)
 assert s.open_project('P')['boq'][0]['quantity']==6;s.store.close()
