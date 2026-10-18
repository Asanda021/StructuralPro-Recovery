"""Synthetic beam/column panel geometry acceptance; never financial approval."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.column_joint_beam_panel import POLICY, PRISM_POLICY, POINTER_KEY, preview, preview_file
from test_column_joint_preflight_phase1 import sample_project


def write(path, data):
    raw=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')
    path.write_bytes(raw)
    return sha256(raw).hexdigest()


def case(tmp_path):
    p=sample_project(); p['boq']=[{'legacy':'protected'}]
    boxes={
        'column':{'x_min_m':'-0.4','y_min_m':'-0.4','z_min_m':'0',
                  'x_max_m':'0.4','y_max_m':'0.4','z_max_m':'3'},
        'counterpart':{'x_min_m':'0','y_min_m':'-0.2','z_min_m':'1',
                       'x_max_m':'2','y_max_m':'0.2','z_max_m':'2'}}
    links=[]
    for role, registry, key, kind, member, physical, version in (
        ('column','reviewed_structural_members','c','column','C1','COL-PH',1),
        ('counterpart','beam_detail_register','b','beam','B1','BEAM-PH',2)):
        rec=p[registry][key];data=rec['data'];g=data['geometry']
        g['source_ref']='پلان هندسی مصنوعی '+role
        g['source_sha256']=('a' if role=='column' else 'b')*64
        data['source']={'approved_by':'SourceReviewer'+role}
        source={'policy':PRISM_POLICY,'project_id':'P','role':role,'kind':kind,
                'floor_id':'L1','member_id':member,'physical_id':physical,
                'coordinate_ref':'GRID-A','vertical_datum_ref':'ELEV-1',
                'geometry_source_ref':g['source_ref'],
                'geometry_source_sha256':g['source_sha256'],
                'prepared_by':'PrismAuthor'+role,'reviewer':'PrismReviewer'+role,
                **boxes[role]}
        fp=tmp_path/(role+'.json'); digest=write(fp,source)
        g[POINTER_KEY]={'policy':PRISM_POLICY,'path':str(fp.resolve()),
                        'sha256':digest,'reference':'Synthetic footprint '+role,
                        'coordinate_ref':'GRID-A','vertical_datum_ref':'ELEV-1',
                        'physical_id':physical}
        links.append({'role':role,'kind':kind,'floor_id':'L1','member_id':member,
                      'physical_id':physical,'record_revision':version,
                      'record_sha256':_digest(rec)})
    doc={'policy':POLICY,'project_id':'P','joint_id':'J1',
         'coordinate_ref':'GRID-A','vertical_datum_ref':'ELEV-1',
         'detail_ref':'Synthetic geometry of joint J1','prepared_by':'JointAuthor',
         'reviewer':'JointReviewer','links':links,
         'panel_zone':{'id':'Z1','physical_id':'JOINT-ONLY-Z1',
                       'detail_ref':'Synthetic panel bounds','approved_by':'PanelAuthor',
                       'x_min_m':'0','x_max_m':'0.4',
                       'y_min_m':'-0.1','y_max_m':'0.1',
                       'z_min_m':'1.25','z_max_m':'1.75'},
         'connection_volume_m3':'0.16','panel_volume_m3':'0.04',
         'reinforcement_status':'not_reconciled',
         'ownership_status':'unresolved',
         'ownership_reason':'لازم است توسط دفتر فنی احراز شود'}
    return p,doc


def test_exact_intersection_and_explicit_panel_are_not_two_concrete_payments(tmp_path):
    project,document=case(tmp_path);before=deepcopy((project,document))
    out=preview(document,project)
    assert out['status']=='BEAM_COLUMN_PANEL_PREVIEW_ONLY'
    assert out['member_geometry_record_bound'] is True
    assert out['ready_for_boq'] is False and out['commit_allowed'] is False and out['rows']==[]
    assert out['observations']==[
        {'operation':'beam_column_connection','volume_m3':'0.16','unit':'m3','basis':'rectangular_3d_intersection'},
        {'operation':'panel_zone','volume_m3':'0.0400','unit':'m3','basis':'documented_rectangular_subset'},
    ]
    assert (project,document)==before


def test_high_precision_decimal_without_rounding(tmp_path):
    project,doc=case(tmp_path)
    # Exactly one additional ten-thousandth of a meter on the x side.
    beam=project['beam_detail_register']['b']
    source_path=tmp_path/'counterpart.json';source=json.loads(source_path.read_text())
    source['x_min_m']='-0.0001';beam['data']['geometry'][POINTER_KEY]['sha256']=write(source_path,source)
    doc['links'][1]['record_sha256']=_digest(beam)
    doc['connection_volume_m3']='0.16004'
    result=preview(doc,project)
    assert Decimal(result['observations'][0]['volume_m3'])==Decimal('0.16004')


@pytest.mark.parametrize('modify', [
    lambda d,p,t:d.update(policy='invalid'),
    lambda d,p,t:d.update(project_id='OTHER'),
    lambda d,p,t:d.update(reviewer='JointAuthor'),
    lambda d,p,t:d.update(ownership_status='column'),
    lambda d,p,t:d.update(reinforcement_status='approved'),
    lambda d,p,t:d.update(ownership_reason=''),
    lambda d,p,t:d['links'].pop(),
    lambda d,p,t:d['links'].append(deepcopy(d['links'][0])),
    lambda d,p,t:d['links'][0].update(record_sha256='f'*64),
    lambda d,p,t:d['links'][0].update(record_revision=2),
    lambda d,p,t:d['links'][1].update(kind='column'),
    lambda d,p,t:d['links'][1].update(physical_id='COL-PH'),
    lambda d,p,t:d['links'][1].update(floor_id='L2'),
    lambda d,p,t:d.update(connection_volume_m3='0.15'),
    lambda d,p,t:d.update(panel_volume_m3='0.03'),
    lambda d,p,t:d.update(connection_volume_m3=0.16),
    lambda d,p,t:d.update(panel_volume_m3=True),
    lambda d,p,t:d.update(panel_volume_m3='NaN'),
    lambda d,p,t:d['panel_zone'].update(y_max_m='0.30'),
    lambda d,p,t:d['panel_zone'].update(z_max_m='4'),
    lambda d,p,t:d['panel_zone'].update(x_min_m='0.5'),
    lambda d,p,t:d['panel_zone'].update(x_min_m='Infinity'),
    lambda d,p,t:d['panel_zone'].update(x_max_m=0.4),
    lambda d,p,t:d['panel_zone'].update(physical_id='COL-PH'),
    lambda d,p,t:d['panel_zone'].update(physical_id='OLD-BAR'),
    lambda d,p,t:d['panel_zone'].update(approved_by='JointReviewer'),
    lambda d,p,t:p['beam_detail_register'].pop('b'),
    lambda d,p,t:p['reviewed_structural_members']['c'].update(revision=3),
    lambda d,p,t:p['reviewed_structural_members']['c']['data']['geometry'][POINTER_KEY].update(sha256='0'*64),
    lambda d,p,t:p['reviewed_structural_members']['c']['data']['geometry'][POINTER_KEY].update(coordinate_ref='WRONG'),
    lambda d,p,t:p['reviewed_structural_members']['c']['data']['geometry'][POINTER_KEY].update(physical_id='OTHER'),
    lambda d,p,t:p['reviewed_structural_members']['c']['data']['geometry'].pop(POINTER_KEY),
    lambda d,p,t:p['reviewed_structural_members']['c']['data']['geometry'].update(source_sha256='f'*64),
    lambda d,p,t:p['beam_detail_register']['b']['data']['bars']['stirrups']['segments'][0].update(physical_id='OLD-BAR'),
    lambda d,p,t:p['reviewed_structural_members'].update(other={'status':'draft','revision':1,'data':{'geometry':{'physical_id':'BEAM-PH'}}}),
    lambda d,p,t:p['reviewed_structural_members']['c']['data'].update(source={'approved_by':'JointReviewer'}),
    lambda d,p,t:t.joinpath('column.json').write_text('not JSON'),
    lambda d,p,t:t.joinpath('counterpart.json').write_text('{"x":0.3}'),
    lambda d,p,t:t.joinpath('counterpart.json').unlink(),
])
def test_bad_identity_geometry_or_shared_claim_fails_closed(tmp_path,modify):
    project,doc=case(tmp_path)
    modify(doc,project,tmp_path)
    with pytest.raises(OwnershipError):preview(doc,project)


def test_disjoint_beam_and_column_cannot_be_declared_connected(tmp_path):
    project,doc=case(tmp_path)
    path=tmp_path/'counterpart.json';data=json.loads(path.read_text())
    data.update(x_min_m='3',x_max_m='4')
    beam=project['beam_detail_register']['b']
    beam['data']['geometry'][POINTER_KEY]['sha256']=write(path,data)
    doc['links'][1]['record_sha256']=_digest(beam)
    with pytest.raises(OwnershipError,match='حجم مشترک'):preview(doc,project)


def test_exact_boundary_contact_without_joint_volume_is_rejected(tmp_path):
    project,doc=case(tmp_path)
    path=tmp_path/'counterpart.json';data=json.loads(path.read_text())
    data.update(x_min_m='0.4',x_max_m='2.4')
    beam=project['beam_detail_register']['b']
    beam['data']['geometry'][POINTER_KEY]['sha256']=write(path,data)
    doc['links'][1]['record_sha256']=_digest(beam)
    with pytest.raises(OwnershipError,match='حجم مشترک'):preview(doc,project)


def test_prism_json_float_duplicate_key_and_file_tamper_rejected(tmp_path):
    project,doc=case(tmp_path)
    path=tmp_path/'column.json';data=json.loads(path.read_text());data['x_min_m']=0.4
    col=project['reviewed_structural_members']['c']
    col['data']['geometry'][POINTER_KEY]['sha256']=write(path,data)
    doc['links'][0]['record_sha256']=_digest(col)
    with pytest.raises(OwnershipError):preview(doc,project)
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):preview(doc,project)


def test_preview_file_does_not_trust_changed_document(tmp_path):
    project,doc=case(tmp_path)
    fp=tmp_path/'beam_column_panel.json';digest=write(fp,doc)
    assert preview_file(project,str(fp),digest)['rows']==[]
    fp.write_bytes(fp.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):preview_file(project,str(fp),digest)


def test_sqlite_save_reopen_and_cas_stale_snapshot(tmp_path):
    app=StructuralProApp(tmp_path/'db');app.create_project('مستند مصنوعی اتصال تیر و ستون','P')
    project,doc=case(tmp_path)
    snapshot=app.open_project('P')
    snapshot.update({k:deepcopy(project[k]) for k in ('reviewed_structural_members','beam_detail_register')})
    app.store.save('P',snapshot)
    loaded=app.open_project('P');original=deepcopy(loaded)
    record=preview(doc,loaded)
    assert record['ready_for_boq'] is False and record['rows']==[]
    assert app.open_project('P')==original
    assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    app.store.close()
    other=StructuralProApp(tmp_path/'db')
    try:
        new=other.open_project('P')
        assert new==original
        assert preview(doc,new)['observations'][0]['volume_m3']=='0.16'
        new['beam_detail_register']['b']['revision']=3
        other.store.save('P',new)
        with pytest.raises(OwnershipError):preview(doc,other.open_project('P'))
    finally:other.store.close()
