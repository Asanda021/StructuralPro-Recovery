"""Limited contact-face observations on versioned synthetic member records.

These do not prove actual footing design, reinforcement anchorage or BOQ rights.
"""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.column_joint_beam_panel import POINTER_KEY, PRISM_POLICY
from core.takeoff.column_joint_footing_tie import POLICY, preview, preview_file


def write(path, content):
    raw = json.dumps(content, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':')).encode('utf-8')
    path.write_bytes(raw)
    return sha256(raw).hexdigest()


def fixture(tmp_path, *, kind='isolated_footing'):
    col_box = {'x_min_m':'-0.4','y_min_m':'-0.4','z_min_m':'0',
               'x_max_m':'0.4','y_max_m':'0.4','z_max_m':'3'}
    if kind == 'tie_beam':
        other_box = {'x_min_m':'0.4','y_min_m':'-0.2','z_min_m':'1',
                     'x_max_m':'2','y_max_m':'0.2','z_max_m':'2'}
    else:
        other_box = {'x_min_m':'-1','y_min_m':'-1','z_min_m':'-0.5',
                     'x_max_m':'1','y_max_m':'1','z_max_m':'0'}
    c = {'status':'draft','revision':2,'data':{'kind':'column','floor_id':'L1',
         'member_id':'C1','physical_id':'COLUMN-PH',
         'source':{'approved_by':'Source-C'},
         'geometry':{'physical_id':'COLUMN-PH','source_ref':'GEOM-C','source_sha256':'a'*64},
         'rebars':{'starters':{'segments':[
             {'id':'C-S1','physical_id':'C-STARTER','centerline_length_m':'0.7',
              'source_ref':'SCHEDULE-C'}]}}}}
    f = {'status':'draft','revision':3,'data':{'kind':kind,'floor_id':'FND',
         'member_id':'F1','physical_id':'FOUNDATION-PH',
         'source':{'approved_by':'Source-F'},
         'geometry':{'physical_id':'FOUNDATION-PH','source_ref':'GEOM-F','source_sha256':'b'*64},
         'rebars':{'starters':{'status':'not_applicable'}}}}
    project = {'id':'P','reviewed_structural_members':{'C':c,'F':f},
               'beam_detail_register':{},'boq':[{'historical':'protected'}],
               'takeoffs':[{'historical':'protected'}]}
    links=[]
    for role, record, box in (('column',c,col_box),('counterpart',f,other_box)):
        d=record['data']; g=d['geometry']
        source = dict(policy=PRISM_POLICY,project_id='P',role=role,kind=d['kind'],
                      floor_id=d['floor_id'],member_id=d['member_id'],
                      physical_id=d['physical_id'],coordinate_ref='COORD',
                      vertical_datum_ref='DATUM',geometry_source_ref=g['source_ref'],
                      geometry_source_sha256=g['source_sha256'],
                      prepared_by='PrismWriter-'+role,reviewer='PrismReviewer-'+role,**box)
        path=tmp_path/(role+'.json')
        g[POINTER_KEY]={'policy':PRISM_POLICY,'path':str(path.resolve()),
                        'sha256':write(path,source),'reference':'evidence of member',
                        'coordinate_ref':'COORD','vertical_datum_ref':'DATUM',
                        'physical_id':d['physical_id']}
        links.append({'role':role,'kind':d['kind'],'floor_id':d['floor_id'],
                      'member_id':d['member_id'],'physical_id':d['physical_id'],
                      'record_revision':record['revision'],'record_sha256':_digest(record)})
    starter={'id':'R1','physical_bar_id':'C-STARTER','owner_role':'column',
             'group_key':'starters','record_piece_id':'C-S1','source_ref':'SCHEDULE-C',
             'detail_ref':'DETAILED-C1','approved_by':'IndependentBarDesigner',
             'axis':'z','start':{'x_m':'0','y_m':'0','z_m':'-0.3'},
             'end':{'x_m':'0','y_m':'0','z_m':'0.4'},'centerline_length_m':'0.7'}
    doc={'policy':POLICY,'project_id':'P','joint_id':'J-C1',
         'coordinate_ref':'COORD','vertical_datum_ref':'DATUM',
         'detail_ref':'connection drawing evidence','prepared_by':'Author',
         'reviewer':'IndependentReviewer','links':links,
         'contact_type':'lateral_face' if kind=='tie_beam' else 'support_face',
         'contact_axis':'x' if kind=='tie_beam' else 'z',
         'face_area_m2':'0.4' if kind=='tie_beam' else '0.64',
         'starter_status':'not_applicable' if kind=='tie_beam' else 'documented',
         'starter_reason':'بدون انتظار طبق دیتایل مستند شناژ' if kind=='tie_beam' else '',
         'starter_bars':[] if kind=='tie_beam' else [starter],
         'ownership_status':'unresolved'}
    return project,doc


