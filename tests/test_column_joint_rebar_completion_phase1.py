"""Test the bounded closed-world *registered bar* schedule, not structural code approval."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.column_joint_rebar_completion import POLICY, preview, preview_file
from test_column_joint_bar_crosswalk_phase1 import prepared
from test_column_joint_beam_panel_phase1 import write


def setup(tmp_path):
    project, routes, geometry = prepared(tmp_path)
    col = project['reviewed_structural_members']['c']
    beam = project['beam_detail_register']['b']
    old = col['data']['rebars']['ties']['segments'][0]
    old.update(source_ref='SRC-OLD', diameter_mm='10')
    longitudinal = col['data']['rebars']['longitudinal']['segments'][0]
    longitudinal['diameter_mm']='16'
    stirrup = beam['data']['bars']['stirrups']['segments'][0]
    stirrup.update(physical_id='B-TIE-PH', source_ref='SRC-TIE', diameter_mm='8')
    beam['data']['bars']['longitudinal']['segments'][0]['diameter_mm']='20'
    geometry['links'][0]['record_sha256'] = _digest(col)
    geometry['links'][1]['record_sha256'] = _digest(beam)
    routes['geometry_document']['sha256'] = write(tmp_path/'joint_geometry.json',geometry)
    route_path = tmp_path/'routes.json'
    route_sha = write(route_path, routes)
    inventory=[]
    for role, groups in [('column',col['data']['rebars']),('counterpart',beam['data']['bars'])]:
        for group_key, group in groups.items():
            for piece in group['segments']:
                scope = ('critical_tie' if piece['physical_id']=='B-TIE-PH' else
                         'excluded_documented' if piece['physical_id']=='OLD-BAR' else 'route')
                inventory.append(dict(role=role,group_key=group_key,
                                      record_piece_id=piece['id'],physical_bar_id=piece['physical_id'],
                                      source_ref=piece['source_ref'],scope=scope,
                                      reason='طبق دیتایل مصنوعی خارج از اتصال است' if scope=='excluded_documented' else '',
                                      reviewed_by='RegisteredBarReviewer'))
    check=lambda phys,diam,provided: dict(physical_bar_id=phys,diameter_mm=diam,
                       required_development_m='0.2',provided_development_m=provided,
                       standard_ref='مبنای طراحی مصنوعی و نیازمند تأیید',
                       calculation_ref='محاسبه مستقل اعلام‌شده مصنوعی',
                       designer='IndependentDesigner',bend_status='straight',
                       bend_radius_mm='',bend_detail_ref='')
    doc=dict(policy=POLICY,project_id='P',joint_id='J1',
             routes_document=dict(path=str(route_path.resolve()),sha256=route_sha,
                                  reference='برنامه مسیر مصنوعی'),
             prepared_by='CompletionAuthor',reviewer='CompletionReviewer',
             inventory=inventory,
             development_checks=[check('BAR-C-PH','16','0.3'),check('BAR-B-PH','20','0.35')],
             critical_tie_stations=[dict(role='counterpart',physical_bar_id='B-TIE-PH',
                            x_m='0.2',y_m='0',z_m='1.5',station_ref='پلان خاموت مصنوعی',
                            approved_by='IndependentTieReviewer')])
    return project,doc,routes,geometry


def test_complete_registered_schedule_readonly(tmp_path):
    p,d,_,_=setup(tmp_path);original=deepcopy((p,d))
    r=preview(d,p)
    assert r['status']=='COLUMN_REBAR_COMPLETENESS_PREVIEW_ONLY'
    assert r['registered_piece_count']==4
    assert r['routed_piece_count']==2 and r['critical_tie_count']==1
    assert r['ready_for_boq'] is False and r['commit_allowed'] is False and r['rows']==[]
    assert (p,d)==original


def test_real_bent_polyline_with_documented_detail_stays_nonfinancial(tmp_path):
    p,d,routes,geometry=setup(tmp_path)
    col=p['reviewed_structural_members']['c']
    col['data']['rebars']['longitudinal']['segments'][0]['centerline_length_m']='0.7'
    route=routes['bar_routes'][0]
    route['points'].insert(1,{'x_m':'0.3','y_m':'0','z_m':'1.2'})
    route['points'][2]['x_m']='0.3'
    route['centerline_length_m']='0.7'
    geometry['links'][0]['record_sha256']=_digest(col)
    routes['geometry_document']['sha256']=write(tmp_path/'joint_geometry.json',geometry)
    d['routes_document']['sha256']=write(tmp_path/'routes.json',routes)
    dev=d['development_checks'][0]
    dev.update(bend_status='documented',bend_radius_mm='64',
               bend_detail_ref='دیتایل مستقل خم مصنوعی',provided_development_m='0.5')
    r=preview(d,p)
    assert r['status']=='COLUMN_REBAR_COMPLETENESS_PREVIEW_ONLY'
    assert r['rows']==[]


@pytest.mark.parametrize('fault',[
    'missing_inventory', 'extra_inventory','double_inventory','mislabel_route',
    'mislabel_tie','missing_route','no_tie','bad_source','bad_diameter',
    'absent_piece_physical','missing_group_segments','bad_group_status',
    'duplicate_physical','duplicate_in_third_member','wrong_owner',
    'no_exclusion_reason','unapproved_exclusion','missing_dev',
    'duplicate_dev','wrong_dev_physical','wrong_dev_diameter',
    'float_required','bool_provided','nan_dev','required_greater_than_provided',
    'provided_greater_than_bar','missing_code_ref','same_designer',
    'bad_bend_claim','bend_without_radius','unjustified_hook_detail',
    'missing_tie','duplicate_tie','tie_wrong_owner','tie_outside',
    'tie_float','tie_no_source','same_tie_reviewer',
    'bad_policy','bad_project','bad_joint','same_reviewer',
    'changed_route_document','changed_geometry_file','stale_revision',
    'route_other_joint','new_extra_field','unsigned_bar','zero_tie_diameter',
])
def test_invalid_and_incomplete_documents_fail_closed(tmp_path,fault):
    p,d,routes,g=setup(tmp_path)
    inv=d['inventory']; dev=d['development_checks'];ties=d['critical_tie_stations']
    if fault=='missing_inventory':inv.pop()
    elif fault=='extra_inventory':inv.append({**inv[0],'record_piece_id':'NOT-RECORD'})
    elif fault=='double_inventory':inv.append(deepcopy(inv[0]))
    elif fault=='mislabel_route':next(x for x in inv if x['physical_bar_id']=='BAR-C-PH')['scope']='excluded_documented'
    elif fault=='mislabel_tie':next(x for x in inv if x['physical_bar_id']=='B-TIE-PH')['scope']='route'
    elif fault=='missing_route':routes['bar_routes'].pop();d['routes_document']['sha256']=write(tmp_path/'routes.json',routes)
    elif fault=='no_tie':next(x for x in inv if x['physical_bar_id']=='B-TIE-PH')['scope']='excluded_documented'
    elif fault=='bad_source':inv[0]['source_ref']='WRONG'
    elif fault=='bad_diameter':dev[0]['diameter_mm']='20'
    elif fault=='absent_piece_physical':p['beam_detail_register']['b']['data']['bars']['stirrups']['segments'][0].pop('physical_id')
    elif fault=='missing_group_segments':p['beam_detail_register']['b']['data']['bars']['stirrups'].pop('segments')
    elif fault=='bad_group_status':p['reviewed_structural_members']['c']['data']['rebars']['ties']={'status':'unreviewed'}
    elif fault=='duplicate_physical':inv[2]['physical_bar_id']=inv[1]['physical_bar_id']
    elif fault=='duplicate_in_third_member':p['reviewed_structural_members']['third']={'data':{'rebars':{'ties':{'segments':[{'physical_id':'BAR-C-PH'}]}}}}
    elif fault=='wrong_owner':inv[0]['role']='counterpart'
    elif fault=='no_exclusion_reason':next(x for x in inv if x['scope']=='excluded_documented')['reason']=''
    elif fault=='unapproved_exclusion':next(x for x in inv if x['scope']=='excluded_documented')['reviewed_by']='CompletionAuthor'
    elif fault=='missing_dev':dev.pop()
    elif fault=='duplicate_dev':dev[1]['physical_bar_id']=dev[0]['physical_bar_id']
    elif fault=='wrong_dev_physical':dev[0]['physical_bar_id']='UNKNOWN'
    elif fault=='wrong_dev_diameter':dev[0]['diameter_mm']='30'
    elif fault=='float_required':dev[0]['required_development_m']=0.2
    elif fault=='bool_provided':dev[0]['provided_development_m']=True
    elif fault=='nan_dev':dev[0]['required_development_m']='NaN'
    elif fault=='required_greater_than_provided':dev[0]['required_development_m']='0.8'
    elif fault=='provided_greater_than_bar':dev[0]['provided_development_m']='0.9'
    elif fault=='missing_code_ref':dev[0]['standard_ref']=''
    elif fault=='same_designer':dev[0]['designer']='CompletionReviewer'
    elif fault=='bad_bend_claim':dev[0]['bend_status']='documented'
    elif fault=='bend_without_radius':dev[0]['bend_status']='documented';dev[0]['bend_detail_ref']='detail'
    elif fault=='unjustified_hook_detail':dev[0]['bend_detail_ref']='fake'
    elif fault=='missing_tie':ties.pop()
    elif fault=='duplicate_tie':ties.append(deepcopy(ties[0]))
    elif fault=='tie_wrong_owner':ties[0]['role']='column'
    elif fault=='tie_outside':ties[0]['z_m']='9'
    elif fault=='tie_float':ties[0]['x_m']=0.2
    elif fault=='tie_no_source':ties[0]['station_ref']=''
    elif fault=='same_tie_reviewer':ties[0]['approved_by']='CompletionReviewer'
    elif fault=='bad_policy':d['policy']='other'
    elif fault=='bad_project':d['project_id']='different'
    elif fault=='bad_joint':d['joint_id']='other'
    elif fault=='same_reviewer':d['reviewer']='CompletionAuthor'
    elif fault=='changed_route_document':(tmp_path/'routes.json').write_text('{}')
    elif fault=='changed_geometry_file':(tmp_path/'joint_geometry.json').write_text('{}')
    elif fault=='stale_revision':p['reviewed_structural_members']['c']['revision']=3
    elif fault=='route_other_joint':routes['joint_id']='J2';d['routes_document']['sha256']=write(tmp_path/'routes.json',routes)
    elif fault=='new_extra_field':d['automatic_code_approval']=True
    elif fault=='unsigned_bar':p['reviewed_structural_members']['c']['data']['rebars']['longitudinal']['segments'][0]['source_ref']=''
    elif fault=='zero_tie_diameter':p['beam_detail_register']['b']['data']['bars']['stirrups']['segments'][0]['diameter_mm']='0'
    with pytest.raises(OwnershipError):preview(d,p)


def test_real_sqlite_round_trip_and_immutable_boq(tmp_path):
    app=StructuralProApp(tmp_path/'db');app.create_project('سازه تست اتصال','P')
    p,d,_,_=setup(tmp_path)
    snapshot=app.open_project('P')
    snapshot.update({key:deepcopy(p[key]) for key in ('reviewed_structural_members','beam_detail_register')})
    app.store.save('P',snapshot)
    saved=app.open_project('P');previous=deepcopy(saved)
    path=tmp_path/'completion.json';digest=write(path,d)
    out=preview_file(saved,str(path),digest)
    assert not out['ready_for_boq'] and out['rows']==[]
    assert app.open_project('P')==previous
    assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    app.store.close()
    other=StructuralProApp(tmp_path/'db')
    try:
        new=other.open_project('P');assert new==previous
        assert not preview(d,new)['commit_allowed']
        new['reviewed_structural_members']['c']['revision']+=1
        other.store.save('P',new)
        with pytest.raises(OwnershipError):preview(d,other.open_project('P'))
    finally:other.store.close()
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):preview_file(previous,str(path),digest)
