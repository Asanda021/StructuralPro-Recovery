"""Synthetic, read-only phase-one physical joint ownership / quantity guards.

These tests do not assert structural design, drawings authenticity or BOQ rights.
"""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.column_joint_preflight import POLICY, KINDS, PENDING, preview, preview_file


def sample_project():
    column = {'status':'draft','revision':1,'data':{
        'kind':'column','floor_id':'L1','member_id':'C1','physical_id':'COL-PH',
        'geometry':{'physical_id':'COL-PH','source_ref':'جزئیات مصنوعی'},
        'source':{'approved_by':'ColumnAuthor'},
        'rebars':{'ties':{'segments':[{'id':'OLD-TIE','physical_id':'OLD-BAR'}]}}}}
    beam = {'status':'draft','revision':2,'data':{
        'floor_id':'L1','beam_id':'B1','physical_id':'BEAM-PH',
        'geometry':{'physical_id':'BEAM-PH'},
        'bars':{'stirrups':{'segments':[{'id':'B-TIE'}]}}}}
    return {'id':'P','reviewed_structural_members':{'c':column},
            'beam_detail_register':{'b':beam},'boq':[{'legacy':'kept'}],
            'takeoffs':[{'legacy':'kept'}]}


def sample_doc(project=None):
    project=project or sample_project()
    c=project['reviewed_structural_members']['c'];b=project['beam_detail_register']['b']
    links=[{'role':'column','kind':'column','floor_id':'L1','member_id':'C1',
            'physical_id':'COL-PH','record_revision':1,'record_sha256':_digest(c)},
           {'role':'counterpart','kind':'beam','floor_id':'L1','member_id':'B1',
            'physical_id':'BEAM-PH','record_revision':2,'record_sha256':_digest(b)}]
    ops={k:{'status':'not_applicable','detail_reference':'دیتایل نمونه',
            'reviewed_by':'JointReviewer','reason':'در این نمونه وجود ندارد','pieces':[]}
         for k in KINDS+PENDING}
    basis={'id':'A','physical_id':'NEW-PH','source_ref':'D1','approved_by':'Engineer'}
    ops['critical_ties'].update(status='confirmed',reason='',pieces=[{
        **basis,'count':'3','cut_length_m':'1.250','unit_weight_kg_m':'0.4',
        'unit_weight_ref':'کاتالوگ تست'}])
    ops['embedded_plates'].update(status='confirmed',reason='',pieces=[{
        **basis,'id':'B','physical_id':'PLATE-PH','count':'2',
        'length_m':'0.5','width_m':'0.2','thickness_m':'0.01',
        'density_kg_m3':'7850','density_ref':'مدرک جرم حجمی'}])
    ops['shear_connectors'].update(status='confirmed',reason='',pieces=[{
        **basis,'id':'C','physical_id':'CON-PH','count':'4',
        'unit_mass_kg':'0.15','unit_mass_ref':'کاتالوگ سازنده'}])
    return {'policy':POLICY,'project_id':'P','joint_id':'J1',
            'coordinate_ref':'A-1','detail_reference':'جزئیات اتصال نمونه',
            'prepared_by':'JointAuthor','reviewer':'JointReviewer','links':links,'operations':ops}


def test_exact_three_material_calculations_never_become_boq():
    project=sample_project();doc=sample_doc(project);original=deepcopy((project,doc))
    result=preview(doc,project)
    assert result['status']=='COLUMN_JOINT_PREVIEW_ONLY'
    assert result['ready_for_boq'] is False and result['commit_allowed'] is False and result['rows']==[]
    assert {x['operation']:Decimal(x['quantity']) for x in result['measurements']}=={
        'critical_ties':Decimal('1.5000'),'embedded_plates':Decimal('15.7000'),
        'shear_connectors':Decimal('0.60')}
    assert (project,doc)==original


def test_exact_string_values_not_rounded_by_binary_float():
    d=sample_doc();d['operations']['critical_ties']['pieces'][0]['unit_weight_kg_m']='0.123456789012345678901234567890'
    out=preview(d,sample_project())
    assert out['measurements'][0]['quantity']=='0.462962958796296295879629629587500'


