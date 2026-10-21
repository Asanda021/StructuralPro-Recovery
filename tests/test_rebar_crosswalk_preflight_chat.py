"""Explicitly synthetic, document-matching contract tests; no financial approval."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import pytest

from core.takeoff.rebar_crosswalk_preflight_chat import (
    POLICY,EVIDENCE,CrosswalkError,template,audit)
from core.takeoff.shared_rebar_ownership_chat import reconcile
from core.takeoff.shear_wall_bridge_chat import compile_preview as shear
from core.takeoff.stair_bridge_chat import compile_preview as stair
from core.takeoff.bored_pile_bridge_chat import compile_preview as pile
from scripts.verify_structural_four_package_preflight_chat import read


def build():
    project={'id':'P','takeoffs':[],'boq':[],'reviewed_aec_systems':{},
             'reviewed_structural_members':{},'beam_detail_register':{}}
    wall=read('shear_wall_chat_reference.json')
    steps=read('stair_chat_example.json'); steps['metadata']['project_id']='P'
    piles=read('bored_pile_documented_synthetic.json')
    previews={'shear_wall':shear(wall,project,reviewer='Independent R',review_reference='Synthetic ref'),
              'stair':stair(steps,project,source_id='STAI-R1',reviewer='Independent R',ownership_reference='Synthetic ref'),
              'bored_pile':pile(piles,project,independent_reviewer='Independent R',ownership_reference='Synthetic ref')}
    owner_data=read('rebar_shared_synthetic.json')
    ownership=reconcile(owner_data,project)
    return previews,owner_data,ownership,project


def explicit_one():
    previews,data,owner,project=build()
    # Synthetic fixture only: adapt a standalone ownership reference to one explicit
    # adapter row; this is NOT a reconciliation of any actual project or original 9.
    record=next(x for x in previews['shear_wall']['takeoff_candidates'] if x['quantities'][0]['unit']=='kg')
    payer=record['provenance']['source_id']; other='SYNTHETIC-SECOND-MEMBER'
    physical='SYNTHETIC-BAR-01'
    data=deepcopy(data)
    for i,claim in enumerate(data['claims']):
        claim.update(source_id=(payer if i==0 else other),payer_source_id=payer,
                     role=('payer' if i==0 else 'reference'),physical_bar_id=physical,
                     physical_piece_id='SYNTHETIC-PIECE-01',
                     participant_source_ids=sorted([payer,other]),
                     count='1',unit_mass_kg_m='1',
                     cut_parts=[{'piece_part_id':'S','kind':'straight',
                                 'length_m':record['quantities'][0]['amount'],
                                 'source_ref':'SYNTHETIC-EXPLICIT-CUT'}])
    data['connections'][0]['bar_ids']=[physical]
    content=b'synthetic ownership source bytes not a real engineering document'
    data['source_sha256']=hashlib.sha256(content).hexdigest()
    owner=reconcile(data,project,source_document=content)
    req=next(x for x in template(previews,'P')['requests'] if x['candidate_source_id']==record['source_id'])
    doc={'schema':EVIDENCE,'project_id':'P',
         'owner_source_fingerprint_sha256':owner['source_fingerprint_sha256'],
         'candidate_source_id':record['source_id'],'candidate_sha256':req['candidate_sha256'],
         'adapter_source_id':payer,'component_physical_id':req['component_physical_id'],
         'physical_bar_id':physical,'physical_piece_id':'SYNTHETIC-PIECE-01',
         'paying_source_id':payer,'mass_kg':record['quantities'][0]['amount'],
         'detail_ref':'SYNTHETIC-DETAIL-ONLY','prepared_by':'Fixture creator',
         'independent_reviewer':'Fixture reviewer'}
    blob=json.dumps(doc,ensure_ascii=False,sort_keys=True).encode('utf-8')
    sha=hashlib.sha256(blob).hexdigest()
    cross={'policy':POLICY,'project_id':'P',
           'owner_source_fingerprint_sha256':owner['source_fingerprint_sha256'],
           'mappings':[{'candidate_source_id':record['source_id'],'evidence_sha256':sha}]}
    return previews,data,content,owner,project,cross,{sha:blob},doc


def test_exact_nine_rows_template_readonly_and_deterministic():
    previews,data,own,proj=build();prev=deepcopy((previews,data,own,proj))
    t=template(previews,'P')
    assert t['unverified_candidate_count']==9 and len(t['requests'])==9
    assert all(x['physical_bar_id'] is None and x['status']=='NEEDS_DOCUMENTED_IDENTITY' for x in t['requests'])
    cw={'policy':POLICY,'project_id':'P','owner_source_fingerprint_sha256':own['source_fingerprint_sha256'],'mappings':[]}
    result=audit(previews,own,cw,{},project_id='P')
    assert result['commit_allowed'] is False and result['undocumented_rows']==9
    assert result['document_consistent_rows']==0
    assert (previews,data,own,proj)==prev
    assert t==template(previews,'P')


def test_one_explicitly_documented_synthetic_link_never_approves():
    previews,owner_input,source_blob,own,proj,cw,files,doc=explicit_one()
    before=deepcopy((previews,owner_input,own,cw,files))
    r=audit(previews,own,cw,files,project_id='P',ownership_source_data=owner_input,ownership_source_document=source_blob)
    assert r['document_consistent_rows']==1 and r['undocumented_rows']==8
    assert r['status']=='BLOCKED_FOR_COMMIT' and r['commit_allowed'] is False
    assert r['document_consistent_links'][0]['status']=='DOCUMENT_CONSISTENT_NOT_ENGINEER_APPROVED'
    assert (previews,owner_input,own,cw,files)==before


@pytest.mark.parametrize('which',[
  'missing_owner_data','changed_owner_payload','wrong_project','bad_policy',
  'bad_ownership_fp','different_cross_fp','unknown_row','duplicate_row','bogus_file',
  'bad_sha','modified_blob','bad_encoding','bad_document_schema','document_missing_field',
  'wrong_candidate_sha','wrong_candidate_id','wrong_source','wrong_component',
  'wrong_bar','wrong_piece','wrong_payer','wrong_mass','decimal_float','nonfinite',
  'missing_detail','same_reviewer','wrong_document_owner_fp','row_changed_after_signature',
  'changed_source_document','replayed_document_on_different_row',
  'duplicate_bar_payment','owner_wrong_payment','unverified_owner_mass'])
def test_fail_closed_negative_crosswalk(which):
    previews,data,source_blob,own,proj,cw,files,doc=explicit_one()
    if which=='missing_owner_data': data=None
    elif which=='changed_owner_payload':own['physical_bar_paid_once'][0]['mass_kg']='13'
    elif which=='wrong_project':cw['project_id']='WRONG'
    elif which=='bad_policy':cw['policy']='NO'
    elif which=='bad_ownership_fp':own['source_fingerprint_sha256']='0'*64
    elif which=='different_cross_fp':cw['owner_source_fingerprint_sha256']='0'*64
    elif which=='unknown_row':cw['mappings'][0]['candidate_source_id']='UNKNOWN'
    elif which=='duplicate_row':cw['mappings'].append(deepcopy(cw['mappings'][0]))
    elif which=='bogus_file':files.clear()
    elif which=='bad_sha':cw['mappings'][0]['evidence_sha256']='x'*64
    elif which=='modified_blob':files[next(iter(files))]=b'not matching digest'
    elif which=='bad_encoding':
        blob=b'\xff';h=hashlib.sha256(blob).hexdigest();files.clear();files[h]=blob;cw['mappings'][0]['evidence_sha256']=h
    elif which in {'bad_document_schema','document_missing_field','wrong_candidate_sha','wrong_candidate_id',
                   'wrong_source','wrong_component','wrong_bar','wrong_piece','wrong_payer',
                   'wrong_mass','decimal_float','nonfinite','missing_detail','same_reviewer',
                   'wrong_document_owner_fp'}:
        k={'bad_document_schema':'schema','document_missing_field':'detail_ref',
           'wrong_candidate_sha':'candidate_sha256','wrong_candidate_id':'candidate_source_id',
           'wrong_source':'adapter_source_id','wrong_component':'component_physical_id',
           'wrong_bar':'physical_bar_id','wrong_piece':'physical_piece_id','wrong_payer':'paying_source_id',
           'wrong_mass':'mass_kg','decimal_float':'mass_kg','nonfinite':'mass_kg',
           'missing_detail':'detail_ref','same_reviewer':'independent_reviewer',
           'wrong_document_owner_fp':'owner_source_fingerprint_sha256'}[which]
        if which=='document_missing_field':doc.pop(k)
        elif which=='decimal_float':doc[k]=.1
        elif which=='nonfinite':doc[k]='NaN'
        elif which=='same_reviewer':doc[k]=doc['prepared_by']
        elif which=='missing_detail':doc[k]=''
        else:doc[k]='WRONG'
        blob=json.dumps(doc,ensure_ascii=False,sort_keys=True).encode()
        sha=hashlib.sha256(blob).hexdigest();files={sha:blob};cw['mappings'][0]['evidence_sha256']=sha
    elif which=='row_changed_after_signature':
        row=next(x for x in previews['shear_wall']['takeoff_candidates'] if x['source_id']==doc['candidate_source_id'])
        row['quantities'][0]['amount']='1000'
    elif which=='changed_source_document':source_blob=b'other document'
    elif which=='replayed_document_on_different_row':
        other=next(x for x in previews['stair']['takeoff_candidates'] if x['quantities'][0]['unit']=='kg')
        cw['mappings'][0]['candidate_source_id']=other['source_id']
    elif which=='duplicate_bar_payment':
        # A second candidate tries to claim the *same* bar already used by the first.
        other=next(x for x in previews['shear_wall']['takeoff_candidates'] if x['quantities'][0]['unit']=='kg' and x['source_id']!=doc['candidate_source_id'])
        newdoc=deepcopy(doc);newdoc['candidate_source_id']=other['source_id']
        t=template(previews,'P');req=next(x for x in t['requests'] if x['candidate_source_id']==other['source_id'])
        newdoc['candidate_sha256']=req['candidate_sha256'];newdoc['component_physical_id']=req['component_physical_id']
        # If this link were fully matched it would still violate unique payment.
        blob=json.dumps(newdoc,ensure_ascii=False,sort_keys=True).encode()
        sha=hashlib.sha256(blob).hexdigest();files[sha]=blob
        cw['mappings'].append({'candidate_source_id':other['source_id'],'evidence_sha256':sha})
    elif which=='owner_wrong_payment':
        for claim in data['claims']:
            claim['payer_source_id']='SOMEONE-ELSE'
    elif which=='unverified_owner_mass':
        for claim in data['claims']:
            claim['cut_parts'][0]['length_m']='1'
    with pytest.raises((CrosswalkError,ValueError)):
        audit(previews,own,cw,files,project_id='P',ownership_source_data=data,ownership_source_document=source_blob)


def test_reject_float_without_forged_schema():
    previews, *_ = build()
    row=next(x for x in previews['shear_wall']['takeoff_candidates'] if x['quantities'][0]['unit']=='kg')
    row['quantities'][0]['amount']=float(1.25)
    with pytest.raises(CrosswalkError):template(previews,'P')


def test_reject_mutated_input_even_without_mapping():
    previews,data,owner,project=build()
    row=next(x for x in previews['stair']['takeoff_candidates'] if x['quantities'][0]['unit']=='kg')
    row['params']['physical_component_id']=None
    with pytest.raises(CrosswalkError):template(previews,'P')
