"""Five bounded discipline claims: exact stored row identity, never financial approval."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_joint_crosswalk import _digest
from core.takeoff.bored_pile_ownership_preflight import OwnershipError
from core.takeoff.reviewed_aec import _id as aec_key, preview_system
from core.takeoff.engine import TakeoffEngine
from core.takeoff.phase1_five_domain_claims import POLICY, DOMAINS, audit, audit_file
from test_reviewed_aec_priorities_6_9 import sample

CASES = (
    ('steel_composite','composite_frame','steel','kg'),
    ('timber_special_roofs','timber_frame','members','m3'),
    ('architecture_finishes','facade_cladding','panels','عدد'),
    ('mep','plumbing','pipes','m'),
    ('site_renovation','external_earthwork','excavation','m3'),
)


def setup():
    registry = {};claims=[]
    for scope,kind,component,unit in CASES:
        data = sample(kind)
        data['system_id'] = 'SYS-'+scope
        data['source']['source_id'] += ':'+scope
        part = data['components'][component]
        row=part['items'][0]
        row.update(physical_component_id='PHYS-'+scope,unit=unit,quantity=1)
        assert preview_system(data,TakeoffEngine())['ready']
        key=aec_key(kind,'L1',data['system_id'])
        record={'revision':1,'status':'draft','data':data}
        registry[key]=record
        claims.append(dict(scope=scope,kind=kind,floor_id='L1',system_id=data['system_id'],
                           component=component,line_id=row['line_id'],
                           physical_component_id=row['physical_component_id'],
                           record_revision=1,record_sha256=_digest(record),quantity='1',
                           unit=unit,source_ref=row['source_ref'],measurement_ref=row['measurement_ref'],
                           evidence_ref='SOURCE-'+scope))
    project={'id':'P','reviewed_aec_systems':registry,'boq':[{'id':'HIST','params':{}}],
             'takeoffs':[{'id':'HIST','params':{}}]}
    doc={'policy':POLICY,'project_id':'P','prepared_by':'Author','reviewer':'OtherReviewer',
         'coverage':'selected_registered_items_only','claims':claims}
    return project,doc


def get_item(project,scope):
    for record in project['reviewed_aec_systems'].values():
        if record['data']['system_id']=='SYS-'+scope:
            return record['data']['components'][next(c for s,_,c,_ in CASES if s==scope)]['items'][0]
    assert False


def refresh(doc,project,scope):
    claim=next(x for x in doc['claims'] if x['scope']==scope)
    record=project['reviewed_aec_systems'][aec_key(claim['kind'],claim['floor_id'],claim['system_id'])]
    claim['record_sha256']=_digest(record)


def test_all_five_domain_selected_claims_are_readonly_and_source_bound():
    p,d=setup();old=deepcopy((p,d))
    r=audit(p,d)
    assert r['covered_scopes']==sorted(DOMAINS)
    assert r['selected_claim_count']==5
    assert r['status']=='FIVE_DOMAINS_CLAIM_PREVIEW_ONLY'
    assert r['ready_for_boq'] is False and r['commit_allowed'] is False and r['rows']==[]
    assert len(r['observations'])==5
    assert (p,d)==old
    assert any('تاریخی' in b for b in r['blockers'])


@pytest.mark.parametrize('scope,kind,component,unit',CASES)
def test_every_scope_was_revalidated_by_existing_aec_engine(scope,kind,component,unit):
    p,d=setup()
    d['claims']=[next(x for x in d['claims'] if x['scope']==scope)]
    out=audit(p,d)
    assert out['covered_scopes']==[scope]
    assert out['observations'][0]['unit']==unit
    assert out['observations'][0]['component']==component
    assert any('پنج حوزه' in b for b in out['blockers'])


@pytest.mark.parametrize('change',[
    'wrong_policy','wrong_project','same_reviewer','pretend_global','bad_scope',
    'bad_kind','bad_component','bad_line','bad_physical','duplicate_claim',
    'empty_claims','unknown_record','stale_revision','wrong_digest','float_revision',
    'float_quantity','boolean_quantity','nan_quantity','wrong_quantity','wrong_unit',
    'wrong_source','wrong_measurement','missing_evidence_ref','new_field',
    'changed_saved_quantity','changed_saved_physical','saved_record_unreviewed',
    'saved_bad_unit','saved_missing_measurement','duplicate_between_systems',
    'same_physical_other_group','wrong_data_system_id','bad_registry','bad_items',
    'invalid_approved_by','new_record_unindexed',
])
def test_fail_closed_on_stale_identity_unproven_quantity_and_cross_system_alias(change):
    p,d=setup();a=d['claims'][0]; first_scope=CASES[0][0]
    if change=='wrong_policy':d['policy']='v0'
    elif change=='wrong_project':d['project_id']='OLD'
    elif change=='same_reviewer':d['reviewer']='Author'
    elif change=='pretend_global':d['coverage']='all_physical_items_cleared'
    elif change=='bad_scope':a['scope']='not_a_scope'
    elif change=='bad_kind':a['kind']='plumbing'
    elif change=='bad_component':a['component']='timber'
    elif change=='bad_line':a['line_id']='NOT-FOUND'
    elif change=='bad_physical':a['physical_component_id']='GUESS'
    elif change=='duplicate_claim':d['claims'].append(deepcopy(a))
    elif change=='empty_claims':d['claims']=[]
    elif change=='unknown_record':p['reviewed_aec_systems'].pop(aec_key(a['kind'],a['floor_id'],a['system_id']))
    elif change=='stale_revision':a['record_revision']=2
    elif change=='wrong_digest':a['record_sha256']='f'*64
    elif change=='float_revision':a['record_revision']=1.0
    elif change=='float_quantity':a['quantity']=1.0
    elif change=='boolean_quantity':a['quantity']=True
    elif change=='nan_quantity':a['quantity']='NaN'
    elif change=='wrong_quantity':a['quantity']='1.01'
    elif change=='wrong_unit':a['unit']='عدد'
    elif change=='wrong_source':a['source_ref']='UNKNOWN'
    elif change=='wrong_measurement':a['measurement_ref']='MISMATCH'
    elif change=='missing_evidence_ref':a['evidence_ref']=''
    elif change=='new_field':a['payment_allowed']=True
    elif change=='changed_saved_quantity':get_item(p,first_scope)['quantity']=2;refresh(d,p,first_scope)
    elif change=='changed_saved_physical':get_item(p,first_scope)['physical_component_id']='OTHER';refresh(d,p,first_scope)
    elif change=='saved_record_unreviewed':
        rec=p['reviewed_aec_systems'][aec_key(a['kind'],a['floor_id'],a['system_id'])]
        rec['data']['components'][a['component']]['status']='unreviewed';refresh(d,p,first_scope)
    elif change=='saved_bad_unit':get_item(p,first_scope)['unit']='m2';refresh(d,p,first_scope)
    elif change=='saved_missing_measurement':get_item(p,first_scope).pop('measurement_ref');refresh(d,p,first_scope)
    elif change=='duplicate_between_systems':
        get_item(p,CASES[1][0])['physical_component_id']=get_item(p,first_scope)['physical_component_id']
        refresh(d,p,CASES[1][0])
    elif change=='same_physical_other_group':
        rec=p['reviewed_aec_systems'][aec_key(a['kind'],a['floor_id'],a['system_id'])]
        part=rec['data']['components']['concrete']['items'][0]
        part['physical_component_id']=a['physical_component_id'];refresh(d,p,first_scope)
    elif change=='wrong_data_system_id':
        rec=p['reviewed_aec_systems'][aec_key(a['kind'],a['floor_id'],a['system_id'])]
        rec['data']['system_id']='DIFFERENT';refresh(d,p,first_scope)
    elif change=='bad_registry':p['reviewed_aec_systems']='CORRUPT'
    elif change=='bad_items':
        rec=p['reviewed_aec_systems'][aec_key(a['kind'],a['floor_id'],a['system_id'])]
        rec['data']['components'][a['component']]['items']='CORRUPT'
    elif change=='invalid_approved_by':
        rec=p['reviewed_aec_systems'][aec_key(a['kind'],a['floor_id'],a['system_id'])]
        rec['data']['components'][a['component']]['approved_by']='';refresh(d,p,first_scope)
    elif change=='new_record_unindexed':
        # A new record without an ID must be reported as a blocker, not hard
        # rejected as an invented duplicate. This case handled separately.
        p['reviewed_aec_systems']['legacy']={'revision':1,'status':'draft','data':{
            'components': {'some':{'status':'not_applicable','items':[{'line_id':'R1'}]}},
            'kind':'some'}}
        out=audit(p,d)
        assert out['rows']==[] and any('بدون شناسه' in b for b in out['blockers'])
        return
    with pytest.raises((OwnershipError, ValueError, TypeError)):
        audit(p,d)


def test_actual_saved_sqlite_snapshot_reopens_and_keeps_finance_unchanged(tmp_path):
    p,d=setup()
    app=StructuralProApp(tmp_path/'db')
    app.create_project('پنج حوزه مهندسی مصنوعی', 'P')
    current=app.open_project('P')
    current['reviewed_aec_systems']=deepcopy(p['reviewed_aec_systems'])
    app.store.save('P',current)
    loaded=app.open_project('P')
    # Snapshot includes current system records but no dummy historical BOQ.
    doc=deepcopy(d)
    prior=deepcopy(loaded)
    evidence=tmp_path/'selected_physical_claims.json'
    raw=json.dumps(doc,sort_keys=True,ensure_ascii=False).encode('utf-8')
    evidence.write_bytes(raw)
    res=audit_file(loaded,str(evidence),sha256(raw).hexdigest())
    assert res['selected_claim_count']==5 and res['rows']==[]
    assert app.open_project('P')==prior
    assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    app.store.close()
    second=StructuralProApp(tmp_path/'db')
    try:
        assert second.open_project('P')==prior
        assert audit(second.open_project('P'),doc)['status']=='FIVE_DOMAINS_CLAIM_PREVIEW_ONLY'
        stale=second.open_project('P')
        key=aec_key(d['claims'][0]['kind'],'L1',d['claims'][0]['system_id'])
        stale['reviewed_aec_systems'][key]['revision']=2
        second.store.save('P',stale)
        with pytest.raises(OwnershipError):audit(second.open_project('P'),doc)
    finally:
        second.store.close()
    evidence.write_bytes(raw+b'\n')
    with pytest.raises(OwnershipError):audit_file(prior,str(evidence),sha256(raw).hexdigest())


@pytest.mark.parametrize('scope,kind', [
    (scope,kind) for scope,kinds in DOMAINS.items() for kind in sorted(kinds)
])
def test_all_registered_families_in_five_scopes_have_existing_reviewed_baseline(scope,kind):
    """Catalog/engine compatibility check, NOT specialist product acceptance."""
    data=sample(kind)
    preview=preview_system(data,TakeoffEngine())
    assert preview['ready'], (scope,kind,preview['blockers'])
    assert preview['rows'] and all(x['source_id'] for x in preview['rows'])


def test_real_aec_save_draft_api_and_cas_for_all_five_domains(tmp_path):
    project,doc=setup()
    app=StructuralProApp(tmp_path/'api-db')
    app.create_project('ثبت واقعی پنج خانواده مصنوعی','P')
    try:
        for claim in doc['claims']:
            key=aec_key(claim['kind'],claim['floor_id'],claim['system_id'])
            entry=app.save_aec_system_draft('P',deepcopy(project['reviewed_aec_systems'][key]['data']),expected_revision=0)
            assert entry['revision']==1
        current=app.open_project('P')
        for claim in doc['claims']:
            key=aec_key(claim['kind'],claim['floor_id'],claim['system_id'])
            claim['record_sha256']=_digest(current['reviewed_aec_systems'][key])
        after=deepcopy(current)
        assert audit(current,doc)['selected_claim_count']==5
        assert app.open_project('P')==after
        assert current['boq']==[] and current['takeoffs']==[]
        assert app.store.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        first=doc['claims'][0]
        key=aec_key(first['kind'],first['floor_id'],first['system_id'])
        draft=app.get_aec_system('P',first['kind'],first['floor_id'],first['system_id'])
        changed=deepcopy(draft['data'])
        # No edited quantities or source claims; this is a benign version bump.
        changed['notes']='nonfinancial controlled revision'
        newer=app.save_aec_system_draft('P',changed,expected_revision=1)
        assert newer['revision']==2
        with pytest.raises(OwnershipError):audit(app.open_project('P'),doc)
    finally:app.store.close()


@pytest.mark.parametrize('scope,other_kind',[
    ('steel_composite','steel_frame'),
    ('timber_special_roofs','sandwich_roof'),
    ('architecture_finishes','stone_cladding'),
    ('mep','lighting'),
    ('site_renovation','demolition'),
])
def test_cross_system_duplicate_physical_claim_is_rejected_in_each_scope(scope,other_kind):
    project,doc=setup()
    former=next(c for c in doc['claims'] if c['scope']==scope)
    previous_id=former['physical_component_id']
    other=sample(other_kind)
    other['system_id']='ADDITIONAL-'+scope
    # Fresh source identity; deliberately duplicate physical piece identity.
    other['source']['source_id'] += ':duplicate-guard-'+scope
    component=next(name for name in other['components'] if other['components'][name].get('status')=='confirmed')
    other['components'][component]['items'][0]['physical_component_id']=previous_id
    key=aec_key(other_kind,'L1',other['system_id'])
    project['reviewed_aec_systems'][key]={'revision':1,'status':'draft','data':other}
    with pytest.raises(OwnershipError,match='تکرار'):
        audit(project,doc)
