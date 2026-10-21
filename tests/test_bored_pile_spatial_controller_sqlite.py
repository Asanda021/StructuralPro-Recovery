"""Saved-version spatial audit wiring with real StructuralProApp and SQLite.

The spatial engine is replaced only in the wiring-positive unit test, so the
source-bound geometry calculations remain the engine suite's responsibility.
"""
from copy import deepcopy
from hashlib import sha256
import json
import sys
from types import ModuleType

import pytest

from app.bored_pile_draft_controller import PileDraftController
from core.platform.application import StructuralProApp
from test_bored_pile_joint_real_application import _saved_joint_case
from test_bored_pile_real_application_controller import _document, _setup


def _prepared(tmp_path):
    app, controller, data, compiled, owner, joint, original_project = _saved_joint_case(tmp_path)
    controller.attach_joint(_document(tmp_path/'joint.json', joint), reference='Synthetic independent joint')
    controller.save()
    return app, controller


def _spatial_file(tmp_path):
    return _document(tmp_path/'spatial.json', {
        'policy':'bored_pile_spatial_overlap_v1',
        'purpose':'synthetic evidence, no finance approval'})


def _patch_spatial(monkeypatch, handler):
    module = ModuleType('core.takeoff.bored_pile_spatial_overlap')
    module.audit_spatial_overlap = handler
    monkeypatch.setitem(sys.modules, module.__name__, module)


def test_spatial_audit_uses_saved_sqlite_snapshot_and_never_writes(tmp_path, monkeypatch):
    app, controller = _prepared(tmp_path)
    path = _spatial_file(tmp_path)
    before = deepcopy(app.open_project('P'))
    assert controller.dirty is False
    calls = []

    def spatial(input_doc, compiled, ownership, owner_sha, joint, snapshot,
                *, evidence_path, evidence_sha256):
        calls.append((input_doc,compiled,ownership,joint))
        assert snapshot == before
        assert compiled['source_sha256'] == joint['input_sha256']
        assert owner_sha == controller.data['pile_detail']['ownership_document']['sha256']
        assert evidence_path == path
        assert evidence_sha256 == sha256(open(path,'rb').read()).hexdigest()
        return {'status':'SPATIAL_PREVIEW_ONLY','matched_interfaces':[{'test':'synthetic'}],
                'ready_for_boq':False,'commit_allowed':False,'rows':[],
                'blockers':['پرداخت مسدود است']}
    _patch_spatial(monkeypatch, spatial)
    try:
        result = controller.audit_spatial(path)
        assert result['status']=='SPATIAL_PREVIEW_ONLY'
        assert len(calls)==1
        result['matched_interfaces'].clear()
        assert controller.dirty is False
        assert app.open_project('P') == before
        assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    finally:
        app.store.close()
    reopened = StructuralProApp(tmp_path/'db')
    try:
        again = PileDraftController(reopened,'P')
        again.load('FND','PG1')
        assert again.revision == controller.revision
        assert 'spatial_document' not in again.data['pile_detail']
        assert reopened.open_project('P')['boq'] == []
        assert reopened.open_project('P')['takeoffs'] == []
    finally:
        reopened.store.close()


@pytest.mark.parametrize('violation',['never_saved','dirty','stale_revision','stale_record','missing_joint','missing_owner'])
def test_audit_refuses_unsaved_stale_or_missing_dependencies(tmp_path,monkeypatch, violation):
    if violation == 'never_saved':
        app, controller, _ = _setup(tmp_path)
    else:
        app, controller = _prepared(tmp_path)
    path = _spatial_file(tmp_path)
    called=[]
    _patch_spatial(monkeypatch, lambda *args, **kwargs: called.append(True))
    try:
        if violation == 'dirty':
            controller.set_preflight(reviewer='Modified but not saved',ownership_reference='source')
        elif violation == 'stale_revision':
            peer=PileDraftController(app,'P')
            peer.load('FND','PG1')
            peer.set_preflight(reviewer='Changed in SQLite',ownership_reference='Updated')
            peer.save()
        elif violation == 'stale_record':
            controller.saved_data=deepcopy(controller.data)
            controller.data['pile_detail']['preflight']['reviewer']='Changed by caller'
            controller.saved_data=deepcopy(controller.data)
        elif violation == 'missing_joint':
            controller.data['pile_detail']['joint_document']={'path':'','sha256':'','reference':''}
            controller.saved_data=deepcopy(controller.data)
        elif violation == 'missing_owner':
            controller.data['pile_detail']['ownership_document']={'path':'','sha256':'','reference':''}
            controller.saved_data=deepcopy(controller.data)
        with pytest.raises(ValueError):
            controller.audit_spatial(path)
        assert not called
        assert app.open_project('P')['boq']==[]
    finally:
        app.store.close()


@pytest.mark.parametrize('violation',['owner_tampered','joint_tampered','not_json','duplicate_keys','float_json','missing_file'])
def test_audit_refuses_corrupt_source_or_evidence_before_geometry(tmp_path, monkeypatch, violation):
    app, controller = _prepared(tmp_path)
    path = _spatial_file(tmp_path)
    called=[]
    _patch_spatial(monkeypatch, lambda *args, **kwargs: called.append(True))
    try:
        if violation == 'owner_tampered':
            doc = controller.data['pile_detail']['ownership_document']['path']
            with open(doc,'ab') as f:f.write(b'\n')
        elif violation == 'joint_tampered':
            doc = controller.data['pile_detail']['joint_document']['path']
            with open(doc,'ab') as f:f.write(b'\n')
        elif violation == 'not_json':
            with open(path,'wb') as f:f.write(b'broken {')
        elif violation == 'duplicate_keys':
            with open(path,'wb') as f:f.write(b'{"a":1,"a":2}')
        elif violation == 'float_json':
            with open(path,'wb') as f:f.write(b'{"a":0.1}')
        else:
            path = str(tmp_path/'nonexistent.json')
        with pytest.raises(ValueError):controller.audit_spatial(path)
        assert called==[]
    finally:
        app.store.close()


@pytest.mark.parametrize('forgery',[
    {'status':'SPATIAL_PREVIEW_ONLY','ready_for_boq':True,'commit_allowed':False,'rows':[]},
    {'status':'SPATIAL_PREVIEW_ONLY','ready_for_boq':False,'commit_allowed':True,'rows':[]},
    {'status':'SPATIAL_PREVIEW_ONLY','ready_for_boq':False,'commit_allowed':False,'rows':[{'quantity':'1'}]},
    {'status':'VERIFIED_FOR_PAYMENT','ready_for_boq':False,'commit_allowed':False,'rows':[]},
])
def test_no_spatial_result_can_bypass_financial_gate(tmp_path,monkeypatch,forgery):
    app,controller=_prepared(tmp_path)
    _patch_spatial(monkeypatch,lambda *args, **kwargs:forgery)
    try:
        with pytest.raises(ValueError):controller.audit_spatial(_spatial_file(tmp_path))
        assert app.open_project('P')['boq']==[]
        assert app.open_project('P')['takeoffs']==[]
    finally:app.store.close()
