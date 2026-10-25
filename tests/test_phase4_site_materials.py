"""W3 domain acceptance: independent exact oracles, real source files, no network."""
from copy import deepcopy
from decimal import Decimal, localcontext
import hashlib
import importlib
import pytest
from core.takeoff.boq import build_boq


def domain():
    try:return importlib.import_module('core.projects.site_materials')
    except ModuleNotFoundError:pytest.fail('W3 material domain is not implemented')


@pytest.fixture
def p(tmp_path):
    f=tmp_path/'approved-source.txt';f.write_text('explicit fixture drawing and stock evidence v1')
    source={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'reference':'drawing/stock v1'}
    qty=[('concrete','m3','10'),('formwork','m2','20'),('block','m2','12.5'),('tile','m2','30'),('pipe','m','17.25')]
    takeoffs=[{'source_id':'T1','status':'approved','approved_by':'engineer','revision':'R1','quantities':[{'code':c,'unit':u,'amount':q,'title':c,'formula':'fixture explicit approved amount'} for c,u,q in qty]}]
    boq=build_boq([{'source_id':'T1','source_ids':['T1'],'item_code':c,'unit':u,'quantity':q,'description':c} for c,u,q in qty])
    return {'id':'P','takeoffs':takeoffs,'boq':boq,'source_fixture':source,'floors':[{'id':'F'}],'zones':[{'id':'Z','floor_ids':['F']}],'project_schedule_tasks':[{'id':'A','floor_ids':['F'],'zone_ids':['Z']},{'id':'B','floor_ids':['F'],'zone_ids':['Z']}],'project_materials':[{'id':'legacy','name':'CON','quantity':999,'unit':'m3','status':'received'}]}


def run(p,op,actor='creator',**data):
    isolated=deepcopy(p)
    out=domain().dispatch(isolated,op,data,actor,'fixture reason')
    p.clear();p.update(isolated)
    return out


def rule(p,id='R',code='CON',base='m3',unit='m3',ratio='1',waste='0'):
    run(p,'material_rule_create',id=id,material_code=code,specification=code+' specification',base_unit=base,material_unit=unit,ratio=ratio,waste_percent=waste,source_version='v1',source=p['source_fixture'])
    run(p,'material_rule_review',actor='reviewer',id=id)
    return run(p,'material_rule_approve',actor='approver',id=id)


def need(p,id='N',rule_id='R',item='concrete',activity='A',**extra):
    return run(p,'material_need',id=id,rule_id=rule_id,source_ids=['T1'],item_code=item,activity_id=activity,floor_ids=['F'],zone_ids=['Z'],period_start='2026-01-01',period_end='2026-01-31',**extra)


def stock(p,op,id,qty='0',**extra):
    return run(p,'inventory_'+op,id=id,material_code='CON',unit='m3',quantity=qty,date='2026-01-01',reference=id,source=p['source_fixture'],confirmed=True,**extra)


def close(p,id='C'):
    return run(p,'inventory_close',id=id,material_code='CON',unit='m3',period_start='2026-01-01',period_end='2026-01-31',source=p['source_fixture'],confirmed=True)


def view(p):return domain().snapshot(p,as_of='2026-01-31')['requirements'][0]


@pytest.mark.parametrize('item,code,base,unit,ratio,waste,expected',[
    ('concrete','CON','m3','m3','1','2.5','10.250'),('block','BLK','m2','count','12','0','150.0'),
    ('tile','TIL','m2','m2','1','7','32.1'),('pipe','PIP','m','m','1.02','0','17.5950')])
def test_approved_material_need_exact_for_four_materials(p,item,code,base,unit,ratio,waste,expected):
    rule(p,code=code,base=base,unit=unit,ratio=ratio,waste=waste)
    result=need(p,item=item)
    assert Decimal(result['quantity'])==Decimal(expected)
    assert isinstance(result['quantity'],str)
    assert result['material_code']==code


