"""Phase-1 branches 2/3/4: bounded synthetic regression, not owner acceptance."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest

from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.phase1_shared_materials_audit import POLICY as MATERIAL_POLICY, audit as material_audit
from core.takeoff.phase1_pile_center_evidence import POLICY as PILE_POLICY, audit as pile_center_audit
from core.takeoff.reviewed_aec import preview_system
from core.takeoff.roof_detail import KINDS as ROOF_KINDS
from core.takeoff.engine import TakeoffEngine
from test_column_joint_footing_tie_phase1 import fixture as face_fixture
from test_bored_pile_spatial_overlap import case as pile_fixture
from test_roof_specialist_work import sample as slab_sample
from test_waffle_specialist_work import sample as waffle_sample
from test_hollowcore_specialist_work import sample as hollow_sample
from test_void_former_roofs_20261016 import sample as void_sample


def material_setup(tmp_path):
    project,_=face_fixture(tmp_path)
    base=[]
    for material,role,key,physical in [('concrete','column','C','C-CONC'),
                                       ('formwork','isolated_footing','F','F-FORM'),
                                       ('rebar','column','C','C-REBAR')]:
        record=project['reviewed_structural_members'][key]
        base.append({'material_kind':material,'physical_material_id':physical,
                     'member_kind':role,'floor_id':record['data']['floor_id'],
                     'member_id':record['data']['member_id'],
                     'source_ref':'پلان مصنوعی','detail_ref':'دیتایل مشخص',
                     'member_revision':record['revision'],'member_record_sha256':_digest(record)})
    doc={'policy':MATERIAL_POLICY,'project_id':'P','prepared_by':'Author',
         'reviewer':'IndependentReviewer','claims':base}
    return project,doc


def test_all_three_shared_material_types_readonly(tmp_path):
    project,doc=material_setup(tmp_path)
    before=deepcopy((project,doc))
    result=material_audit(project,doc)
    assert result['verified_registered_claim_count']==3
    assert result['rows']==[] and not result['ready_for_boq'] and not result['commit_allowed']
    assert (project,doc)==before

@pytest.mark.parametrize('fault', ['duplicate','stale','wrong_member','bad_kind','float_revision',
                                   'wrong_project','same_reviewer','bad_record','empty','extra'])
def test_shared_material_fail_closed(tmp_path,fault):
    p,d=material_setup(tmp_path)
    if fault=='duplicate':d['claims'][1]['physical_material_id']='C-CONC'
    elif fault=='stale':p['reviewed_structural_members']['C']['revision']=5
    elif fault=='wrong_member':d['claims'][0]['member_id']='MISSING'
    elif fault=='bad_kind':d['claims'][0]['material_kind']='rubber'
    elif fault=='float_revision':d['claims'][0]['member_revision']=2.0
    elif fault=='wrong_project':d['project_id']='X'
    elif fault=='same_reviewer':d['reviewer']='Author'
    elif fault=='bad_record':p['reviewed_structural_members']['F']='bad'
    elif fault=='empty':d['claims']=[]
    else:d['claims'][0]['surprise']='guess'
    with pytest.raises(OwnershipError):material_audit(p,d)


def test_shared_material_histories_remain_blocked(tmp_path):
    p,d=material_setup(tmp_path)
    p['takeoffs']=[{'id':'previous','params':{'component_physical_id':'C-CONC'}}]
    p['boq']=[{'id':'historical','quantity':'99'}]
    before=deepcopy(p)
    result=material_audit(p,d)
    assert any('دوباره‌شماری' in b for b in result['blockers'])
    assert result['rows']==[] and p==before


def center_setup(tmp_path):
    data,compiled,owner,joint,project,spatial=pile_fixture(tmp_path)
    centers=[{'pile_id':p['id'],'pile_physical_id':p['physical_id'],
              'x_m':'0','y_m':'0','source_ref':'جانمایی مصنوعی'} for p in data['piles']]
    doc={'policy':PILE_POLICY,'project_id':data['project_id'],
         'floor_id':data['floor_id'],'group_id':data['group_id'],
         'coordinate_ref':data['datum']['coordinate_ref'],
         'vertical_datum_ref':data['datum']['vertical_datum_ref'],
         'input_sha256':compiled['source_sha256'], 'source_reference':'جدول مختصات مستقل',
         'prepared_by':'CoordinatesAuthor','reviewer':'CoordinatesReviewer','centers':centers}
    path=tmp_path/'pile_center.json';raw=json.dumps(doc,ensure_ascii=False,sort_keys=True).encode()
    path.write_bytes(raw)
    return data,compiled,spatial,doc,path,sha256(raw).hexdigest()


def test_every_pile_center_and_spatial_link_match(tmp_path):
    data,compiled,spatial,doc,path,digest=center_setup(tmp_path)
    original=deepcopy((data,compiled,spatial))
    result=pile_center_audit(data,compiled,spatial,center_path=path,center_sha256=digest)
    assert result['checked_link_count']==2
    assert result['rows']==[] and not result['commit_allowed']
    assert (data,compiled,spatial)==original

@pytest.mark.parametrize('fault',['wrong_xy','wrong_input','bad_project','bad_reviewer',
                                  'not_every_pile','repeat','wrong_phys','float_center','wrong_datum',
                                  'tamper_bytes','extra_key','bad_sha','missing_link'])
def test_pile_xy_external_claim_must_match_and_remain_nonfinancial(tmp_path,fault):
    data,compiled,spatial,doc,path,digest=center_setup(tmp_path)
    if fault=='wrong_xy':spatial['links'][0]['pile_center_x_m']='2'
    elif fault=='wrong_input':doc['input_sha256']='f'*64
    elif fault=='bad_project':doc['project_id']='OTHER'
    elif fault=='bad_reviewer':doc['reviewer']='CoordinatesAuthor'
    elif fault=='not_every_pile':doc['centers']=[]
    elif fault=='repeat':doc['centers'].append(deepcopy(doc['centers'][0]))
    elif fault=='wrong_phys':doc['centers'][0]['pile_physical_id']='OTHER'
    elif fault=='float_center':doc['centers'][0]['x_m']=0.0
    elif fault=='wrong_datum':doc['vertical_datum_ref']='WRONG'
    elif fault=='extra_key':doc['guess']=True
    elif fault=='bad_sha':digest='f'*64
    elif fault=='missing_link':spatial['links']=[]
    if fault in ('wrong_input','bad_project','bad_reviewer','not_every_pile','repeat',
                 'wrong_phys','float_center','wrong_datum','extra_key'):
        payload=json.dumps(doc,ensure_ascii=False,sort_keys=True).encode()
        path.write_bytes(payload);digest=sha256(payload).hexdigest()
    if fault=='tamper_bytes':path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):
        pile_center_audit(data,compiled,spatial,center_path=path,center_sha256=digest)


_FACTORIES={'solid_slab':slab_sample,'joist_block':slab_sample,
            'joist_foam':slab_sample,'waffle_one_way':waffle_sample,
            'waffle_two_way':waffle_sample,'hollow_core_detail':hollow_sample,
            'uboot':void_sample,'cobiax':void_sample}

def test_all_eight_roofs_have_exact_specialist_contract():
    assert set(ROOF_KINDS)==set(_FACTORIES)
    assert len(ROOF_KINDS)==8

@pytest.mark.parametrize('kind', sorted(_FACTORIES))
def test_eight_roof_sources_preview_without_mutation_or_duplicate_quantities(kind):
    data=_FACTORIES[kind](kind);before=deepcopy(data)
    result=preview_system(data,TakeoffEngine())
    assert result['ready'], result['blockers']
    assert result['rows'] and all(r.get('quantity') is not None for r in result['rows'])
    assert data==before

@pytest.mark.parametrize('kind', sorted(_FACTORIES))
def test_eight_roof_unknown_drawing_scale_is_rejected(kind):
    data=_FACTORIES[kind](kind)
    data['source']['mode']='drawing'
    result=preview_system(data,TakeoffEngine())
    assert not result['ready'] and result['blockers']

@pytest.mark.parametrize('kind', sorted(_FACTORIES))
def test_eight_roof_duplicate_physical_rebar_is_rejected(kind):
    data=_FACTORIES[kind](kind)
    groups=data['roof_detail']['rebars']
    supported=[x for x in groups.values() if x.get('status')=='confirmed' and x.get('series')]
    assert len(supported)>=2
    supported[1]['series'][0]['physical_key']=supported[0]['series'][0]['physical_key']
    result=preview_system(data,TakeoffEngine())
    assert not result['ready'] and result['blockers']

@pytest.mark.parametrize('kind', sorted(_FACTORIES))
def test_eight_roof_draft_roundtrip_retains_original_boq(tmp_path,kind):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db')
    try:
        app.create_project('سقف مستقل مصنوعی','P')
        old=app.open_project('P')
        data=_FACTORIES[kind](kind)
        saved=app.save_aec_system_draft('P',data,expected_revision=0)
        assert saved['revision']==1
        after=app.open_project('P')
        assert after['boq']==old['boq'] and after['takeoffs']==old['takeoffs']
        assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    finally:app.store.close()
    second=StructuralProApp(tmp_path/'db')
    try:
        rec=second.get_aec_system('P',kind,'L1','S1')
        assert rec['revision']==1 and rec['data']['kind']==kind
        assert second.open_project('P')['boq']==old['boq']
    finally:second.store.close()