def update_member_link(p,d,role):
    link=next(x for x in d['links'] if x['role']==role)
    key='C' if role=='column' else 'F'
    link['record_sha256']=_digest(p['reviewed_structural_members'][key])


def update_source(p,d,role,path):
    key='C' if role=='column' else 'F'
    record=p['reviewed_structural_members'][key]
    record['data']['geometry'][POINTER_KEY]['sha256']=write(path, json.loads(path.read_text()))
    update_member_link(p,d,role)


def test_column_resting_on_footing_has_zero_shared_volume_and_positive_face(tmp_path):
    project,doc=fixture(tmp_path);before=deepcopy((project,doc))
    result=preview(doc,project)
    assert result['contact_type']=='support_face'
    assert result['face_area_m2']=='0.64'
    assert result['shared_concrete_volume_m3']=='0'
    assert result['observations']==[{'physical_bar_id':'C-STARTER',
                                    'owner_role':'column','crossing_length_m':'0.7',
                                    'unit':'m'}]
    assert result['rows']==[] and not result['ready_for_boq'] and not result['commit_allowed']
    assert (project,doc)==before


@pytest.mark.parametrize('kind', ['isolated_footing','strip_footing','mat_footing'])
def test_three_footing_families_allow_supported_contact_only(tmp_path,kind):
    project,doc=fixture(tmp_path,kind=kind)
    assert preview(doc,project)['counterpart_kind']==kind


def test_lateral_grade_beam_face_with_explicitly_no_starters(tmp_path):
    project,doc=fixture(tmp_path,kind='tie_beam')
    result=preview(doc,project)
    assert result['face_area_m2']=='0.4'
    assert result['contact_axis']=='x'
    assert result['observations']==[]
    assert result['ready_for_boq'] is False


def test_lateral_grade_beam_bar_crosses_x_face_when_documented(tmp_path):
    project,doc=fixture(tmp_path,kind='tie_beam')
    c=project['reviewed_structural_members']['C'];piece=c['data']['rebars']['starters']['segments'][0]
    piece['centerline_length_m']='0.8'
    update_member_link(project,doc,'column')
    doc['starter_status']='documented';doc['starter_reason']=''
    doc['starter_bars']=[{'id':'R2','physical_bar_id':'C-STARTER',
        'owner_role':'column','group_key':'starters','record_piece_id':'C-S1',
        'source_ref':'SCHEDULE-C','detail_ref':'GRADE-BEAM-DETAIL',
        'approved_by':'AnotherBarDesigner','axis':'x',
        'start':{'x_m':'0.9','y_m':'0','z_m':'1.5'},
        'end':{'x_m':'0.1','y_m':'0','z_m':'1.5'},'centerline_length_m':'0.8'}]
    assert preview(doc,project)['observations'][0]['crossing_length_m']=='0.8'


