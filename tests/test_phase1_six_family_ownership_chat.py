"""Real imported source tests of read-only six-family concrete/rebar/formwork guard."""
from copy import deepcopy
from hashlib import sha256

import pytest
from core.takeoff.building_six_family_ownership_chat import (
    POLICY, _digest, audit,
)

FAMILIES = ('foundation','tie_beam','column','beam','slab','stair')
KINDS = ('isolated_footing','tie_beam','column','beam','solid_slab','stair')
OPS = ('concrete','rebar','formwork')
UNITS = {'concrete':'m3','rebar':'kg','formwork':'m2'}
EVIDENCE = b'SYNTHETIC TAKEOFF DRAWING BYTES: NOT AN ENGINEERING SIGNATURE'
EVIDENCE_SHA = sha256(EVIDENCE).hexdigest()
GEOMETRY = b'SYNTHETIC INTERFACE BYTES: NO GEOMETRY AUTHORITY'
GEOMETRY_SHA = sha256(GEOMETRY).hexdigest()


def sample():
    project={'id':'P-1','reviewed_structural_members':{},'beam_detail_register':{},
             'reviewed_aec_systems':{},'takeoffs':[],'boq':[{'legacy':'unchanged'}]}
    links=[];claims=[]
    for family,kind in zip(FAMILIES,KINDS):
        source=f'SYN:{family}'; physical=f'MEMBER-{family}'
        registry=('beam_detail_register' if kind=='beam' else 'reviewed_aec_systems'
                  if kind in ('solid_slab','stair') else 'reviewed_structural_members')
        data={'kind':kind,'floor_id':'L1',
              'beam_id' if kind=='beam' else 'system_id' if registry=='reviewed_aec_systems' else 'member_id':kind.upper(),
              'physical_id':physical,'source':{'source_id':source},
              'geometry':{'physical_id':physical}}
        record={'status':'draft','revision':1,'data':data}
        record_key=f'{family}:1';project[registry][record_key]=record
        links.append({'family':family,'kind':kind,'floor_id':'L1',
                      'member_id':kind.upper(),'physical_member_id':physical,
                      'source_id':source,'registry':registry,'record_key':record_key,
                      'record_revision':1,'record_sha256':_digest(record)})
        for op in OPS:
            claims.append({'source_id':source,'operation':op,
                           'physical_id':f'PART:{family}:{op}','scope_id':f'SCOPE:{family}:{op}',
                           'role':'payer','payer_source_id':source,'quantity_exact':'1.250',
                           'unit':UNITS[op],'detail_ref':f'DETAIL:{family}:{op}',
                           'evidence_sha256':EVIDENCE_SHA,
                           'prepared_by':'engineer-a','reviewed_by':'engineer-b'})
    # A shared rebar can be referenced by a different member, but never paid twice.
    reference=deepcopy(next(c for c in claims if c['source_id']=='SYN:beam' and c['operation']=='rebar'))
    reference.update(source_id='SYN:column', role='reference')
    claims.append(reference)
    interface={'member_left':'MEMBER:placeholder'}
    interfaces=[{'member_left':'MEMBER-column','member_right':'MEMBER-beam',
                 'operation':'concrete','interface_id':'I-COL-BEAM',
                 'coordinate_ref':'SYN:A1','detail_ref':'SYN:JOINT-D1',
                 'geometry_evidence_sha256':GEOMETRY_SHA,
                 'prepared_by':'engineer-a','reviewed_by':'engineer-b',
                 'assessment':'UNVERIFIED_NEEDS_GEOMETRY'}]
    doc={'policy':POLICY,'project_id':'P-1','building_id':'B-1',
         'project_sha256':_digest(project),'links':links,'claims':claims,
         'interfaces':interfaces}
    docs={EVIDENCE_SHA:EVIDENCE, GEOMETRY_SHA:GEOMETRY}
    return doc,project,docs


def check_valid(d=None,p=None,files=None):
    if d is None:d,p,files=sample()
    return audit(d,p,documents=files)


def blocked(mutator):
    doc,project,docs=sample()
    mutator(doc,project,docs)
    before=deepcopy((doc,project,docs))
    result=check_valid(doc,project,docs)
    assert result['document_consistent'] is False, result
    assert result['ready'] is False and result['commit_allowed'] is False
    assert result['payable_rows']==[] and result['physical_owner_count']==0
    assert result['totals_not_payable']=={} and result['blockers']
    assert (doc,project,docs)==before


def test_all_six_member_registries_and_three_operations_explicitly_reconciled():
    doc,project,docs=sample()
    snapshot=deepcopy((doc,project,docs))
    out=check_valid(doc,project,docs)
    assert out['document_consistent'] is True
    assert out['physical_owner_count']==18
    assert out['material_rows_by_operation']=={'concrete':6,'rebar':6,'formwork':6}
    assert out['totals_not_payable']=={'concrete':'7.500','formwork':'7.500','rebar':'7.500'}
    assert out['unresolved_interfaces']==['I-COL-BEAM']
    assert out['payable_rows']==[] and not out['commit_allowed'] and not out['ready']
    assert out['blockers'] and (doc,project,docs)==snapshot


