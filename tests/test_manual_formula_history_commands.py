from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp
from test_manual_formula_persistence import data

def test_delete_undo_redo_monotonic_revision_and_source(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول')
 assert callable(getattr(s,'delete_manual_formulas',None)), 'حذف کنترل‌شده فرمول وجود ندارد'
 s.delete_manual_formulas('P',['A'],expected_revisions={'A':1},reason='حذف پیش‌نویس');assert not s.load_manual_formulas('P')
 s.undo_manual_formulas('P');a=s.load_manual_formulas('P')['A'];assert a['revision']>1 and a['data']['source_id']=='manual:test:A'
 s.redo_manual_formulas('P');assert not s.load_manual_formulas('P');s.undo_manual_formulas('P');assert s.load_manual_formulas('P')['A']['revision']>a['revision'];s.store.close()

def test_reference_and_committed_delete_undo_are_blocked(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول')
 assert callable(getattr(s,'delete_manual_formulas',None)), 'حذف امن وجود ندارد'
 s.save_manual_formula('P','B',data(source_id='B',member='C2',variables={},references={'base':'A'},expression='base*2'),expected_revision=0,reason='وابسته');before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):s.delete_manual_formulas('P',['A'],expected_revisions={'A':1},reason='حذف مرجع')
 assert s.open_project('P')==before
 s.review_manual_formula('P','A',expected_revision=1,reviewer='بازبین',note='کنترل');s.commit_manual_formula('P','A',expected_revision=1)
 with pytest.raises(ValueError):s.delete_manual_formulas('P',['A'],expected_revisions={'A':1},reason='حذف قطعی')
 with pytest.raises(ValueError):s.undo_manual_formulas('P')
 assert len(s.open_project('P')['boq'])==1;s.store.close()
