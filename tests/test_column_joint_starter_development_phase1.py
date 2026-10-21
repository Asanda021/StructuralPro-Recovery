"""Straight starter embedment and claimed design worksheet acceptance (synthetic)."""
from copy import deepcopy
from decimal import Decimal
import json

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.column_joint_starter_development import POLICY, CALC_POLICY, preview, preview_file
from test_column_joint_footing_tie_phase1 import fixture, write, update_member_link


def setup(tmp_path, kind='isolated_footing'):
    p,contact=fixture(tmp_path,kind=kind)
    if kind=='tie_beam':
        c=p['reviewed_structural_members']['C']
        c['data']['rebars']['starters']['segments'][0]['centerline_length_m']='0.8'
        update_member_link(p, contact,'column')
        contact['starter_status']='documented';contact['starter_reason']=''
        contact['starter_bars']=[{'id':'R2','physical_bar_id':'C-STARTER','owner_role':'column',
          'group_key':'starters','record_piece_id':'C-S1','source_ref':'SCHEDULE-C',
          'detail_ref':'DRAWN-TIE','approved_by':'BarDesigner','axis':'x',
          'start':{'x_m':'0.9','y_m':'0','z_m':'1.5'},
          'end':{'x_m':'0.1','y_m':'0','z_m':'1.5'},'centerline_length_m':'0.8'}]
    c=p['reviewed_structural_members']['C']
    c['data']['rebars']['starters']['segments'][0]['diameter_mm']='20'
    update_member_link(p,contact,'column')
    contact_path=tmp_path/'contact.json';contact_sha=write(contact_path,contact)
    provided_other='0.5' if kind=='tie_beam' else '0.3'
    provided_column='0.3' if kind=='tie_beam' else '0.4'
    clearance='0.19' if kind=='tie_beam' else '0.39'
    sheet={'policy':CALC_POLICY,'project_id':'P','joint_id':'J-C1',
         'physical_bar_id':'C-STARTER','diameter_mm':'20',
         'required_counterpart_m':'0.2','required_column_m':'0.2',
         'required_clear_cover_m':'0.04','design_code_ref':'Code-version-claimed-only',
         'calculation_ref':'Engineer-sheet-example','designer':'IndependentDesigner',
         'independent_reviewer':'IndependentChecker',
         'bend_status':'straight','bend_detail_ref':'','bend_radius_mm':'',
         'bend_angle_deg':''}
    sheet_path=tmp_path/'sheet.json';sheet_sha=write(sheet_path,sheet)
    d={'policy':POLICY,'project_id':'P','joint_id':'J-C1',
       'contact_document':{'path':str(contact_path.resolve()),'sha256':contact_sha,
                           'reference':'Source bound contact'},
       'prepared_by':'DevelopmentAuthor','reviewer':'DevelopmentReviewer',
       'starter_checks':[{'physical_bar_id':'C-STARTER','diameter_mm':'20',
                          'provided_counterpart_m':provided_other,
                          'provided_column_m':provided_column,
                          'transverse_clearance_m':clearance,
                          'worksheet_document':{'path':str(sheet_path.resolve()),
                                                'sha256':sheet_sha,
                                                'reference':'Independent source worksheet'}}]}
    return p,d,sheet


@pytest.mark.parametrize('kind',['isolated_footing','strip_footing','mat_footing','tie_beam'])
def test_source_bound_straight_starter_never_financial(tmp_path,kind):
    p,d,s=setup(tmp_path,kind);before=deepcopy((p,d))
    out=preview(d,p)
    assert out['status']=='STARTER_DEVELOPMENT_EVIDENCE_PREVIEW_ONLY'
    assert out['ready_for_boq'] is False and out['commit_allowed'] is False and out['rows']==[]
    assert out['observations'][0]['design_code_conformance_verified'] is False
    assert Decimal(out['observations'][0]['provided_column_m'])>0
    assert (p,d)==before