def test_no_interface_claim_never_implies_real_geometric_clearance():
    doc,project,docs=sample();doc['interfaces']=[]
    out=check_valid(doc,project,docs)
    assert out['document_consistent']
    assert out['payable_rows']==[]
    assert any('هیچ فصل مشترک' in s for s in out['blockers'])


@pytest.mark.parametrize('family', FAMILIES)
def test_missing_any_one_of_six_families_fails_closed(family):
    blocked(lambda d,p,b: d['links'].__setitem__(slice(None),[x for x in d['links'] if x['family']!=family]))


@pytest.mark.parametrize('operation', OPS)
def test_two_material_payers_on_same_physical_part_are_rejected(operation):
    def change(d,p,b):
        row=next(x for x in d['claims'] if x['source_id']=='SYN:beam' and x['operation']==operation)
        new=deepcopy(row);new['source_id']='SYN:column';new['payer_source_id']='SYN:column';new['role']='payer'
        d['claims'].append(new)
    blocked(change)


@pytest.mark.parametrize('operation', OPS)
def test_different_physical_ids_same_scope_are_not_disjoint_by_declaration(operation):
    def change(d,p,b):
        target=next(x for x in d['claims'] if x['source_id']=='SYN:beam' and x['operation']==operation)
        target['scope_id']=next(x for x in d['claims'] if x['source_id']=='SYN:column' and x['operation']==operation)['scope_id']
    blocked(change)


@pytest.mark.parametrize('operation', OPS)
def test_same_physical_id_used_for_two_different_operations_is_rejected(operation):
    def change(d,p,b):
        a=next(x for x in d['claims'] if x['source_id']=='SYN:beam' and x['operation']==operation)
        other=next(x for x in d['claims'] if x['source_id']=='SYN:foundation' and x['operation']!=operation)
        a['physical_id']=other['physical_id']
    blocked(change)


@pytest.mark.parametrize('field,value',[
    ('quantity_exact','0'),('quantity_exact','NaN'),('quantity_exact','1e500'),
    ('quantity_exact',1.25),('quantity_exact',True),('unit','عدد'),
    ('payer_source_id','SYN:unknown'),('role','unknown'),
    ('prepared_by','engineer-b'),('evidence_sha256','0'*64),
])
def test_invalid_material_quantity_unit_owner_or_evidence_fails_closed(field,value):
    blocked(lambda d,p,b:d['claims'][0].__setitem__(field,value))


@pytest.mark.parametrize('case',[0,1,2,3,4,5,6,7,8])
def test_member_record_snapshot_identity_is_pinned(case):
    def change(d,p,b):
        link=d['links'][0]
        rec=p['reviewed_structural_members'][link['record_key']]
        if case==0:link['record_revision']=2
        elif case==1:link['record_sha256']='0'*64
        elif case==2:rec['data']['geometry']['physical_id']='CHANGED'
        elif case==3:rec['status']='committed'
        elif case==4:rec['data']['source']['source_id']='ANOTHER'
        elif case==5:link['kind']='beam'
        elif case==6:link['family']='stair'
        elif case==7:link['registry']='reviewed_aec_systems'
        elif case==8:link['physical_member_id']='DIFFERENT'
        if case in (2,3,4):d['project_sha256']=_digest(p)
    blocked(change)


def test_project_snapshot_edit_prevents_stale_claim_passing():
    blocked(lambda d,p,b:p['boq'].append({'new':True}))


def test_reference_requires_exact_single_payer_and_identical_scope():
    blocked(lambda d,p,b:d['claims'][-1].__setitem__('quantity_exact','2'))


def test_reference_cannot_change_payer():
    blocked(lambda d,p,b:d['claims'][-1].__setitem__('payer_source_id','SYN:column'))


def test_no_payer_reference_only_is_rejected():
    blocked(lambda d,p,b:d['claims'][0].update(role='reference',payer_source_id='SYN:beam'))


def test_duplicate_same_member_claim_does_not_create_second_quantity():
    blocked(lambda d,p,b:d['claims'].append(deepcopy(d['claims'][0])))


def test_historical_physical_piece_disallows_second_payer():
    def change(d,p,b):
        p['takeoffs'].append({'source_id':'OLD','params':{'physical_component_id':'PART:beam:rebar'}})
        d['project_sha256']=_digest(p)
    blocked(change)


def test_historical_unidentified_rows_remain_explicit_blockers():
    d,p,b=sample();p['takeoffs'].append({'source_id':'LEGACY','params':{},'description':'متره قدیمی'})
    d['project_sha256']=_digest(p)
    out=check_valid(d,p,b)
    assert out['document_consistent']
    assert out['blocked_historical_rows']==[0]
    assert out['payable_rows']==[]
    assert any('تاریخی' in s for s in out['blockers'])