def test_partial_receipt_consumption_reservation_and_no_double_count(p):
    rule(p);need(p);stock(p,'opening','O','2');stock(p,'receipt','I','4')
    stock(p,'reserve','V','3',requirement_id='N');stock(p,'consume','U','2',requirement_id='N');close(p)
    v=view(p)
    assert {k:Decimal(v[k]) for k in ['quantity','consumed','reserved','on_hand','free_stock','shortage']}=={'quantity':Decimal(10),'consumed':Decimal(2),'reserved':Decimal(1),'on_hand':Decimal(4),'free_stock':Decimal(3),'shortage':Decimal(4)}
    assert p['project_materials'][0]['quantity']==999


def test_other_requirement_reservations_reduce_available_supply(p):
    rule(p);need(p);rule(p,id='R2',base='m2',ratio='.1');need(p,id='N2',rule_id='R2',item='formwork',activity='B')
    stock(p,'opening','O','5');stock(p,'reserve','V','2',requirement_id='N2');close(p)
    assert Decimal(view(p)['shortage'])==7


@pytest.mark.parametrize('missing',['opening','closure'])
def test_missing_stock_coverage_is_unknown_not_zero(p,missing):
    rule(p);need(p)
    if missing=='closure':stock(p,'opening','O','0')
    else:close(p)
    assert view(p)['shortage'] is None


def test_explicit_zero_coverage_produces_true_zero_supply_and_need_shortage(p):
    rule(p);need(p);stock(p,'opening','O','0');close(p)
    assert Decimal(view(p)['on_hand'])==0 and Decimal(view(p)['shortage'])==10


def test_returns_and_append_only_correction(p):
    rule(p);need(p);stock(p,'opening','O','4');stock(p,'receipt','I','5');stock(p,'consume','U','3',requirement_id='N')
    stock(p,'return','RT','1',direction='stock_in',reference_id='U')
    stock(p,'return','RS','2',direction='stock_out',reference_id='I')
    stock(p,'correct','X',reference_id='RS');close(p)
    assert Decimal(view(p)['on_hand'])==7 and Decimal(view(p)['consumed'])==2
    assert len(p['project_materials'])==7
    assert next(x for x in p['project_materials'] if x['id']=='RS')['quantity']=='2'


def test_closure_invalidated_by_later_backdated_receipt(p):
    rule(p);need(p);stock(p,'opening','O','0');close(p)
    stock(p,'receipt','I','2')
    assert view(p)['shortage'] is None
    close(p,id='C2');assert Decimal(view(p)['shortage'])==8


def test_rule_independent_review_and_approval(p):
    run(p,'material_rule_create',id='R',material_code='CON',specification='C30',base_unit='m3',material_unit='m3',ratio='1',waste_percent='0',source_version='v1',source=p['source_fixture'])
    with pytest.raises(ValueError):run(p,'material_rule_approve',actor='approver',id='R')
    with pytest.raises(ValueError):run(p,'material_rule_review',id='R')
    run(p,'material_rule_review',actor='reviewer',id='R')
    with pytest.raises(ValueError):run(p,'material_rule_approve',actor='reviewer',id='R')


@pytest.mark.parametrize('case',['unit','reference','negative','reserve','consume','unconfirmed','cross_project','return_cap','double_correction'])
def test_invalid_inventory_postings_rejected(p,case):
    rule(p);need(p);stock(p,'opening','O','5');stock(p,'receipt','I','2')
    with pytest.raises(ValueError):
        if case=='unit':run(p,'inventory_receipt',id='X',material_code='CON',unit='kg',quantity='1',date='2026-01-01',reference='X',source=p['source_fixture'],confirmed=True)
        elif case=='reference':run(p,'inventory_receipt',id='X',material_code='CON',unit='m3',quantity='1',date='2026-01-01',reference='I',source=p['source_fixture'],confirmed=True)
        elif case=='negative':stock(p,'consume','X','8',requirement_id='N')
        elif case=='reserve':stock(p,'reserve','X','11',requirement_id='N')
        elif case=='consume':stock(p,'consume','X','11',requirement_id='N')
        elif case=='unconfirmed':run(p,'inventory_receipt',id='X',material_code='CON',unit='m3',quantity='1',date='2026-01-01',reference='X',source=p['source_fixture'])
        elif case=='cross_project':stock(p,'consume','X','1',requirement_id='FOREIGN')
        elif case=='return_cap':stock(p,'return','X','3',direction='stock_out',reference_id='I')
        else:
            stock(p,'correct','X',reference_id='I');stock(p,'correct','Y',reference_id='I')


