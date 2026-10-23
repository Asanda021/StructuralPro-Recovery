"""Phase 2 remaining contracts; synthetic IFC is never customer evidence."""
from decimal import Decimal
import hashlib
import json
import pytest
from core.bim.ifc import DeepIFCAdapter
from core.takeoff.ai_output_guard import validate_ai_takeoff_proposal
from test_ai_takeoff_output_guard import valid_proposal
from test_phase2_priority5_ifc import model_file

@pytest.mark.parametrize('field',['quantity','confidence','meters_per_pixel','minimum_confidence'])
def test_ai_boolean_is_not_engineering_number(field):
    proposal=valid_proposal()
    kwargs={'user_confirmed':True}
    if field=='minimum_confidence':
        kwargs[field]=True
        proposal['candidates'][0]['confidence']=1
    elif field=='meters_per_pixel':proposal['candidates'][0]['evidence'][field]=True
    else:proposal['candidates'][0][field]=True
    assert not validate_ai_takeoff_proposal(proposal,**kwargs)['valid']

@pytest.mark.parametrize('mm',[False,True])
def test_display_contract_real_ifc_units_and_reopen(tmp_path,mm):
    path=tmp_path/'مدل.ifc';_,objects=model_file(path,millimetres=mm)
    adapter=DeepIFCAdapter()
    contract=adapter.read_display_contract(path,revision='R1')
    assert contract['policy']=='ifc_display_geometry_v1'
    assert contract['source_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert contract['revision']=='R1' and contract['dimension']==3
    assert contract['coordinate_system']=='IFC world coordinates in metres'
    assert contract['quantity_authority'] is False
    assert len(contract['elements'])==12
    item=next(x for x in contract['elements'] if x['global_id']==objects[0].GlobalId)
    assert tuple(Decimal(v) for v in item['origin_m'])==(Decimal('1000000'),Decimal('7'),Decimal('0'))
    assert item['building_id'] and item['storey_id'] and item['triangles']
    ys=[v[1] for v in item['vertices_m']]
    assert max(ys)-min(ys)==pytest.approx(4)
    saved=tmp_path/'display.json';saved.write_text(json.dumps(contract),encoding='utf-8')
    assert json.loads(saved.read_text())==contract


def test_display_contract_rejects_ambiguous_units(tmp_path):
    path=tmp_path/'bad.ifc';m,_=model_file(path)
    m.by_type('IfcProject')[0].UnitsInContext=None;m.write(str(path))
    with pytest.raises(ValueError):DeepIFCAdapter().read_display_contract(path,revision='R1')


def test_project_display_contract_uses_reviewed_identity_after_reopen(tmp_path):
    from test_phase2_priority5_closure import identity_case
    from core.platform.application import StructuralProApp
    app,path,proof,proposal,args=identity_case(tmp_path)
    before=app.store.current_digest('P')
    with pytest.raises(ValueError):app.ifc_display_geometry('P',proposal['id'])
    assert app.store.current_digest('P')==before
    app.review_ifc_identity('P',**args)
    before=app.store.current_digest('P')
    data=app.ifc_display_geometry('P',proposal['id'])
    assert data['project_id']=='P' and data['member_id']=='B1' and data['floor_id']=='F1'
    assert len(data['geometry']['elements'])==1
    assert data['geometry']['elements'][0]['global_id']==proposal['global_id']
    assert data['financial_permission'] is False and data['dimension']==3
    assert app.store.current_digest('P')==before
    app.store.close(); app=StructuralProApp(tmp_path/'app')
    assert app.ifc_display_geometry('P',proposal['id'])==data
    assert app.store.integrity_check()['ok']
    proof.write_text('changed evidence')
    with pytest.raises(ValueError):app.ifc_display_geometry('P',proposal['id'])
    assert app.store.current_digest('P')==before
    app.store.close()


def test_local_ai_response_is_advisory_and_has_truthful_generator(tmp_path):
    from core.ai.local_engine import LocalAIEngine
    engine=LocalAIEngine(model_dir=tmp_path/'models',edition='standard')
    response=engine.inspect_project({'name':'explicit synthetic','takeoffs':[]})
    assert response.quantity_authority is False
    assert response.requires_user_confirmation is True
    assert response.provenance['model_id']=='local-rule-engine-v1'
    assert response.provenance['mode']=='deterministic_offline_qa'
    assert response.provenance['data_sha256']==hashlib.sha256(
        json.dumps({'name':'explicit synthetic','takeoffs':[]},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

@pytest.mark.parametrize('field',['quantity','confidence','meters_per_pixel'])
def test_ai_overflow_is_rejected_not_crashed(field):
    proposal=valid_proposal()
    container=proposal['candidates'][0]['evidence'] if field=='meters_per_pixel' else proposal['candidates'][0]
    container[field]=10**1000
    assert not validate_ai_takeoff_proposal(proposal,user_confirmed=True)['approved']

@pytest.mark.parametrize('invalid',['changed_source','no_representation','missing_revision'])
def test_display_rejects_invalid_geometry_without_project_mutation(tmp_path,invalid):
    from test_phase2_priority5_closure import identity_case
    import ifcopenshell
    app,path,proof,proposal,args=identity_case(tmp_path)
    app.review_ifc_identity('P',**args)
    before=app.store.current_digest('P')
    if invalid=='changed_source':path.write_text(path.read_text()+'\n')
    elif invalid=='no_representation':
        # A new properly reviewed source may contain QTO but no display geometry.
        model=ifcopenshell.open(str(path));model.by_guid(proposal['global_id']).Representation=None
        new=tmp_path/'no-mesh.ifc';model.write(str(new))
        item=app.save_ifc_identity_proposal('P',str(new),revision='R2',global_id=proposal['global_id'],floor_id='F1',member_id='B1',author='author',reference='Explicit no mesh revision',source_sha256=hashlib.sha256(new.read_bytes()).hexdigest(),expected_digest=app.store.current_digest('P'))
        app.review_ifc_identity('P',**{**args,'proposal_id':item['id'],'expected_digest':app.store.current_digest('P')},supersedes=proposal['id'])
        proposal=item;before=app.store.current_digest('P')
    with pytest.raises(ValueError):
        if invalid=='missing_revision':DeepIFCAdapter().read_display_contract(path,revision='')
        else:app.ifc_display_geometry('P',proposal['id'])
    assert app.store.current_digest('P')==before
    app.store.close()

@pytest.mark.parametrize('mode',['split','merge'])
def test_lineage_display_is_not_a_second_quantity_owner(tmp_path,mode):
    from test_phase2_priority5_complete import case
    app,args,ep,allocation=case(tmp_path,mode=mode)
    old=[x["proposal_id"] for x in allocation["previous"]]
    new=[x["proposal_id"] for x in allocation["current"]]
    before=app.store.current_digest('P')
    for proposal in old+new:
        result=app.ifc_display_geometry('P',proposal)
        assert result['financial_permission'] is False
        assert result['ownership_view']==('historical' if proposal in old else 'current')
    assert app.store.current_digest('P')==before
    assert sum(Decimal(str(row['quantity'])) for row in app.open_project('P')['boq'])==Decimal('6')
    app.store.close()


def test_existing_project_assistant_preserves_proposal_provenance(tmp_path):
    from core.ai.project_assistant import ProjectAssistant
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'app');app.create_project('Synthetic readonly QA','P')
    before=app.store.current_digest('P')
    result=ProjectAssistant().review(app.open_project('P'))
    assert result['provenance']['model_id']=='local-rule-engine-v1'
    assert result['requires_user_confirmation'] and not result['quantity_authority']
    assert app.store.current_digest('P')==before and app.open_project('P')['boq']==[]
    app.store.close()


def test_generator_asset_manifest_uses_actual_local_bytes(tmp_path):
    from core.ai.local_engine import LocalAIEngine
    # These bytes test hashing only; they are explicitly NOT a working GGUF.
    model=tmp_path/'hash-only.fixture';model.write_bytes(b'asset-hash-fixture')
    projector=tmp_path/'projector.fixture';projector.write_bytes(b'projector-hash-fixture')
    image=tmp_path/'source.fixture';image.write_bytes(b'source-hash-fixture')
    engine=LocalAIEngine(model_dir=tmp_path,model_path=model,edition='pro')
    engine.mmproj_path=projector
    result=engine._model_provenance({'revision':'R2'},image)
    assert result['model_sha256']==hashlib.sha256(model.read_bytes()).hexdigest()
    assert result['source_sha256']==hashlib.sha256(image.read_bytes()).hexdigest()
    assert result['projector_sha256']==hashlib.sha256(projector.read_bytes()).hexdigest()


def test_light_cannot_enable_local_ai_with_explicit_model_path(tmp_path):
    from core.ai.local_engine import LocalAIEngine
    asset=tmp_path/'hash-only.fixture';asset.write_bytes(b'not a model; no inference claimed')
    engine=LocalAIEngine(model_dir=tmp_path,model_path=asset,edition='light')
    assert not engine.has_llm_model
    assert engine.inspect_project({'name':'P','takeoffs':[]}).source=='fail-closed'
    assert engine.answer('بررسی پروژه').source=='fail-closed'


@pytest.mark.parametrize('edition',['light','standard','pro'])
def test_native_ai_page_truthful_readonly(tmp_path,edition):
    import os,sys,subprocess
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen',STRUCTURALPRO_EDITION=edition,PYTHONPATH=str(root))
    result=subprocess.run([sys.executable,str(root/'tests/phase2_priority6_ai_qt_probe.py'),str(tmp_path)],
                          cwd=root,env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    receipt=json.loads((tmp_path/'receipt.json').read_text())
    assert receipt['status']=='PASS' and receipt['boq_unchanged']
    assert (tmp_path/'ai-native.png').is_file()
