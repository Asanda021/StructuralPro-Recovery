"""Real StructuralProApp/SQLite read-only v2 source schedule roundtrip.

The sample intentionally has no starter bars; distinct bar-positive v2 behavior
is covered by test_bored_pile_starter_source_v2 with receiving-member records.
"""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from app.bored_pile_draft_controller import PileDraftController
from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_joint_crosswalk import SOURCE_BAR_POLICY
from core.takeoff.bored_pile_starter_source import SCHEMA
from test_bored_pile_joint_real_application import _saved_joint_case
from test_bored_pile_real_application_controller import _document


def _prepare(tmp_path):
    case = _saved_joint_case(tmp_path)
    app,controller,data,compiled,owner,joint,snapshot=case
    schedule = dict(schema=SCHEMA,project_id=data['project_id'],floor_id=data['floor_id'],
                    group_id=data['group_id'],input_sha256=compiled['source_sha256'],
                    coordinate_ref=data['datum']['coordinate_ref'],
                    vertical_datum_ref=data['datum']['vertical_datum_ref'],
                    prepared_by='ScheduleAuthor',reviewer='ScheduleReviewer',series=[])
    path=tmp_path/'real-source-empty.json'
    raw=json.dumps(schedule,ensure_ascii=False).encode('utf-8')
    path.write_bytes(raw)
    j=deepcopy(joint)
    j['policy']=SOURCE_BAR_POLICY
    j['starter_source_document']={'path':str(path),'sha256':sha256(raw).hexdigest(),
                                  'reference':'واقعی؛ فهرست صریح خالی میلگرد انتظار'}
    joint_path=_document(tmp_path/'joint-v2.json',j)
    return app,controller,path,joint_path


def test_real_controller_attach_save_reopen_v2_preserves_blocked_money(tmp_path):
    app,controller,source_path,joint_path=_prepare(tmp_path)
    try:
        audit=controller.attach_joint(joint_path,reference='مدرک بررسی مشترک')
        assert audit['source_identity_verified'] is True
        assert audit['matched_starter_pieces']==0
        assert not audit['commit_allowed'] and not audit['ready_for_boq'] and audit['rows']==[]
        controller.save()
        assert controller.revision>=1
        app.store.close()
        reopened=StructuralProApp(tmp_path/'db')
        try:
            after=PileDraftController(reopened,'P')
            after.load('FND','PG1')
            preview=after.preview()
            assert preview['joint_audit']['source_identity_verified'] is True
            assert preview['joint_audit']['source_identity_document_sha256']==sha256(source_path.read_bytes()).hexdigest()
            assert not preview['commit_allowed'] and preview['rows']==[]
            assert reopened.open_project('P')['boq']==[] and reopened.open_project('P')['takeoffs']==[]
            assert reopened.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
        finally:
            reopened.store.close()
    finally:
        try:app.store.close()
        except Exception:pass


def test_tampered_source_file_after_save_revokes_readonly_joint_audit(tmp_path):
    app,controller,source_path,joint_path=_prepare(tmp_path)
    try:
        controller.attach_joint(joint_path,reference='مدرک بررسی مشترک')
        controller.save()
        source_path.write_bytes(source_path.read_bytes()+b' ')
        preview=controller.preview()
        assert preview['joint_audit'] is None
        assert not preview['ready'] and not preview['commit_allowed'] and preview['rows']==[]
        assert any('تطبیق' in blocker for blocker in preview['blockers'])
        assert app.open_project('P')['boq']==[] and app.open_project('P')['takeoffs']==[]
    finally:
        app.store.close()