def test_duplicate_physical_material_allocation_rejected_but_distinct_operation_allowed(p):
    rule(p);need(p)
    with pytest.raises(ValueError):need(p,id='N2',activity='B')
    rule(p,id='F',code='FORM',base='m2',unit='m2');assert need(p,id='N3',rule_id='F',item='formwork')['item_code']=='formwork'


def test_aggregate_requires_entire_source_set(p):
    p['takeoffs'].append({**deepcopy(p['takeoffs'][0]),'source_id':'T2'})
    for r in p['boq']:r['source_ids']=['T1','T2'];r['quantity']=str(Decimal(str(r['quantity']))*2)
    rule(p)
    with pytest.raises(ValueError):need(p)


def test_stale_boq_rule_and_evidence_never_current(p):
    rule(p);need(p);stock(p,'opening','O','0');close(p)
    p['takeoffs'][0]['quantities'][0]['amount']='11';p['boq'][0]['quantity']='11'
    assert view(p)['current'] is False and view(p)['shortage'] is None
    n=need(p,id='N2',supersedes='N');assert n['quantity']=='11'
    assert len(p['material_requirements'])==2
    p['material_rules'][0]['ratio']='2'
    assert domain().snapshot(p,as_of='2026-01-31')['requirements'][-1]['current'] is False


def test_tampered_evidence_blocks_shortage_and_purchase(p):
    rule(p);need(p);stock(p,'opening','O','0');close(p)
    from pathlib import Path
    Path(p['source_fixture']['path']).write_text('tampered')
    assert view(p)['shortage'] is None
    with pytest.raises(ValueError):run(p,'purchase_draft',id='P1',requirement_id='N',as_of='2026-01-31',owner='buyer')


def test_purchase_draft_missing_price_and_independent_approval_no_finance_effect(p):
    rule(p);need(p);stock(p,'opening','O','2');close(p);boq=deepcopy(p['boq'])
    purchase=run(p,'purchase_draft',id='P1',requirement_id='N',as_of='2026-01-31',owner='buyer')
    assert purchase['quantity']=='8' and purchase['price'] is None and purchase['supplier'] is None
    run(p,'purchase_review',actor='reviewer',id='P1')
    with pytest.raises(ValueError):run(p,'purchase_approve',actor='reviewer',id='P1')
    assert run(p,'purchase_approve',actor='approver',id='P1')['status']=='approved'
    assert p['boq']==boq and 'financial_documents' not in p


def test_price_requires_currency_and_source_and_stale_purchase_rejected(p):
    rule(p);need(p);stock(p,'opening','O','0');close(p)
    with pytest.raises(ValueError):run(p,'purchase_draft',id='P1',requirement_id='N',as_of='2026-01-31',owner='buyer',price='100')
    run(p,'purchase_draft',id='P1',requirement_id='N',as_of='2026-01-31',owner='buyer',price='100',currency='IRR',price_source=p['source_fixture'])
    stock(p,'receipt','I','1');close(p,id='C2')
    with pytest.raises(ValueError):run(p,'purchase_review',actor='reviewer',id='P1')


def test_high_precision_need_and_snapshot_are_lossless_read_only(p):
    amount='12345678901234567890.12345678901234567890123456789'
    p['takeoffs'][0]['quantities'][0]['amount']=amount;p['boq'][0]['quantity']=amount
    ratio='1.12345678901234567890123456789';rule(p,ratio=ratio,waste='0.12345678901234567890123456789')
    n=need(p)
    with localcontext() as ctx:
        ctx.prec=512
        expected=Decimal(amount)*Decimal(ratio)*(1+Decimal('0.12345678901234567890123456789')/100)
    assert Decimal(n['quantity'])==expected
    original=deepcopy(p);domain().snapshot(p,as_of='2026-01-31');assert p==original