@pytest.mark.parametrize('mutation',[
    lambda p,d:d.update(project_id='OTHER'),
    lambda p,d:d.update(policy='old'),
    lambda p,d:d.update(contact_type='volume_overlap'),
    lambda p,d:d.update(contact_axis='x'),
    lambda p,d:d.update(face_area_m2='0.63'),
    lambda p,d:d.update(face_area_m2=0.64),
    lambda p,d:d.update(face_area_m2=True),
    lambda p,d:d.update(ownership_status='approved'),
    lambda p,d:d.update(reviewer='Author'),
    lambda p,d:d['links'].pop(),
    lambda p,d:d['links'].append(deepcopy(d['links'][0])),
    lambda p,d:d['links'][0].update(record_sha256='0'*64),
    lambda p,d:d['links'][0].update(record_revision=1),
    lambda p,d:d['links'][1].update(kind='beam'),
    lambda p,d:d['links'][1].update(physical_id='COLUMN-PH'),
    lambda p,d:d['links'][1].update(floor_id='other'),
    lambda p,d:d.update(starter_status='not_applicable',starter_reason='none',starter_bars=[]),
    lambda p,d:d['starter_bars'][0].update(physical_bar_id='OTHER'),
    lambda p,d:d['starter_bars'][0].update(owner_role='other'),
    lambda p,d:d['starter_bars'][0].update(group_key='ties'),
    lambda p,d:d['starter_bars'][0].update(source_ref='fake'),
    lambda p,d:d['starter_bars'][0].update(axis='x'),
    lambda p,d:d['starter_bars'][0].update(centerline_length_m='0.8'),
    lambda p,d:d['starter_bars'][0].update(centerline_length_m='NaN'),
    lambda p,d:d['starter_bars'][0].update(centerline_length_m=0.7),
    lambda p,d:d['starter_bars'][0]['start'].update(z_m='0'),
    lambda p,d:d['starter_bars'][0]['end'].update(z_m='-0.3'),
    lambda p,d:d['starter_bars'][0]['start'].update(x_m='0.1'),
    lambda p,d:d['starter_bars'][0]['end'].update(z_m='3.5'),
    lambda p,d:d['starter_bars'][0]['end'].update(z_m=False),
    lambda p,d:d['starter_bars'][0].update(approved_by='IndependentReviewer'),
    lambda p,d:d['starter_bars'].append(deepcopy(d['starter_bars'][0])),
    lambda p,d:p['reviewed_structural_members']['C']['data']['rebars']['starters']['segments'][0].update(source_ref='changed'),
    lambda p,d:p['reviewed_structural_members']['C'].update(revision=3),
    lambda p,d:p['reviewed_structural_members'].update(THIRD={'status':'draft','revision':1,
       'data':{'kind':'column','floor_id':'L2','member_id':'C3',
               'geometry':{'physical_id':'COLUMN-PH'},'rebars':{}}}),
    lambda p,d:p['reviewed_structural_members'].update(THIRD={'status':'draft','revision':1,
       'data':{'kind':'column','floor_id':'L2','member_id':'C3',
               'geometry':{'physical_id':'DIFFERENT'},'rebars':{'ties':{'segments':[
                   {'physical_id':'C-STARTER'}]}}}}),
])
def test_invalid_member_geometry_and_starter_evidence_is_rejected(tmp_path,mutation):
    project,doc=fixture(tmp_path)
    mutation(project,doc)
    with pytest.raises(OwnershipError):preview(doc,project)


@pytest.mark.parametrize('change',[
    {'z_max_m':'0.15'},
    {'z_max_m':'-0.01'},
    {'x_min_m':'-0.2'},
    {'x_max_m':'0.2'},
    {'z_min_m':'-0.01'},
])
def test_footing_partially_overlaps_or_cannot_support_whole_column(tmp_path,change):
    p,d=fixture(tmp_path)
    path=tmp_path/'counterpart.json'
    j=json.loads(path.read_text());j.update(change)
    p['reviewed_structural_members']['F']['data']['geometry'][POINTER_KEY]['sha256']=write(path,j)
    update_member_link(p,d,'counterpart')
    with pytest.raises(OwnershipError):preview(d,p)


def test_tampered_or_removed_prism_document_blocks(tmp_path):
    p,d=fixture(tmp_path)
    path=tmp_path/'counterpart.json'
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):preview(d,p)
    path.unlink()
    with pytest.raises(OwnershipError):preview(d,p)


def test_preview_file_requires_original_bytes(tmp_path):
    p,d=fixture(tmp_path)
    path=tmp_path/'joint.json';digest=write(path,d)
    assert preview_file(p,str(path),digest)['rows']==[]
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):preview_file(p,str(path),digest)


def test_real_sqlite_round_trip_does_not_change_financial_books(tmp_path):
    app=StructuralProApp(tmp_path/'db');app.create_project('اتصال آزمایشی ستون به پی','P')
    p,d=fixture(tmp_path);snap=app.open_project('P')
    snap.update({key:deepcopy(p[key]) for key in ('reviewed_structural_members','beam_detail_register')})
    app.store.save('P',snap)
    saved=app.open_project('P');before=deepcopy(saved)
    assert not preview(d,saved)['commit_allowed']
    assert app.open_project('P')==before
    assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    app.store.close()
    second=StructuralProApp(tmp_path/'db')
    try:
        recovered=second.open_project('P')
        assert recovered==before and preview(d,recovered)['rows']==[]
        recovered['reviewed_structural_members']['C']['revision']=3
        second.store.save('P',recovered)
        with pytest.raises(OwnershipError):preview(d,second.open_project('P'))
    finally:
        second.store.close()
