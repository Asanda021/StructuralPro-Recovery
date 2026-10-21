"""Bounded construction joint and repair geometry on documented source files."""
from copy import deepcopy
import json

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.column_joint_interface_surface import POLICY, preview, preview_file
from test_column_joint_footing_tie_phase1 import fixture, write


def setup(tmp_path, kind='isolated_footing'):
    p, contact=fixture(tmp_path,kind=kind)
    f=tmp_path/'contact.json';sha=write(f,contact)
    if kind=='tie_beam':
        joint_rect=dict(x_min_m='0.4',x_max_m='0.4',y_min_m='-0.1',y_max_m='0.1',
                        z_min_m='1.25',z_max_m='1.75')
        repair_rect=dict(x_min_m='0.4',x_max_m='0.4',y_min_m='-0.05',y_max_m='0.05',
                         z_min_m='1.4',z_max_m='1.6')
        ja='0.10';volume='0.001'
    else:
        joint_rect=dict(x_min_m='-0.2',x_max_m='0.2',y_min_m='-0.2',y_max_m='0.2',
                        z_min_m='0',z_max_m='0')
        repair_rect=dict(x_min_m='0',x_max_m='0.2',y_min_m='0',y_max_m='0.2',
                         z_min_m='0',z_max_m='0')
        ja='0.16';volume='0.002'
    d={'policy':POLICY,'project_id':'P','joint_id':'J-C1',
       'contact_document':{'path':str(f.resolve()),'sha256':sha,'reference':'Contact evidence'},
       'prepared_by':'InterfaceAuthor','reviewer':'InterfaceReviewer',
       'joint':{'status':'documented','surface':joint_rect,'declared_area_m2':ja,
                'surface_treatment_ref':'Reference-Prep-1',
                'detail_ref':'Independent-Joint-Drawing','approved_by':'JointDesigner'},
       'repair':{'status':'documented','surface':repair_rect,'physical_patch_id':'REPAIR-PH-1',
                 'owner_role':'column','thickness_m':'0.05','declared_volume_m3':volume,
                 'detail_ref':'Repair-Detail','approved_by':'RepairDesigner','reason':''}}
    return p,d


@pytest.mark.parametrize('kind',['isolated_footing','strip_footing','mat_footing','tie_beam'])
def test_joint_and_repair_geometry_not_boq(tmp_path,kind):
    p,d=setup(tmp_path,kind=kind);orig=deepcopy((p,d))
    r=preview(d,p)
    assert r['status']=='CONSTRUCTION_JOINT_REPAIR_PREVIEW_ONLY'
    assert r['rows']==[] and r['ready_for_boq'] is False and r['commit_allowed'] is False
    assert r['observations'][1]['max_envelope_m3']==('0.00100' if kind=='tie_beam' else '0.0020')
    assert (p,d)==orig


def test_explicitly_no_repair_does_not_claim_volume(tmp_path):
    p,d=setup(tmp_path)
    d['repair']={'status':'not_applicable','surface':{},'physical_patch_id':'',
                 'owner_role':'','thickness_m':'','declared_volume_m3':'',
                 'detail_ref':'','approved_by':'','reason':'فاقد دستور ترمیم در سناریوی نمونه'}
    r=preview(d,p)
    assert len(r['observations'])==1 and r['observations'][0]['area_m2']=='0.16'