def test_unapproved_boq_sources_and_bad_location_rejected(p):
    rule(p);p['takeoffs'][0].pop('approved_by');p['takeoffs'][0]['status']='draft'
    with pytest.raises(ValueError):need(p)
    p['takeoffs'][0]['status']='approved'
    with pytest.raises(ValueError):run(p,'material_need',id='N',rule_id='R',source_ids=['T1'],item_code='concrete',activity_id='A',floor_ids=['FOREIGN'],zone_ids=['Z'],period_start='2026-01-01',period_end='2026-01-31')


def test_material_rule_and_requirement_cannot_be_transplanted_between_projects(p):
    rule(p);need(p);p['id']='FOREIGN'
    assert view(p)['current'] is False
    with pytest.raises(ValueError):need(p,id='N2',supersedes='N')


def test_backdated_inventory_cannot_erase_a_historic_negative_balance(p):
    rule(p);need(p);stock(p,'opening','O','2')
    run(p,'inventory_receipt',id='LATE',material_code='CON',unit='m3',quantity='10',date='2026-01-20',reference='LATE',source=p['source_fixture'],confirmed=True)
    with pytest.raises(ValueError):
        run(p,'inventory_consume',id='EARLY',material_code='CON',unit='m3',quantity='3',date='2026-01-02',reference='EARLY',source=p['source_fixture'],confirmed=True,requirement_id='N')


def test_audit_bound_quantity_approval_accepts_canonical_legacy_takeoff(p):
    from core.projects.controls import boq_basis
    rule(p);p['takeoffs'][0].pop('approved_by');p['takeoffs'][0].pop('status')
    approval={'source':p['source_fixture'],'approved_by':'engineer','source_version':'v1','basis_digest':boq_basis(p,p['boq'][0])}
    assert need(p,quantity_approval=approval)['quantity_approval']['approved_by']=='engineer'


def test_quantity_approval_must_bind_exact_current_boq(p):
    rule(p);p['takeoffs'][0].pop('approved_by');p['takeoffs'][0].pop('status')
    with pytest.raises(ValueError):need(p,quantity_approval={'source':p['source_fixture'],'approved_by':'engineer','source_version':'v1','basis_digest':'forged'})


def test_reversal_chain_allows_dependency_then_parent_correction(p):
    rule(p);need(p);stock(p,'opening','O','10');stock(p,'consume','U','3',requirement_id='N')
    stock(p,'return','RT','1',direction='stock_in',reference_id='U')
    stock(p,'correct','X',reference_id='RT')
    stock(p,'correct','Y',reference_id='U');close(p)
    assert Decimal(view(p)['consumed'])==0 and Decimal(view(p)['on_hand'])==10


def test_snapshot_before_last_covered_event_still_has_known_stock(p):
    rule(p);need(p);stock(p,'opening','O','2')
    run(p,'inventory_receipt',id='LATE',material_code='CON',unit='m3',quantity='3',date='2026-01-20',reference='LATE',source=p['source_fixture'],confirmed=True)
    close(p)
    v=domain().snapshot(p,as_of='2026-01-10')['requirements'][0]
    assert v['stock_known'] is True and Decimal(v['on_hand'])==2


def test_correction_infers_exact_quantity_from_referenced_document(p):
    rule(p);need(p);stock(p,'opening','O','0');stock(p,'receipt','I','3.25')
    e=run(p,'inventory_correct',id='X',material_code='CON',unit='m3',date='2026-01-02',reference='X',source=p['source_fixture'],confirmed=True,reference_id='I')
    assert e['quantity']=='3.25'


def test_common_free_stock_is_allocated_once_across_distinct_requirements(p):
    rule(p);need(p);rule(p,id='R2',base='m2',ratio='.1');need(p,id='N2',rule_id='R2',item='formwork',activity='B')
    stock(p,'opening','O','5');close(p)
    rows=domain().snapshot(p,as_of='2026-01-31')['requirements']
    assert sum((Decimal(r['shortage']) for r in rows),Decimal(0))==7
    assert Decimal(rows[0]['shortage'])==5 and Decimal(rows[1]['shortage'])==2
    assert domain().snapshot(p,as_of='2026-01-31',activity_id='B')['requirements'][0]['shortage']=='2.0'


