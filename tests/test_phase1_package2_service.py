"""Real service / SQLite acceptance for existing steel and prism engines."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest
from core.platform.application import StructuralProApp
from core.takeoff.building_six_family_ownership_chat import _digest
from test_phase1_steel_stair_support_crosswalk_chat import example,DRAWING
from test_phase1_work_six_family_service import setup as six_setup
from test_phase1_multi_member_overlap import two

STEEL='steel_stair_support_service_work_v1'
GEOMETRY='six_family_geometry_service_work_v1'

def evidence(folder,request,documents):
    source=folder/'service-request.json';source.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
    paths={}
    for h,raw in documents.items():
        p=folder/h;p.write_bytes(raw);paths[h]=str(p)
    return dict(source_path=str(source),source_sha256=sha256(source.read_bytes()).hexdigest(),evidence_files=paths)


def steel_case(tmp_path):
    d,s,p,files=example();a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P')
    current=a.open_project('P');current.update(p);a.store.save('P',current)
    request={'policy':STEEL,'project_id':'P','project_sha256':_digest(a.structural_handoff_basis('P')),
             'stair_document':s,'support_document':d}
    files[s['source']['sha256']]=DRAWING
    return a,request,evidence(tmp_path,request,files)


def geometry_case(tmp_path):
    a,owner,args=six_setup(tmp_path)
    project,geometry=two(tmp_path)
    # Use the exact real record keys/identities read by existing prism verifier.
    p=a.open_project('P-1');p['id']='P-1'
    for book,old,key,family in [('reviewed_structural_members','c','column:1','column'),('beam_detail_register','b','beam:1','beam')]:
        record=deepcopy(project[book][old]);data=record['data'];data['source']['source_id']='SYN:'+family
        data['physical_id']='MEMBER-'+family;data['geometry']['physical_id']='MEMBER-'+family
        pointer=data['geometry']['column_joint_prism_v1'];pointer['physical_id']='MEMBER-'+family
        path=Path(pointer['path']);doc=json.loads(path.read_text());doc['project_id']='P-1';doc['physical_id']='MEMBER-'+family
        path.write_text(json.dumps(doc));pointer['sha256']=sha256(path.read_bytes()).hexdigest()
        p[book][key]=record
        link=next(x for x in owner['links'] if x['family']==family)
        link.update(member_id=data.get('member_id',data.get('beam_id')),record_revision=record['revision'],record_sha256=_digest(record))
        g=next(x for x in geometry['links'] if x['kind']==('column' if family=='column' else 'beam'))
        g.update(physical_id='MEMBER-'+family,record_sha256=_digest(record))
    a.store.save('P-1',p);geometry['project_id']='P-1'
    owner['project_sha256']=_digest(a.structural_handoff_basis('P-1'))
    docs={h:Path(path).read_bytes() for h,path in args['evidence_files'].items()};hashes=[]
    for book,key in [('reviewed_structural_members','column:1'),('beam_detail_register','beam:1')]:
        pointer=p[book][key]['data']['geometry']['column_joint_prism_v1'];h=pointer['sha256'];docs[h]=Path(pointer['path']).read_bytes();hashes.append(h)
    request={'policy':GEOMETRY,'project_id':'P-1','project_sha256':owner['project_sha256'],
             'ownership_document':owner,'geometry_documents':[geometry],'geometry_source_hashes':hashes}
    return a,request,evidence(tmp_path,request,docs)


@pytest.mark.parametrize('kind',['steel','geometry'])
def test_persist_real_composite_audit_reopen_preserves_boq_and_locks(tmp_path,kind):
    a,d,args=steel_case(tmp_path) if kind=='steel' else geometry_case(tmp_path);pid=d['project_id'];before=deepcopy(a.open_project(pid))
    root=a.data_dir
    try:
        a.save_structural_handoff_draft(pid,'JOINT-AUDIT',d,expected_revision=0,**args)
        result=a.run_structural_handoff_audit(pid,'JOINT-AUDIT',expected_revision=1)['result']
        assert result['document_consistent'],result['blockers']
        assert not result['ready'] and not result['commit_allowed'] and result['payable_rows']==[]
        if kind=='geometry':
            assert result['geometry_reports'][0]['pair_intersections'][0]['envelope_intersection_m3']=='0.16'
            assert result['material_deduction_m3'] is None
        else:assert result['support']['support_evidence_checked'] and result['unverified_operations']
        assert a.open_project(pid)['boq']==before['boq'] and a.open_project(pid)['takeoffs']==before['takeoffs']
    finally:a.store.close()
    b=StructuralProApp(root)
    try:
        saved=b.get_structural_handoff_audit(pid,'JOINT-AUDIT');assert not saved['stale'] and saved['result']==result
        assert b.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
        snapshot='\n'.join(b.store.db.iterdump())
        with pytest.raises(ValueError):b.commit_structural_handoff_audit(pid,'JOINT-AUDIT',expected_revision=2)
        with pytest.raises(RuntimeError):b.run_structural_handoff_audit(pid,'JOINT-AUDIT',expected_revision=1)
        assert '\n'.join(b.store.db.iterdump())==snapshot
    finally:b.store.close()


@pytest.mark.parametrize('kind',['steel','geometry'])
@pytest.mark.parametrize('bad',['bytes','member_revision','payer'])
def test_bad_cross_member_evidence_cannot_change_boq(tmp_path,kind,bad):
    a,d,args=steel_case(tmp_path) if kind=='steel' else geometry_case(tmp_path);pid=d['project_id']
    try:
        if bad=='payer':
            if kind=='steel':d['stair_document']['ownership']['claims'][0]['payer_system']='OTHER'
            else:d['ownership_document']['claims'][0]['payer_source_id']='OTHER'
            Path(args['source_path']).write_text(json.dumps(d));args['source_sha256']=sha256(Path(args['source_path']).read_bytes()).hexdigest()
        a.save_structural_handoff_draft(pid,'X',d,expected_revision=0,**args)
        if bad=='bytes':Path(next(iter(args['evidence_files'].values()))).write_bytes(b'changed')
        if bad=='member_revision':
            p=a.open_project(pid);next(iter(p['reviewed_structural_members'].values()))['revision']+=1;a.store.save(pid,p)
        before='\n'.join(a.store.db.iterdump());boq=deepcopy(a.open_project(pid)['boq'])
        if bad=='payer':
            r=a.run_structural_handoff_audit(pid,'X',expected_revision=1)['result'];assert not r['document_consistent'] and r['payable_rows']==[]
        else:
            with pytest.raises((ValueError,RuntimeError)):a.run_structural_handoff_audit(pid,'X',expected_revision=1)
            assert '\n'.join(a.store.db.iterdump())==before
        assert a.open_project(pid)['boq']==boq
    finally:a.store.close()


def test_duplicate_geometry_pair_is_not_a_second_independent_audit(tmp_path):
    a,d,args=geometry_case(tmp_path)
    try:
        d['geometry_documents'].append(deepcopy(d['geometry_documents'][0]))
        args=evidence(tmp_path,d,{h:Path(p).read_bytes() for h,p in args['evidence_files'].items()})
        a.save_structural_handoff_draft('P-1','X',d,expected_revision=0,**args)
        r=a.run_structural_handoff_audit('P-1','X',expected_revision=1)['result']
        assert not r['document_consistent'] and r['payable_rows']==[]
    finally:a.store.close()


@pytest.mark.parametrize('kind',['steel','geometry'])
def test_composite_service_cas_rejects_actual_second_writer(tmp_path,monkeypatch,kind):
    a,d,args=steel_case(tmp_path) if kind=='steel' else geometry_case(tmp_path);pid=d['project_id']
    a.save_structural_handoff_draft(pid,'X',d,expected_revision=0,**args)
    b=StructuralProApp(a.data_dir);real=a.store.save;before=deepcopy(a.open_project(pid)['boq'])
    def other_writer(*v,**kw):
        p=b.open_project(pid);p['name']='نویسنده هم‌زمان';b.store.save(pid,p)
        return real(*v,**kw)
    monkeypatch.setattr(a.store,'save',other_writer)
    try:
        with pytest.raises(RuntimeError):a.run_structural_handoff_audit(pid,'X',expected_revision=1)
        p=b.open_project(pid);assert p['boq']==before and p['structural_handoff_audits']['X']['revision']==1
    finally:a.store.close();b.store.close()