@pytest.mark.parametrize('case',[0,1,2,3,4,5,6,7,8,9])
def test_interface_mismatch_never_unblocks_geometry_or_payment(case):
    def change(d,p,b):
        x=d['interfaces'][0]
        if case==0:x['member_left']='UNKNOWN'
        elif case==1:x['member_right']=x['member_left']
        elif case==2:x['operation']='steel'
        elif case==3:x['geometry_evidence_sha256']='f'*64
        elif case==4:x['prepared_by']=x['reviewed_by']
        elif case==5:x['assessment']='SIGNED_APPROVED'
        elif case==6:d['interfaces'].append(deepcopy(x))
        elif case==7:x['coordinate_ref']=''
        elif case==8:b[x['geometry_evidence_sha256']]=b'tampered'
        elif case==9:x.pop('detail_ref')
    blocked(change)


def test_contradictory_physical_member_ids_in_two_registries_fail_closed():
    def change(d,p,b):
        a=d['links'][0];z=d['links'][1]
        z['physical_member_id']=a['physical_member_id']
        r=p[z['registry']][z['record_key']]
        r['data']['physical_id']=a['physical_member_id']
        r['data']['geometry']['physical_id']=a['physical_member_id']
        z['record_sha256']=_digest(r)
        d['project_sha256']=_digest(p)
    blocked(change)


def test_no_partial_totals_survive_late_invalid_claim():
    blocked(lambda d,p,b:d['claims'][-1].__setitem__('evidence_sha256','0'*64))


def test_manual_six_family_document_does_not_change_sqlite_boq():
    d,p,b=sample();existing=deepcopy((p['boq'],p['takeoffs'],p['reviewed_structural_members']))
    out=check_valid(d,p,b)
    assert out['document_consistent']
    assert (p['boq'],p['takeoffs'],p['reviewed_structural_members'])==existing
    assert not out['ready'] and not out['commit_allowed']


def test_registered_seventh_member_cannot_be_hidden_from_reconciliation():
    def change(d,p,b):
        rec=deepcopy(next(iter(p['reviewed_structural_members'].values())))
        rec['data']['member_id']='NEW-FOOTING'
        rec['data']['physical_id']='NEW-FOOTING-PH'
        rec['data']['geometry']['physical_id']='NEW-FOOTING-PH'
        p['reviewed_structural_members']['EXTRA']=rec
        d['project_sha256']=_digest(p)
    blocked(change)


def test_same_physical_id_with_unicode_compatibility_form_is_rejected():
    def change(d,p,b):
        x=next(c for c in d['claims'] if c['source_id']=='SYN:column' and c['operation']=='concrete')
        y=next(c for c in d['claims'] if c['source_id']=='SYN:foundation' and c['operation']=='concrete')
        y['physical_id']=x['physical_id'].replace('P','Ｐ')
    blocked(change)


def test_alias_of_scope_id_does_not_hide_double_count():
    def change(d,p,b):
        x=next(c for c in d['claims'] if c['source_id']=='SYN:column' and c['operation']=='formwork')
        y=next(c for c in d['claims'] if c['source_id']=='SYN:foundation' and c['operation']=='formwork')
        y['scope_id']=x['scope_id'].replace('S','Ｓ')
    blocked(change)


def test_invisible_character_inside_member_identity_not_allowed():
    blocked(lambda d,p,b:d['claims'][0].__setitem__('physical_id','BAD\u200dID'))


def test_previously_paid_boq_physical_item_blocks_second_payment():
    def change(d,p,b):
        p['boq'].append({'params':{'physical_piece_id':'PART:beam:concrete'}})
        d['project_sha256']=_digest(p)
    blocked(change)


def test_historical_boq_without_physical_identity_remains_explicit_blocker():
    d,p,b=sample();out=check_valid(d,p,b)
    assert out['document_consistent'] is True
    assert out['blocked_historical_boq_rows']==[0]
    assert out['blockers'] and out['payable_rows']==[]


def test_physical_piece_cannot_share_member_id():
    blocked(lambda d,p,b:d['claims'][0].__setitem__('physical_id','MEMBER-column'))


def test_wrong_building_id_against_explicit_project_building_id_is_rejected():
    d,p,b=sample();p['building_id']='B-1';d['project_sha256']=_digest(p)
    d['building_id']='OTHER-BUILDING'
    out=check_valid(d,p,b)
    assert not out['document_consistent'] and out['payable_rows']==[]


def test_long_decimal_sums_are_exact_not_binary_float_or_context_rounded():
    d,p,b=sample()
    d['claims'][0]['quantity_exact']='1.12345678901234567890123456789012345678901234567890'
    out=check_valid(d,p,b)
    assert out['document_consistent']
    assert out['totals_not_payable']['concrete']=='7.37345678901234567890123456789012345678901234567890'
    assert not out['commit_allowed'] and out['payable_rows']==[]