def test_superseding_after_documented_full_reversal_preserves_history(p):
    rule(p);need(p);stock(p,'opening','O','10');stock(p,'consume','U','2',requirement_id='N');stock(p,'correct','X',reference_id='U')
    p['takeoffs'][0]['quantities'][0]['amount']='11';p['boq'][0]['quantity']='11'
    need(p,id='N2',supersedes='N')
    assert len(p['material_requirements'])==2
    assert len(p['project_materials'])==4


def test_approved_purchase_snapshot_revalidates_stock_and_document_integrity(p):
    rule(p);need(p);stock(p,'opening','O','0');close(p)
    run(p,'purchase_draft',id='P1',requirement_id='N',as_of='2026-01-31',owner='buyer')
    run(p,'purchase_review',actor='reviewer',id='P1');run(p,'purchase_approve',actor='approver',id='P1')
    assert domain().snapshot(p,as_of='2026-01-31')['purchase_drafts'][0]['current'] is True
    p['purchase_drafts'][0]['quantity']='999'
    assert domain().snapshot(p,as_of='2026-01-31')['purchase_drafts'][0]['current'] is False
    p['purchase_drafts'][0]['quantity']='10';stock(p,'receipt','I','1');close(p,id='C2')
    assert domain().snapshot(p,as_of='2026-01-31')['purchase_drafts'][0]['basis_stale'] is True


def test_operation_registry_lists_every_supported_command():
    assert {'material_rule_create','material_rule_review','material_rule_approve','material_need',
            'inventory_opening','inventory_receipt','inventory_consume','inventory_reserve','inventory_return',
            'inventory_correct','inventory_close','purchase_draft','purchase_review','purchase_approve','purchase_cancel'}==set(domain().OPS)

def test_purchase_cancel_preserves_amount_and_allows_new_reviewed_request(p):
    rule(p);need(p);stock(p,'opening','O','0');close(p)
    first=run(p,'purchase_draft',id='BUY',requirement_id='N',as_of='2026-01-31',owner='creator')
    run(p,'purchase_review',actor='reviewer',id='BUY');run(p,'purchase_approve',actor='approver',id='BUY')
    run(p,'purchase_cancel',id='BUY')
    assert p['purchase_drafts'][0]['quantity']==first['quantity'] and p['purchase_drafts'][0]['status']=='cancelled'
    second=run(p,'purchase_draft',id='BUY2',requirement_id='N',as_of='2026-01-31',owner='creator')
    assert second['status']=='draft'


def test_explicit_quantity_approval_cannot_launder_unreviewed_ai(p):
    from core.projects.controls import boq_basis
    rule(p);p['takeoffs'][0].pop('approved_by');p['takeoffs'][0]['status']='unreviewed';p['takeoffs'][0]['provenance']={'mode':'ai'}
    approval={'source':p['source_fixture'],'approved_by':'engineer','source_version':'v1','basis_digest':boq_basis(p,p['boq'][0])}
    with pytest.raises(ValueError):need(p,quantity_approval=approval)


def test_existing_committed_specialist_review_uses_canonical_review_metadata(p):
    rule(p);p['takeoffs'][0].pop('approved_by');p['takeoffs'][0].pop('status');p['takeoffs'][0]['review']={'approved_by':'specialist'}
    p['reviewed_aec_systems']={'specialist':{'status':'committed','source_ids':['T1']}}
    assert need(p)['quantity_approval'] is None


def test_mistaken_explicit_zero_opening_can_be_reversed_then_replaced(p):
    rule(p);need(p);stock(p,'opening','O','0')
    stock(p,'correct','X',reference_id='O')
    stock(p,'opening','O2','3');close(p)
    assert Decimal(view(p)['on_hand'])==3 and Decimal(view(p)['shortage'])==7
    assert next(e for e in p['project_materials'] if e['id']=='O')['quantity']=='0'
