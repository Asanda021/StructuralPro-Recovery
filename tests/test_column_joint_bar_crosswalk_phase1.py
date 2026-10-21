"""Source-bound individual bar routes; synthetic examples, no design approval."""
from copy import deepcopy
from decimal import Decimal
import json

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.column_joint_bar_crosswalk import POLICY, preview, preview_file
from test_column_joint_beam_panel_phase1 import case, write


def prepared(tmp_path):
    project,geometry=case(tmp_path)
    col=project['reviewed_structural_members']['c']
    beam=project['beam_detail_register']['b']
    col['data']['rebars']['longitudinal']={'segments':[
        {'id':'C-BAR','physical_id':'BAR-C-PH','centerline_length_m':'0.6','source_ref':'SRC-C'}]}
    beam['data']['bars']['longitudinal']={'segments':[
        {'id':'B-BAR','physical_id':'BAR-B-PH','centerline_length_m':'0.8','source_ref':'SRC-B'}]}
    geometry['links'][0]['record_sha256']=_digest(col)
    geometry['links'][1]['record_sha256']=_digest(beam)
    path=tmp_path/'joint_geometry.json';digest=write(path,geometry)
    def point(x,y,z):return {'x_m':x,'y_m':y,'z_m':z}
    routes=[
        {'id':'R-C','physical_bar_id':'BAR-C-PH','owner_role':'column',
         'group_key':'longitudinal','record_piece_id':'C-BAR','source_ref':'SRC-C',
         'detail_ref':'محور مستند قائم','approved_by':'Independent-Bar-C',
         'centerline_length_m':'0.6','length_in_panel_m':'0.50',
         'points':[point('0.2','0','1.2'),point('0.2','0','1.8')]},
        {'id':'R-B','physical_bar_id':'BAR-B-PH','owner_role':'counterpart',
         'group_key':'longitudinal','record_piece_id':'B-BAR','source_ref':'SRC-B',
         'detail_ref':'محور مستند تیر','approved_by':'Independent-Bar-B',
         'centerline_length_m':'0.8','length_in_panel_m':'0.4',
         'points':[point('0','0','1.5'),point('0.8','0','1.5')]},
    ]
    doc={'policy':POLICY,'project_id':'P','joint_id':'J1',
         'geometry_document':{'path':str(path.resolve()),'sha256':digest,
                              'reference':'Geometry evidence, not signed drawing'},
         'prepared_by':'RouteAuthor','reviewer':'IndependentReviewer','bar_routes':routes}
    return project,doc,geometry


def test_two_source_bound_bars_never_enter_boq(tmp_path):
    project,doc,_=prepared(tmp_path)
    before=deepcopy((project,doc))
    result=preview(doc,project)
    assert result['status']=='BAR_ROUTE_PREVIEW_ONLY'
    assert result['ownership_scope']=='explicit_pieces_only'
    assert result['ready_for_boq'] is False and result['commit_allowed'] is False and result['rows']==[]
    assert [(x['owner_role'],Decimal(x['centerline_length_m']),Decimal(x['length_in_panel_m']))
            for x in result['observations']]==[
                ('column',Decimal('0.6'),Decimal('0.5')),
                ('counterpart',Decimal('0.8'),Decimal('0.4'))]
    assert (project,doc)==before


def test_valid_orthogonal_bent_polyline_and_nonrepeated_segments(tmp_path):
    project,doc,_=prepared(tmp_path)
    record=project['reviewed_structural_members']['c']['data']['rebars']['longitudinal']['segments'][0]
    record['centerline_length_m']='0.7'
    a=doc['bar_routes'][0]
    a['points'].insert(1,{'x_m':'0.3','y_m':'0','z_m':'1.2'})
    a['points'][2]['x_m']='0.3'
    a['centerline_length_m']='0.7'
    a['length_in_panel_m']='0.5'
    geometry=deepcopy(json.loads((tmp_path/'joint_geometry.json').read_text()))
    geometry['links'][0]['record_sha256']=_digest(project['reviewed_structural_members']['c'])
    doc['geometry_document']['sha256']=write(tmp_path/'joint_geometry.json',geometry)
    result=preview(doc,project)
    assert Decimal(result['observations'][0]['centerline_length_m'])==Decimal('0.7')


