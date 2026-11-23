"""Synthetic final BOQ sink vetoes for unapproved P2-A documentary evidence."""
import pytest

from core.takeoff.boq import build_boq


def work_row(**changes):
    row = dict(source='reviewed-manual-1', source_id='reviewed-manual-1',
               source_type='takeoff', description='reviewed synthetic concrete',
               item_code='020103', price_code='020103', quantity='1.25',
               unit='m3', unit_price='500', status='active')
    row.update(changes)
    return row


@pytest.mark.parametrize('status', [
    'AGREED_CANDIDATE', 'MATCHED_DOCUMENT_AMOUNT_ONLY',
    'BLOCKED_AMOUNT_CONFLICT', 'BLOCKED_DUPLICATE_SOURCE_CODE',
    'BLOCKED_SOURCE_CODE_CONFLICT', 'BLOCKED_REVISION_CONFLICT',
    'QUANTITY_CANDIDATE', 'GEOMETRY_ONLY', 'PROPOSED_UNVERIFIED',
    'ACCEPTED_WITH_EXCEPTIONS', 'ENGINEERING_APPROVAL_REQUIRED',
])
def test_final_boq_rejects_document_only_statuses(status):
    with pytest.raises(ValueError):
        build_boq([work_row(status=status)])


@pytest.mark.parametrize('origin', [
    'pdf_excel_crosswalk', 'historical_document_audit',
    'legacy_financial_audit', 'pdf_quantity_preview',
])
def test_final_boq_rejects_document_source_origin(origin):
    with pytest.raises(ValueError):
        build_boq([work_row(source_type=origin)])


@pytest.mark.parametrize('marker', [
    'source_document_audit', 'pdf_excel_reconciliation',
    'legacy_financial_audit', 'quantity_evidence_preview',
])
def test_final_boq_rejects_audit_marker_even_with_active_status(marker):
    with pytest.raises(ValueError):
        build_boq([work_row(**{marker: {'status': 'MATCHED_DOCUMENT_AMOUNT_ONLY'}})])


def test_final_boq_rejects_explicit_nonpayable_marker():
    with pytest.raises(ValueError):
        build_boq([work_row(financially_payable=False)])


def test_final_boq_accepts_legacy_valid_synthetic_row():
    out = build_boq([work_row()])
    assert len(out) == 1
    assert out[0]['item_code'] == '020103'
    assert out[0]['total'] is not None


def test_final_boq_rejects_mixed_batch_atomically():
    with pytest.raises(ValueError):
        build_boq([work_row(), work_row(source_id='unverified-2',
                 status='BLOCKED_AMOUNT_CONFLICT')])


def sample_takeoff(**changes):
    t = {'source_id': 'synthetic-source-1', 'domain': 'drawing',
         'quantities': [{'code': '020103', 'title': 'concrete', 'unit': 'm3',
                         'amount': 1.25, 'status': 'active'}]}
    t.update(changes)
    return t


def test_rebuild_boq_rejects_takeoff_with_document_audit_marker():
    from core.takeoff.commit_guards import rebuild_project_boq
    with pytest.raises(ValueError):
        rebuild_project_boq({'takeoffs': [], 'boq': []},
                            [sample_takeoff(source_document_audit={'approved': False})])


def test_rebuild_boq_rejects_quantity_with_unverified_document_state():
    from core.takeoff.commit_guards import rebuild_project_boq
    t = sample_takeoff()
    t['quantities'][0]['status'] = 'MATCHED_DOCUMENT_AMOUNT_ONLY'
    with pytest.raises(ValueError):
        rebuild_project_boq({'takeoffs': [], 'boq': []}, [t])


def test_rebuild_boq_preserves_reviewed_legacy_positive_control():
    from core.takeoff.commit_guards import rebuild_project_boq
    takeoffs, boq = rebuild_project_boq({'takeoffs': [], 'boq': []}, [sample_takeoff()])
    assert len(takeoffs) == len(boq) == 1
    assert boq[0]['source_id'] == 'synthetic-source-1'


def test_validate_commit_rows_rejects_document_audit_marker():
    from core.takeoff.commit_guards import validate_commit_rows
    t = sample_takeoff()
    t['quantities'][0]['status'] = 'BLOCKED_SOURCE_CODE_CONFLICT'
    with pytest.raises(ValueError):
        validate_commit_rows({'takeoffs': []}, [t], source_id='synthetic-source-1')
