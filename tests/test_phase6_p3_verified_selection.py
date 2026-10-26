"""Phase 6 P3 first independent slice: explicit reviewed cross-view identities."""
from copy import deepcopy
import pytest

from core.drawings.verified_selection import VerifiedSelectionCrosswalk


SHA = 'a' * 64


def record(*, member='M-1', boq='B-01', global_id='G-1',
           shape='shape-3d-1'):
    return {
        'project_id': 'P-1', 'source_sha256': SHA, 'revision': 'R1',
        'global_id': global_id, 'member_id': member,
        'shape_id': shape, 'boq_row_id': boq,
        'evidence_ref': 'manual-review-1', 'reviewer_id': 'engineer-1',
        'review_status': 'approved',
    }


def make_index(links=None):
    return VerifiedSelectionCrosswalk(
        project_id='P-1', source_sha256=SHA, revision='R1',
        real_global_ids={'G-1','G-2'},
        real_member_ids={'M-1', 'M-2'},
        real_boq_row_ids={'B-01','B-02'},
        approved_records=[record()] if links is None else links,
        trusted_review_pairs=frozenset({('manual-review-1', 'engineer-1')}))


@pytest.mark.parametrize('origin,identifier', [
    ('2d','G-1'),('3d','G-1'),('tree','M-1'),('boq','B-01')])
def test_four_valid_selections_share_same_explicit_evidence(origin, identifier):
    index = make_index()
    result = index.resolve(origin=origin, identifier=identifier,
                           project_id='P-1', source_sha256=SHA, revision='R1')
    assert result.status == 'linked'
    assert result.global_ids == ('G-1',)
    assert result.member_ids == ('M-1',)
    assert result.boq_row_ids == ('B-01',)
    assert result.shape_ids == ('shape-3d-1',)


def test_many_members_to_one_boq_row_are_kept_distinct_not_counted(tmp_path):
    links = [record(), record(member='M-2', global_id='G-2', shape='shape-3d-2')]
    frozen = deepcopy(links)
    index = make_index(links)
    result = index.resolve(origin='boq', identifier='B-01', project_id='P-1',
                           source_sha256=SHA, revision='R1')
    assert result.global_ids == ('G-1', 'G-2')
    assert result.member_ids == ('M-1', 'M-2')
    assert links == frozen
    # This navigation API neither computes quantities nor accesses SQLite.
    assert 'quantity' not in result.__dict__


def test_unsupported_or_missing_mapping_never_guesses_identity():
    index = make_index()
    for origin, identifier, expected in [
        ('boq', 'B-02', 'unlinked'),
        ('tree', 'M-2', 'unlinked'),
        ('2d', 'G-2', 'unlinked'),
        ('boq', 'UNKNOWN', 'unverified')]:
        result = index.resolve(origin=origin, identifier=identifier,
                               project_id='P-1', source_sha256=SHA, revision='R1')
        assert result.status == expected
        assert result.boq_row_ids == ()
        assert result.global_ids == ()


@pytest.mark.parametrize('field,value', [
    ('project_id','other'),
    ('source_sha256','b'*64),
    ('revision','R2'),
    ('review_status','draft'),
    ('reviewer_id',''),
    ('evidence_ref',''),
    ('global_id','UNKNOWN'),
    ('member_id','UNKNOWN'),
    ('boq_row_id','UNKNOWN'),
])
def test_malformed_or_unreviewed_explicit_links_fail_closed(field, value):
    link = record()
    link[field] = value
    with pytest.raises(ValueError):
        make_index([link])


@pytest.mark.parametrize('field,value', [
    ('project_id','other'),('source_sha256','b'*64),('revision','R2')
])
def test_selection_refuses_stale_project_source_and_revision(field,value):
    index = make_index()
    params={'origin':'boq','identifier':'B-01',
            'project_id':'P-1','source_sha256':SHA,'revision':'R1'}
    params[field] = value
    with pytest.raises(ValueError, match='تغییر'):
        index.resolve(**params)


def test_no_confusion_between_strings_from_different_id_namespaces():
    index = make_index()
    assert index.resolve(origin='boq', identifier='M-1',
                         project_id='P-1', source_sha256=SHA,
                         revision='R1').status == 'unverified'
    assert index.resolve(origin='tree', identifier='B-01',
                         project_id='P-1', source_sha256=SHA,
                         revision='R1').status == 'unverified'


def test_duplicate_approved_link_rejected():
    same = record()
    with pytest.raises(ValueError, match='تکراری'):
        make_index([same, dict(same)])


def test_ifc_selection_does_not_suggest_unapproved_boq_links():
    no_boq = record(boq=None)
    index = make_index([no_boq])
    source = index.resolve(origin='3d',identifier='G-1',
                           project_id='P-1',source_sha256=SHA, revision='R1')
    assert source.status == 'linked'
    assert source.boq_row_ids == ()


def test_self_declared_approved_link_requires_independent_review_registry():
    from core.drawings.verified_selection import VerifiedSelectionCrosswalk
    with pytest.raises(ValueError, match='تأیید'):
        VerifiedSelectionCrosswalk(
            project_id='P-1', source_sha256=SHA, revision='R1',
            real_global_ids={'G-1'}, real_member_ids={'M-1'},
            real_boq_row_ids={'B-01'}, approved_records=[record()],
            trusted_review_pairs=frozenset({('forged-other-evidence','another-reviewer')}))