@pytest.mark.parametrize('mutation',[
    lambda d,p:d.update(project_id='OTHER'),
    lambda d,p:d.update(policy='legacy'),
    lambda d,p:d.update(reviewer='JointAuthor'),
    lambda d,p:d['links'].pop(),
    lambda d,p:d['links'].append(deepcopy(d['links'][0])),
    lambda d,p:d['links'][0].update(record_revision=2),
    lambda d,p:d['links'][0].update(record_sha256='f'*64),
    lambda d,p:d['links'][0].update(physical_id='NO-PH'),
    lambda d,p:d['links'][1].update(physical_id='COL-PH'),
    lambda d,p:d['links'][1].update(kind='column'),
    lambda d,p:d['links'][1].update(floor_id='L2'),
    lambda d,p:d['links'][1].update(kind='unknown'),
    lambda d,p:d['operations'].pop('construction_joint'),
    lambda d,p:d['operations']['panel_zone'].update(status='confirmed',reason='',pieces=[{'id':'NOT_SUPPORTED'}]),
    lambda d,p:d['operations']['critical_ties'].update(status='unreviewed'),
    lambda d,p:d['operations']['critical_ties']['pieces'][0].update(count=3.0),
    lambda d,p:d['operations']['critical_ties']['pieces'][0].update(count=True),
    lambda d,p:d['operations']['critical_ties']['pieces'][0].update(count='1.5'),
    lambda d,p:d['operations']['critical_ties']['pieces'][0].update(cut_length_m='NaN'),
    lambda d,p:d['operations']['critical_ties']['pieces'][0].update(unit_weight_kg_m='Infinity'),
    lambda d,p:d['operations']['critical_ties']['pieces'][0].update(physical_id='OLD-BAR'),
    lambda d,p:d['operations']['critical_ties']['pieces'][0].update(physical_id='B-TIE'),
    lambda d,p:d['operations']['critical_ties']['pieces'][0].update(physical_id='COL-PH'),
    lambda d,p:d['operations']['embedded_plates']['pieces'][0].update(physical_id='NEW-PH'),
    lambda d,p:d['operations']['embedded_plates']['pieces'][0].update(id='A'),
    lambda d,p:p['reviewed_structural_members'].update(third={'status':'draft','revision':1,'data':{
        'kind':'column','floor_id':'L1','member_id':'C3','geometry':{'physical_id':'COL-OTHER'},
        'rebars':{'ties':{'segments':[{'physical_id':'NEW-PH'}]}}}}),
    lambda d,p:d['operations']['critical_ties']['pieces'][0].update(source_ref=''),
    lambda d,p:d['operations']['shear_connectors']['pieces'][0].update(unit_mass_ref=''),
    lambda d,p:d['operations']['embedded_plates']['pieces'][0].update(thickness_m='-0.01'),
    lambda d,p:d['operations']['critical_ties'].update(reviewed_by='JointAuthor'),
    lambda d,p:d['operations']['critical_ties'].update(reason='فرض'),
    lambda d,p:d['operations']['embedded_plates'].update(status='not_applicable'),
    lambda d,p:p['beam_detail_register'].pop('b'),
    lambda d,p:p['beam_detail_register']['b']['data']['bars']['stirrups']['segments'][0].update(physical_id='NEW-PH'),
])
def test_wrong_identity_undocumented_amount_or_duplicate_fails_closed(mutation):
    project=sample_project();doc=sample_doc(project);mutation(doc,project)
    with pytest.raises(OwnershipError):preview(doc,project)


def test_stale_revision_and_digest_even_if_identity_same():
    project=sample_project();doc=sample_doc(project)
    project['reviewed_structural_members']['c']['revision']=2
    with pytest.raises(OwnershipError):preview(doc,project)
    project['reviewed_structural_members']['c']['revision']=1
    project['reviewed_structural_members']['c']['data']['geometry']['source_ref']='changed'
    with pytest.raises(OwnershipError):preview(doc,project)


def test_alias_of_parent_in_third_registered_member_rejected():
    project=sample_project();doc=sample_doc(project)
    other=deepcopy(project['reviewed_structural_members']['c'])
    other['data']['member_id']='C2'
    project['reviewed_structural_members']['other']=other
    with pytest.raises(OwnershipError,match='هویت'):preview(doc,project)


def test_real_sqlite_snapshot_bytes_checked_and_finances_unchanged(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project('نمونه داده اتصال ستون','P')
    project=app.open_project('P')
    fixture=sample_project()
    project.update({k:deepcopy(fixture[k]) for k in ('reviewed_structural_members','beam_detail_register')})
    app.store.save('P',project)
    saved=app.open_project('P');doc=sample_doc(saved)
    payload=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    path=tmp_path/'joint.json';path.write_bytes(payload)
    digest=sha256(payload).hexdigest()
    before=deepcopy(saved)
    out=preview_file(saved,str(path),digest)
    assert out['rows']==[] and not out['ready_for_boq']
    assert app.open_project('P')==before
    path.write_bytes(payload+b'\n')
    with pytest.raises(OwnershipError):preview_file(saved,str(path),digest)
    assert app.store.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    app.store.close()
    second=StructuralProApp(tmp_path)
    try:
        assert second.open_project('P')==before
        assert preview(doc,second.open_project('P'))['rows']==[]
    finally:second.store.close()


def test_stale_sqlite_snapshot_after_external_change_fails(tmp_path):
    app=StructuralProApp(tmp_path);app.create_project('مصنوعی','P')
    base=sample_project();project=app.open_project('P')
    project.update({k:deepcopy(base[k]) for k in ('reviewed_structural_members','beam_detail_register')})
    app.store.save('P',project)
    saved=app.open_project('P');doc=sample_doc(saved)
    second=StructuralProApp(tmp_path)
    altered=second.open_project('P')
    altered['reviewed_structural_members']['c']['revision']=2
    second.store.save('P',altered)
    with pytest.raises(OwnershipError):preview(doc,app.open_project('P'))
    second.store.close();app.store.close()
