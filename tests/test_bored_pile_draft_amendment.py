"""Draft-only bored-pile amendment contract, with physical SQLite CAS.

The service simulates the existing application API; full StructuralProApp and Qt
acceptance remain separate. No BOQ or payment row may be created here.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from app.bored_pile_draft_controller import PileDraftController
from test_bored_pile_draft_controller import SqliteService, _setup, _json, domain_stubs


@pytest.fixture(autouse=True)
def use_isolated_domain_stubs(domain_stubs):
    pass


class JournalingSQLite(SqliteService):
    def __init__(self, path):
        super().__init__(path)
        self.journal = []

    def save_structural_member_draft(self, pid, data, *, expected_revision, reason='ثبت پیش‌نویس'):
        result = super().save_structural_member_draft(pid, data, expected_revision=expected_revision)
        self.journal.append((expected_revision + 1, reason))
        return result


def setup(tmp_path):
    c, base, data = _setup(tmp_path)
    base.close()
    service = JournalingSQLite(tmp_path / 'p.db')
    c.service = service
    c.save()
    return c, service, data


def amended(data):
    new = deepcopy(data)
    new['piles'][0]['interface']['approved_by'] = 'IndependentGeometryCorrection'
    return new


def test_amendment_real_sqlite_journal_and_invalidate_owner_and_joint(tmp_path):
    c, service, old = setup(tmp_path)
    c.data['pile_detail']['ownership_document'] = {'path':'owner.json','sha256':'a'*64,'reference':'owner'}
    c.data['pile_detail']['joint_document'] = {'path':'joint.json','sha256':'b'*64,'reference':'joint'}
    c.save()
    path = _json(tmp_path/'revised.json', amended(old))
    result = c.amend_input(path, reason='اصلاح دیتایل طبق نقشه بازنگری‌شده')
    assert result['pile_detail']['input'] == amended(old)
    assert c.revision == 3 and not c.dirty
    assert result['pile_detail']['ownership_document']['sha256'] == ''
    assert result['pile_detail']['joint_document']['sha256'] == ''
    assert service.journal[-1] == (3,'اصلاحیه پیش‌نویس شمع: اصلاح دیتایل طبق نقشه بازنگری‌شده')
    service.close()
    reopened = JournalingSQLite(tmp_path / 'p.db')
    peer = PileDraftController(reopened, 'P')
    assert peer.load('FND','PG1')['pile_detail']['input'] == amended(old)
    assert peer.revision == 3
    assert reopened.open_project('P')['boq'] == []
    reopened.close()


@pytest.mark.parametrize('kind', ['no_op','same_bytes','blank_reason','other_project',
                                   'other_source','other_datum','other_group',
                                   'changed_physical_id','added_pile'])
def test_invalid_amendment_does_not_modify_sqlite(tmp_path, kind):
    c, service, old = setup(tmp_path)
    source = amended(old)
    reason = 'مدرک اصلاحیه مصنوعی'
    if kind == 'no_op': source = deepcopy(old)
    if kind == 'same_bytes':
        path = Path(c.data['pile_detail']['input_document']['path'])
    else:
        if kind == 'other_project':source['project_id']='WRONG'
        if kind == 'other_source':source['source']['source_id']='ANOTHER'
        if kind == 'other_datum':source['datum']['axis_ref']='ANOTHER'
        if kind == 'other_group':source['group_id']='OTHER'
        if kind == 'changed_physical_id':source['piles'][0]['physical_id']='OTHER-PHYSICAL'
        if kind == 'added_pile':
            extra=deepcopy(source['piles'][0]);extra.update(id='BP2',physical_id='OTHER-PHYSICAL');source['piles'].append(extra)
        path=_json(tmp_path/'revised.json',source)
    if kind=='blank_reason':reason=' '
    before=deepcopy(c.data)
    with pytest.raises(ValueError):c.amend_input(path, reason=reason)
    assert c.data == before and c.revision == 1
    assert service.get_structural_member('P','bored_pile','FND','PG1')['revision'] == 1
    assert service.open_project('P')['boq'] == []
    service.close()


def test_stale_cas_amendment_rolls_back_controller_and_database(tmp_path):
    c, service, old = setup(tmp_path)
    other=PileDraftController(service,'P')
    other.load('FND','PG1')
    other.set_preflight(reviewer='PeerReviewer', ownership_reference='updated')
    other.save()
    assert other.revision == 2
    snapshot=deepcopy(c.data)
    with pytest.raises(RuntimeError):c.amend_input(_json(tmp_path/'new.json',amended(old)),reason='اصلاح مستند')
    assert c.revision==1 and c.data==snapshot and not c.dirty
    assert service.get_structural_member('P','bored_pile','FND','PG1')['revision']==2
    assert service.open_project('P')['boq']==[]
    service.close()


def test_changed_old_evidence_blocks_amendment(tmp_path):
    c, service, old = setup(tmp_path)
    original=Path(c.data['pile_detail']['input_document']['path'])
    original.write_bytes(original.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='مدرک قبلی'):
        c.amend_input(_json(tmp_path/'new.json',amended(old)),reason='اصلاح واقعی')
    assert c.revision==1 and not c.dirty
    service.close()


def test_reject_dirty_or_not_persisted(tmp_path):
    c, base, old = _setup(tmp_path)
    path=_json(tmp_path/'new.json',amended(old))
    with pytest.raises(ValueError,match='ذخیره‌شده'):c.amend_input(path,reason='علت')
    c.save()
    c.set_preflight(reviewer='NewReviewer',ownership_reference='changed')
    with pytest.raises(ValueError,match='ذخیره‌نشده'):c.amend_input(path,reason='علت')
    base.close()
