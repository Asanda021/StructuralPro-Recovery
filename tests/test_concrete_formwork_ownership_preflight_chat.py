"""Real combined structural engine previews; synthetic documents never confer approval."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest
from core.takeoff.shear_wall_bridge_chat import compile_preview as shear
from core.takeoff.stair_bridge_chat import compile_preview as stair
from core.takeoff.bored_pile_bridge_chat import compile_preview as pile
from core.takeoff.concrete_formwork_ownership_preflight_chat import (
    POLICY,EVIDENCE_POLICY,OwnershipPreflightError,request_template,audit,
    _claims,amount,canonical,digest)

ROOT=Path(__file__).resolve().parents[1]/'examples'
GEOMETRY_BYTES=b'synthetic geometry, NOT engineering validation'
GEOMETRY_HASH=hashlib.sha256(GEOMETRY_BYTES).hexdigest()


def example(name):
    return json.loads((ROOT/name).read_text('utf-8'))


@pytest.fixture()
def sources():
    project={'id':'P','takeoffs':[],'boq':[],'reviewed_aec_systems':{},
             'reviewed_structural_members':{},'beam_detail_register':{}}
    s=example('shear_wall_chat_reference.json')
    t=example('stair_chat_example.json'); t['metadata']['project_id']='P'
    b=example('bored_pile_documented_synthetic.json')
    previews={'shear_wall':shear(s,project,reviewer='Independent Engineer',review_reference='Synthetic only'),
              'stair':stair(t,project,source_id='STAI-R1',reviewer='Independent Engineer',ownership_reference='Synthetic only'),
              'bored_pile':pile(b,project,independent_reviewer='Independent Engineer',ownership_reference='Synthetic only')}
    return previews,project


def doc_for(c, scope=None):
    return {'schema':EVIDENCE_POLICY,'project_id':c['project_id'],
            'candidate_source_id':c['candidate_source_id'],'candidate_sha256':c['candidate_sha256'],
            'engine':c['engine'],'physical_component_id':c['physical_component_id'],
            'operation':c['operation'],'unit':c['unit'],'quantity_exact':c['quantity_exact'],
            'scope_id':scope or 'scope:'+c['candidate_source_id'],
            'coordinate_ref':c['coordinate_ref_in_adapter'] or 'synthetic-unverified-coordinates',
            'geometry_document_sha256':GEOMETRY_HASH,
            'paying_source_id':c['candidate_source_id'], 'detail_ref':'SYNTHETIC-NOT-SIGNED',
            'prepared_by':'Editor A','independent_reviewer':'Reviewer B',
            'interface_review_status':'UNVERIFIED_NEEDS_CROSS_MEMBER_GEOMETRY'}


def evidence(doc):
    raw=canonical(doc).encode('utf-8')
    return hashlib.sha256(raw).hexdigest(),raw


def fixture_ledger(previews,project,count=2):
    candidates=list(_claims(previews,project).values())
    docs={GEOMETRY_HASH:GEOMETRY_BYTES};mappings=[]
    for c in candidates[:count]:
        h,b=evidence(doc_for(c));docs[h]=b
        mappings.append({'candidate_source_id':c['candidate_source_id'],'evidence_sha256':h})
    return {'policy':POLICY,'project_id':project['id'],'mappings':mappings},docs


def test_real_engines_and_no_mutation(sources):
    previews,project=sources
    snapshot=deepcopy((previews,project))
    tpl=request_template(previews,project)
    claim=_claims(previews,project)
    assert len(claim)>10
    assert tpl['commit_allowed'] is False and len(tpl['requests'])==len(claim)
    assert len({c['candidate_sha256'] for c in claim.values()})==len(claim)
    assert {c['engine'] for c in claim.values()}=={'shear_wall','stair','bored_pile'}
    assert all(c['unit']=='m3' if c['operation']=='concrete' else c['unit']=='m2' for c in claim.values())
    assert (previews,project)==snapshot


def test_empty_ledger_is_explicitly_blocked(sources):
    p,project=sources
    result=audit(p,project,{'policy':POLICY,'project_id':'P','mappings':[]},{})
    assert result['commit_allowed'] is False
    assert result['status']=='BLOCKED_FOR_COMMIT'
    assert result['undocumented_count']==result['candidate_count']
    assert not result['reviewed_evidence']


def test_valid_document_only_confirms_integrity(sources):
    p,project=sources
    ledger,docs=fixture_ledger(p,project)
    before=deepcopy((p,project,ledger,docs))
    r=audit(p,project,ledger,docs)
    assert r['document_consistent_count']==2
    assert r['undocumented_count']==r['candidate_count']-2
    assert all(x['status']=='DOCUMENT_CONSISTENT_NOT_ENGINEER_VERIFIED' for x in r['reviewed_evidence'])
    assert r['blockers'] and r['commit_allowed'] is False
    assert (p,project,ledger,docs)==before
    assert audit(p,project,ledger,docs)==r


def test_every_row_documented_still_no_approval(sources):
    p,project=sources
    ledger,docs=fixture_ledger(p,project,count=999)
    r=audit(p,project,ledger,docs)
    assert r['undocumented_count']==0
    assert r['document_consistent_count']==r['candidate_count']
    assert r['status']=='BLOCKED_FOR_COMMIT' and r['commit_allowed'] is False
    assert r['coordinate_unanchored_count']>0


@pytest.mark.parametrize("operation",("concrete","formwork"))
def test_one_duplicate_physical_scope_fails(sources,operation):
    p,project=sources
    c=list(_claims(p,project).values())
    matched=[x for x in c if x['operation']==operation][:2]
    docs={GEOMETRY_HASH:GEOMETRY_BYTES};maps=[]
    for x in matched:
        h,b=evidence(doc_for(x,'duplicate-paid-volume'))
        docs[h]=b;maps.append({'candidate_source_id':x['candidate_source_id'],'evidence_sha256':h})
    with pytest.raises(OwnershipPreflightError,match='دو ردیف مثبت'):
        audit(p,project,{'policy':POLICY,'project_id':'P','mappings':maps},docs)


@pytest.mark.parametrize('changed',[
    'source','candidate_hash','engine','component','operation','unit','quantity','scope_empty',
    'coordinate_wrong','geometry_hash','payer','detail_empty','reviewer_same',
    'interface_status','schema','extra','missing','float','nan','dup_json_key','stale_doc',
])
def test_malicious_or_stale_document_fails(sources,changed):
    p,project=sources
    c=next(x for x in _claims(p,project).values() if x['engine']=='shear_wall' and x['operation']=='concrete')
    d=doc_for(c)
    if changed=='source':d['candidate_source_id']='other'
    if changed=='candidate_hash':d['candidate_sha256']='0'*64
    if changed=='engine':d['engine']='pile'
    if changed=='component':d['physical_component_id']='fake'
    if changed=='operation':d['operation']='formwork'
    if changed=='unit':d['unit']='m2'
    if changed=='quantity':d['quantity_exact']='1000'
    if changed=='scope_empty':d['scope_id']=' '
    if changed=='coordinate_wrong':d['coordinate_ref']='WRONG'
    if changed=='geometry_hash':d['geometry_document_sha256']='bad'
    if changed=='payer':d['paying_source_id']='another'
    if changed=='detail_empty':d['detail_ref']=''
    if changed=='reviewer_same':d['independent_reviewer']='editor a'
    if changed=='interface_status':d['interface_review_status']='ENGINEER_APPROVED'
    if changed=='schema':d['schema']='another'
    if changed=='extra':d['allow_pay']=True
    if changed=='missing':del d['detail_ref']
    if changed=='float':d['quantity_exact']=float(d['quantity_exact'])
    if changed=='nan':d['quantity_exact']='NaN'
    if changed=='float':
        b=json.dumps(d,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        h=hashlib.sha256(b).hexdigest()
    else:
        h,b=evidence(d)
    if changed=='dup_json_key':
        b=b[:-1]+b',"project_id":"FAKE"}'
        h=hashlib.sha256(b).hexdigest()
    if changed=='stale_doc':
        b=b.replace(b'P',b'Z',1)
    with pytest.raises(OwnershipPreflightError):
        audit(p,project,{'policy':POLICY,'project_id':'P','mappings':[
              {'candidate_source_id':c['candidate_source_id'],'evidence_sha256':h}]},{h:b,GEOMETRY_HASH:GEOMETRY_BYTES})


@pytest.mark.parametrize('case',[
  'wrong_project','extra_key','missing_key','unknown_candidate','duplicate_mapping','missing_file',
  'bad_hash','claims_missing','wrong_preview_policy','claims_fake_approval',
  'negative_quantity','float_quantity','wrong_unit','historical_duplicate',
  'wrong_deduction','duplicate_deduction','fake_gross',
])
def test_unsafe_previews_and_ledger_rejected(sources,case):
    p,project=sources
    ledger,docs=fixture_ledger(p,project)
    if case=='wrong_project':ledger['project_id']='ANOTHER'
    elif case=='extra_key':ledger['authorized']=True
    elif case=='missing_key':ledger.pop('policy')
    elif case=='unknown_candidate':ledger['mappings'][0]['candidate_source_id']='NO-SUCH-ID'
    elif case=='duplicate_mapping':ledger['mappings'].append(deepcopy(ledger['mappings'][0]))
    elif case=='missing_file':docs.clear()
    elif case=='bad_hash':ledger['mappings'][0]['evidence_sha256']='UPPER'
    elif case=='claims_missing':p.pop('shear_wall')
    elif case=='wrong_preview_policy':p['stair']['policy']='FAKE'
    elif case=='claims_fake_approval':p['bored_pile']['commit_allowed']=True
    elif case in ('negative_quantity','float_quantity','wrong_unit'):
        row=next(r for r in p['shear_wall']['takeoff_candidates'] if r['quantities'][0]['unit']=='m3')
        row['quantities'][0]['amount']={'negative_quantity':'-1','float_quantity':1.1,'wrong_unit':'3'}[case]
        if case=='wrong_unit':row['quantities'][0]['unit']='kg'
    elif case=='historical_duplicate':project['takeoffs'].append(deepcopy(p['stair']['takeoff_candidates'][0]))
    elif case in ('wrong_deduction','duplicate_deduction','fake_gross'):
        row=next(r for r in p['shear_wall']['takeoff_candidates'] if r['quantities'][0]['unit']=='m3')
        if case=='wrong_deduction':row['params']['intersections'][0]['volume_m3']='-2'
        if case=='duplicate_deduction':row['params']['intersections'].append(deepcopy(row['params']['intersections'][0]))
        if case=='fake_gross':row['params']['gross_concrete_m3']='1'
    with pytest.raises(OwnershipPreflightError):
        audit(p,project,ledger,docs)


def test_exact_long_decimal_and_nonstrict_reviewer(sources):
    p,project=sources
    c=next(x for x in _claims(p,project).values() if x['engine']=='stair' and len(x['quantity_exact'])>40)
    d=doc_for(c)
    h,b=evidence(d)
    r=audit(p,project,{'policy':POLICY,'project_id':'P','mappings':[{'candidate_source_id':c['candidate_source_id'],'evidence_sha256':h}]},{h:b,GEOMETRY_HASH:GEOMETRY_BYTES})
    assert r['reviewed_evidence'][0]['quantity_exact']==c['quantity_exact']
    assert len(r['reviewed_evidence'][0]['quantity_exact'])>40


def test_geometry_bytes_are_not_optional(sources):
    p,project=sources
    ledger,docs=fixture_ledger(p,project)
    docs.pop(GEOMETRY_HASH)
    with pytest.raises(OwnershipPreflightError,match='هندسی'):
        audit(p,project,ledger,docs)


def test_geometry_bytes_tampering_detected(sources):
    p,project=sources
    ledger,docs=fixture_ledger(p,project)
    docs[GEOMETRY_HASH]=b'ALTERED DRAWING'
    with pytest.raises(OwnershipPreflightError,match='هندسی'):
        audit(p,project,ledger,docs)


@pytest.mark.parametrize('x',[-1,0,'0','NaN','Infinity','-Infinity',float('inf'),0.1,True,{},None])
def test_strict_decimal_rejects_invalid(x):
    with pytest.raises(OwnershipPreflightError):amount(x)


def test_existing_project_snapshot_remains_read_only(sources):
    p,project=sources
    row={'source_id':'historical-different','params':{'physical_component_id':'old'},'quantities':[]}
    project['takeoffs']=[row]
    before=deepcopy((p,project))
    r=audit(p,project,{'policy':POLICY,'project_id':'P','mappings':[]},{})
    assert r['blockers'] and 'تاریخی' in r['blockers'][-1]
    assert (p,project)==before


def test_schema_summary_exact_count(sources):
    p,project=sources
    r=audit(p,project,{'policy':POLICY,'project_id':'P','mappings':[]},{})
    assert r['candidate_count_by_operation']['concrete']>0
    assert r['candidate_count_by_operation']['formwork']>0
    assert sum(r['candidate_count_by_operation'].values())==r['candidate_count']