@pytest.mark.parametrize('fault',[
    'wrong_policy','wrong_project','wrong_joint','same_reviewer','bad_contact_hash',
    'bad_contact_path','revised_column','damaged_prism','no_starters',
    'wrong_piece_id','wrong_piece_source','two_checks','missing_checks',
    'unknown_bar','wrong_diameter','missing_record_diameter',
    'float_diameter','float_embed','boolean_embed','nan_embed',
    'wrong_other_embed','wrong_column_embed','negative_embed',
    'wrong_clearance','insufficient_cover','required_other_exceeds','required_column_exceeds',
    'bad_sheet_hash','changed_sheet','wrong_sheet_joint','wrong_sheet_bar',
    'wrong_sheet_diameter','missing_standard','missing_calculation',
    'same_designer','same_checker','checker_same_reviewer','bent_claim',
    'bend_radius_claim','bend_detail_on_straight','missing_sheet','duplicate_key',
    'extra_field','bar_duplicated_elsewhere','second_member_approver',
])
def test_bad_design_claim_or_source_fails_closed(tmp_path,fault):
    p,d,s=setup(tmp_path)
    chk=d['starter_checks'][0]
    sheet_path=tmp_path/'sheet.json'
    update_sheet=False
    if fault=='wrong_policy':d['policy']='other'
    elif fault=='wrong_project':d['project_id']='OTHER'
    elif fault=='wrong_joint':d['joint_id']='OTHER'
    elif fault=='same_reviewer':d['reviewer']='DevelopmentAuthor'
    elif fault=='bad_contact_hash':d['contact_document']['sha256']='0'*64
    elif fault=='bad_contact_path':d['contact_document']['path']='invalid.json'
    elif fault=='revised_column':p['reviewed_structural_members']['C']['revision']=3
    elif fault=='damaged_prism':(tmp_path/'column.json').write_text('{}')
    elif fault=='no_starters':contact=json.loads((tmp_path/'contact.json').read_text());contact['starter_status']='not_applicable';contact['starter_bars']=[];contact['starter_reason']='none';d['contact_document']['sha256']=write(tmp_path/'contact.json',contact)
    elif fault=='wrong_piece_id':p['reviewed_structural_members']['C']['data']['rebars']['starters']['segments'][0]['id']='CHANGED'
    elif fault=='wrong_piece_source':p['reviewed_structural_members']['C']['data']['rebars']['starters']['segments'][0]['source_ref']='other'
    elif fault=='two_checks':d['starter_checks'].append(deepcopy(chk))
    elif fault=='missing_checks':d['starter_checks']=[]
    elif fault=='unknown_bar':chk['physical_bar_id']='OTHER'
    elif fault=='wrong_diameter':chk['diameter_mm']='18'
    elif fault=='missing_record_diameter':p['reviewed_structural_members']['C']['data']['rebars']['starters']['segments'][0].pop('diameter_mm')
    elif fault=='float_diameter':chk['diameter_mm']=20.0
    elif fault=='float_embed':chk['provided_counterpart_m']=0.3
    elif fault=='boolean_embed':chk['provided_column_m']=True
    elif fault=='nan_embed':chk['provided_column_m']='NaN'
    elif fault=='wrong_other_embed':chk['provided_counterpart_m']='0.31'
    elif fault=='wrong_column_embed':chk['provided_column_m']='0.41'
    elif fault=='negative_embed':chk['provided_column_m']='-0.4'
    elif fault=='wrong_clearance':chk['transverse_clearance_m']='0.38'
    elif fault=='insufficient_cover':s['required_clear_cover_m']='0.4';update_sheet=True
    elif fault=='required_other_exceeds':s['required_counterpart_m']='0.35';update_sheet=True
    elif fault=='required_column_exceeds':s['required_column_m']='0.45';update_sheet=True
    elif fault=='bad_sheet_hash':chk['worksheet_document']['sha256']='f'*64
    elif fault=='changed_sheet':sheet_path.write_text('{}')
    elif fault=='wrong_sheet_joint':s['joint_id']='OTHER';update_sheet=True
    elif fault=='wrong_sheet_bar':s['physical_bar_id']='OTHER';update_sheet=True
    elif fault=='wrong_sheet_diameter':s['diameter_mm']='18';update_sheet=True
    elif fault=='missing_standard':s['design_code_ref']='';update_sheet=True
    elif fault=='missing_calculation':s['calculation_ref']='';update_sheet=True
    elif fault=='same_designer':s['designer']='DevelopmentAuthor';update_sheet=True
    elif fault=='same_checker':s['independent_reviewer']='IndependentDesigner';update_sheet=True
    elif fault=='checker_same_reviewer':s['independent_reviewer']='DevelopmentReviewer';update_sheet=True
    elif fault=='bent_claim':s['bend_status']='documented';s['bend_detail_ref']='Hook';s['bend_radius_mm']='40';s['bend_angle_deg']='90';update_sheet=True
    elif fault=='bend_radius_claim':s['bend_radius_mm']='40';update_sheet=True
    elif fault=='bend_detail_on_straight':s['bend_detail_ref']='Hook';update_sheet=True
    elif fault=='missing_sheet':sheet_path.unlink()
    elif fault=='duplicate_key':sheet_path.write_text('{"a":1,"a":1}')
    elif fault=='extra_field':s['pretend_design_approval']=True;update_sheet=True
    elif fault=='bar_duplicated_elsewhere':p['reviewed_structural_members']['THIRD']={'status':'draft','revision':1,'data':{'rebars':{'ties':{'segments':[{'physical_id':'C-STARTER'}]}}}}
    elif fault=='second_member_approver':p['reviewed_structural_members']['C']['data']['source']['approved_by']='IndependentReviewer'
    if update_sheet:
        chk['worksheet_document']['sha256']=write(sheet_path,s)
    with pytest.raises(OwnershipError):preview(d,p)


def test_sqlite_roundtrip_sha_fresh_read_and_no_ledger_mutation(tmp_path):
    app=StructuralProApp(tmp_path/'db');app.create_project('آزمون مستند مهاری', 'P')
    project,doc,_=setup(tmp_path)
    snap=app.open_project('P')
    snap.update({k:deepcopy(project[k]) for k in ('reviewed_structural_members','beam_detail_register')})
    app.store.save('P',snap)
    saved=app.open_project('P');before=deepcopy(saved)
    path=tmp_path/'development.json';sha=write(path,doc)
    out=preview_file(saved,str(path),sha)
    assert out['ready_for_boq'] is False and out['rows']==[]
    assert app.open_project('P')==before
    assert app.store.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    app.store.close()
    second=StructuralProApp(tmp_path/'db')
    try:
        again=second.open_project('P');assert again==before
        assert preview(doc,again)['status']=='STARTER_DEVELOPMENT_EVIDENCE_PREVIEW_ONLY'
        again['reviewed_structural_members']['C']['revision']=3
        second.store.save('P',again)
        with pytest.raises(OwnershipError):preview(doc,second.open_project('P'))
    finally:second.store.close()
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(OwnershipError):preview_file(before,str(path),sha)