@pytest.mark.parametrize('fault',[
    'bad_policy','bad_project','bad_joint','bad_reviewer','bad_geom_hash','bad_geom_file',
    'stale_geom_snapshot','missing_geom_pointer','wrong_owner_role','wrong_group','wrong_piece_id',
    'wrong_piece_physical','duplicate_route','duplicate_physical','wrong_segment_source',
    'bad_claim_total','bad_claim_panel','float_point','bool_point','nan_point','inf_point',
    'oblique_segment','zero_segment','outside_column','outside_beam','outside_panel',
    'wrong_piece_length','missing_piece','same_bar_in_other_member','same_bar_in_third_member',
    'invalid_member_revision','empty_routes','too_many_routes','missing_detail_ref',
    'nonindependent_approver','reverse_overlap','negative_claim','float_claim',
    'missing_point','unknown_property','missing_member',
])
def test_invalid_evidence_rejected_without_amounts(tmp_path,fault):
    project,doc,geometry=prepared(tmp_path)
    a=doc['bar_routes'][0]
    if fault=='bad_policy':doc['policy']='bad'
    elif fault=='bad_project':doc['project_id']='OTHER'
    elif fault=='bad_joint':doc['joint_id']='OTHER'
    elif fault=='bad_reviewer':doc['reviewer']='RouteAuthor'
    elif fault=='bad_geom_hash':doc['geometry_document']['sha256']='0'*64
    elif fault=='bad_geom_file':(tmp_path/'joint_geometry.json').write_text('{}')
    elif fault=='stale_geom_snapshot':project['reviewed_structural_members']['c']['revision']=2
    elif fault=='missing_geom_pointer':project['reviewed_structural_members']['c']['data']['geometry'].pop('column_joint_prism_v1')
    elif fault=='wrong_owner_role':a['owner_role']='not_member'
    elif fault=='wrong_group':a['group_key']='stirrups'
    elif fault=='wrong_piece_id':a['record_piece_id']='OTHER'
    elif fault=='wrong_piece_physical':a['physical_bar_id']='ANOTHER'
    elif fault=='duplicate_route':doc['bar_routes'].append(deepcopy(a))
    elif fault=='duplicate_physical':doc['bar_routes'][1]['physical_bar_id']=a['physical_bar_id']
    elif fault=='wrong_segment_source':a['source_ref']='different source'
    elif fault=='bad_claim_total':a['centerline_length_m']='0.61'
    elif fault=='bad_claim_panel':a['length_in_panel_m']='0.51'
    elif fault=='float_point':a['points'][0]['x_m']=0.2
    elif fault=='bool_point':a['points'][0]['x_m']=True
    elif fault=='nan_point':a['points'][0]['x_m']='NaN'
    elif fault=='inf_point':a['points'][0]['x_m']='Infinity'
    elif fault=='oblique_segment':a['points'][1]['y_m']='0.01'
    elif fault=='zero_segment':a['points'][1]=deepcopy(a['points'][0])
    elif fault=='outside_column':a['points'][1]['z_m']='4'
    elif fault=='outside_beam':doc['bar_routes'][1]['points'][1]['x_m']='3'
    elif fault=='outside_panel':a['points'][0]['x_m']='-0.2';a['points'][1]['x_m']='-0.2'
    elif fault=='wrong_piece_length':project['reviewed_structural_members']['c']['data']['rebars']['longitudinal']['segments'][0]['centerline_length_m']='0.7'
    elif fault=='missing_piece':project['reviewed_structural_members']['c']['data']['rebars']['longitudinal']['segments']=[]
    elif fault=='same_bar_in_other_member':project['beam_detail_register']['b']['data']['bars']['longitudinal']['segments'][0]['physical_id']='BAR-C-PH'
    elif fault=='same_bar_in_third_member':project['reviewed_structural_members']['other']={'data':{'kind':'column','floor_id':'L2','member_id':'C3','rebars':{'other':{'segments':[{'physical_id':'BAR-C-PH'}]}},'geometry':{'physical_id':'THIRD'}},'status':'draft','revision':1}
    elif fault=='invalid_member_revision':doc['geometry_document']['reference']='';return _assert_reject(doc,project)
    elif fault=='empty_routes':doc['bar_routes']=[]
    elif fault=='too_many_routes':doc['bar_routes']*=130
    elif fault=='missing_detail_ref':a['detail_ref']=''
    elif fault=='nonindependent_approver':a['approved_by']='IndependentReviewer'
    elif fault=='reverse_overlap':a['points']=[{'x_m':'0.2','y_m':'0','z_m':'1.2'},
                                                  {'x_m':'0.2','y_m':'0','z_m':'1.8'},
                                                  {'x_m':'0.2','y_m':'0','z_m':'1.2'}]
    elif fault=='negative_claim':a['centerline_length_m']='-0.6'
    elif fault=='float_claim':a['length_in_panel_m']=0.5
    elif fault=='missing_point':a['points'][0].pop('x_m')
    elif fault=='unknown_property':a['undocumented']='value'
    elif fault=='missing_member':project['reviewed_structural_members'].pop('c')
    # Snapshot digest and geometry source remain stale on purpose for altered records.
    _assert_reject(doc,project)


def _assert_reject(doc,project):
    with pytest.raises(OwnershipError):preview(doc,project)


def test_sqlite_roundtrip_and_stale_cas_history(tmp_path):
    app=StructuralProApp(tmp_path/'db');app.create_project('آزمون مصنوعی میلگرد مشترک','P')
    project,doc,_=prepared(tmp_path)
    snap=app.open_project('P')
    snap.update({k:deepcopy(project[k]) for k in ('reviewed_structural_members','beam_detail_register')})
    app.store.save('P',snap)
    before=app.open_project('P')
    path=tmp_path/'rebar_routes.json';digest=write(path,doc)
    assert len(preview_file(before,str(path),digest)['observations'])==2
    assert app.open_project('P')==before
    assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    app.store.close()
    reopened=StructuralProApp(tmp_path/'db')
    try:
        after=reopened.open_project('P')
        assert after==before
        assert after['boq']==before['boq'] and after['takeoffs']==before['takeoffs']
        modified=deepcopy(after)
        modified['beam_detail_register']['b']['revision']=3
        reopened.store.save('P',modified)
        _assert_reject(doc,reopened.open_project('P'))
    finally:
        reopened.store.close()
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):preview_file(before,str(path),digest)
