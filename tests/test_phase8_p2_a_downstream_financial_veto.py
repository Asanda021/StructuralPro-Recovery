"""Synthetic RED/GREEN checks for downstream finance and report sinks."""
import pytest
from core.takeoff.boq import boq_summary
from core.commercial.statement import statement_rows
from core.reports.aec_office_package import audit_boq


def row(**kw):
    r = {
        'source_id': 'synthetic', 'source_type': 'reviewed_manual',
        'price_code': '280101', 'item_code': '280101',
        'description': 'synthetic test only', 'quantity': '1',
        'unit': 'm3', 'unit_price': '100', 'total': '100',
        'factor': '1', 'status': 'active', 'source_ids': ['synthetic'],
    }
    r.update(kw)
    return r


@pytest.mark.parametrize('changes', [
    {'source_type': 'legacy_financial_audit'},
    {'status': 'BLOCKED_AMOUNT_CONFLICT'},
    {'source_document_audit': {'status': 'BLOCKED_AMOUNT_CONFLICT'}},
    {'financially_payable': False},
    {'status': 'AGREED_CANDIDATE'},
])
@pytest.mark.parametrize('sink', ['boq_summary', 'statement_rows', 'audit_boq'])
def test_document_evidence_never_reaches_downstream_financial_sink(changes, sink):
    r = row(**changes)
    with pytest.raises(ValueError):
        if sink == 'boq_summary':
            boq_summary([r])
        elif sink == 'statement_rows':
            statement_rows({'boq': [r]})
        else:
            audit_boq({'boq': [r], 'takeoffs': []})


def test_legitimate_boq_summary_unchanged():
    result = boq_summary([row()])
    assert result['grand_total'] == 100
    assert result['active_line_count'] == 1


def test_legitimate_statement_projection_unchanged():
    result = statement_rows({'boq': [row()]})
    assert len(result) == 1
    assert result[0]['price_code'] == '280101'


def test_financial_report_export_rejects_stored_document_row_before_file_write(tmp_path):
    from core.platform.application import StructuralProApp
    from types import SimpleNamespace
    app = object.__new__(StructuralProApp)
    bad = row(source_type='historical_document_audit')
    app.store = SimpleNamespace(get=lambda _id: {
        'id': 'synthetic', 'name': 'Synthetic', 'boq': [bad],
    })
    path = tmp_path / 'statement.xlsx'
    with pytest.raises(ValueError):
        app.report('synthetic', 'xlsx', path)
    assert not path.exists()


def test_document_marker_cannot_be_hidden_by_active_status():
    r = row(status='active', source_document_audit={'unverified': True})
    with pytest.raises(ValueError):
        boq_summary([r])


def test_nonfinancial_audit_report_retains_blocked_status_as_evidence():
    from core.reports.project_report import build_report
    report = build_report('synthetic audit', [{
        'description': 'Documentary conflict evidence',
        'status': 'BLOCKED_AMOUNT_CONFLICT',
        'quantity': '1', 'total': '100', 'source_id': 'synthetic',
    }])
    assert report.validate()['valid']
    assert report.rows[0]['status'] == 'BLOCKED_AMOUNT_CONFLICT'