@pytest.mark.parametrize('fault',[
    'wrong_policy','wrong_project','bad_joint','same_reviewer','bad_contact_sha',
    'changed_contact','missing_member','stale_member',
    'joint_not_documented','wrong_joint_area','float_joint_area','joint_area_nan',
    'wrong_joint_plane','joint_outside_face','joint_zero_area',
    'missing_prep','joint_same_reviewer','missing_joint_detail',
    'repair_wrong_volume','repair_float_volume','repair_zero_thickness',
    'repair_negative_thickness','repair_too_deep','repair_wrong_plane',
    'repair_outside_face','repair_edge_only','repair_same_reviewer',
    'repair_same_member_physical','repair_wrong_side','repair_no_detail',
    'repair_bad_status','no_repair_with_volume','no_repair_no_reason',
    'repair_with_reason','extra_field','missing_surface','float_geometry',
    'bool_geometry','null_geometry','nan_geometry',
])
def test_bad_surface_or_documented_repair_fails_closed(tmp_path,fault):
    p,d=setup(tmp_path)
    joint=d['joint'];repair=d['repair'];surface=repair['surface']
    if fault=='wrong_policy':d['policy']='OLD'
    elif fault=='wrong_project':d['project_id']='OTHER'
    elif fault=='bad_joint':d['joint_id']='OTHER'
    elif fault=='same_reviewer':d['reviewer']='InterfaceAuthor'
    elif fault=='bad_contact_sha':d['contact_document']['sha256']='0'*64
    elif fault=='changed_contact':(tmp_path/'contact.json').write_text('{}')
    elif fault=='missing_member':p['reviewed_structural_members'].pop('F')
    elif fault=='stale_member':p['reviewed_structural_members']['C']['revision']+=1
    elif fault=='joint_not_documented':joint['status']='unreviewed'
    elif fault=='wrong_joint_area':joint['declared_area_m2']='0.17'
    elif fault=='float_joint_area':joint['declared_area_m2']=0.16
    elif fault=='joint_area_nan':joint['declared_area_m2']='NaN'
    elif fault=='wrong_joint_plane':joint['surface']['z_min_m']='0.01'
    elif fault=='joint_outside_face':joint['surface']['x_max_m']='0.5'
    elif fault=='joint_zero_area':joint['surface']['x_min_m']='0.2'
    elif fault=='missing_prep':joint['surface_treatment_ref']=''
    elif fault=='joint_same_reviewer':joint['approved_by']='InterfaceReviewer'
    elif fault=='missing_joint_detail':joint['detail_ref']=''
    elif fault=='repair_wrong_volume':repair['declared_volume_m3']='0.003'
    elif fault=='repair_float_volume':repair['declared_volume_m3']=0.002
    elif fault=='repair_zero_thickness':repair['thickness_m']='0'
    elif fault=='repair_negative_thickness':repair['thickness_m']='-0.1'
    elif fault=='repair_too_deep':repair['thickness_m']='3.1'
    elif fault=='repair_wrong_plane':surface['z_max_m']='0.1'
    elif fault=='repair_outside_face':surface['x_max_m']='0.6'
    elif fault=='repair_edge_only':surface['x_min_m']='0.2'
    elif fault=='repair_same_reviewer':repair['approved_by']='InterfaceReviewer'
    elif fault=='repair_same_member_physical':repair['physical_patch_id']='COLUMN-PH'
    elif fault=='repair_wrong_side':repair['owner_role']='unregistered'
    elif fault=='repair_no_detail':repair['detail_ref']=''
    elif fault=='repair_bad_status':repair['status']='confirmed_paid'
    elif fault=='no_repair_with_volume':repair['status']='not_applicable';repair['reason']='No repair';repair['surface']={}
    elif fault=='no_repair_no_reason':repair['status']='not_applicable';repair['reason']='';repair['surface']={}
    elif fault=='repair_with_reason':repair['reason']='none'
    elif fault=='extra_field':joint['paid']=True
    elif fault=='missing_surface':repair.pop('surface')
    elif fault=='float_geometry':surface['x_max_m']=0.2
    elif fault=='bool_geometry':surface['y_min_m']=True
    elif fault=='null_geometry':surface['y_max_m']=None
    elif fault=='nan_geometry':surface['z_min_m']='NaN'
    with pytest.raises(OwnershipError):preview(d,p)


def test_sqlite_roundtrip_read_only_and_checked_bytes(tmp_path):
    app=StructuralProApp(tmp_path/'db');app.create_project('آزمون فرضی ترمیم','P')
    p,d=setup(tmp_path)
    project=app.open_project('P')
    project.update({k:deepcopy(p[k]) for k in ('reviewed_structural_members','beam_detail_register')})
    app.store.save('P',project)
    before=app.open_project('P');saved=deepcopy(before)
    path=tmp_path/'surface.json';digest=write(path,d)
    assert not preview_file(before,str(path),digest)['commit_allowed']
    assert app.open_project('P')==saved
    assert app.store.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    app.store.close()
    other=StructuralProApp(tmp_path/'db')
    try:
        after=other.open_project('P');assert after==saved
        after['reviewed_structural_members']['F']['revision']+=1
        other.store.save('P',after)
        with pytest.raises(OwnershipError):preview(d,other.open_project('P'))
    finally:other.store.close()
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):preview_file(saved,str(path),digest)
