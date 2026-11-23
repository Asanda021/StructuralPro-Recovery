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

def test_period_summary_export_rejects_tainted_boq_before_template(tmp_path):
    from core.platform.application import StructuralProApp
    from types import SimpleNamespace
    from unittest.mock import patch
    app = object.__new__(StructuralProApp)
    project = {
        'id': 'synthetic', 'name': 'Synthetic',
        'boq': [row(source_type='legacy_financial_audit')],
    }
    app.store = SimpleNamespace(get=lambda _id: project)
    app.project_statement_summary = lambda _id: {'gross_current': '100'}
    app.statement_periods = lambda _id: [{
        'number': 1, 'gross_current': 100, 'retention': 0,
        'advance_recovery': 0, 'tax': 0, 'insurance': 0,
        'payable_current': 100, 'progress_percent': 1,
    }]
    with patch('core.reports.project_report.ProjectReport.export',
               return_value='EXPORTED') as exporter:
        with pytest.raises(ValueError):
            app.project_statement_report(
                'synthetic', 'csv', tmp_path / 'historical.csv')
    exporter.assert_not_called()


def test_verified_statement_pdf_export_rejects_unapproved_boq_before_report(tmp_path):
    from core.platform.application import StructuralProApp
    app = object.__new__(StructuralProApp)
    app.open_project = lambda _id: {
        'id': 'synthetic', 'name': 'Synthetic',
        'boq': [row(status='BLOCKED_AMOUNT_CONFLICT')],
    }
    app.project_statement_period = lambda _id, _period: (_ for _ in ()).throw(
        AssertionError('Period must not be accessed before BOQ veto'))
    with pytest.raises(ValueError):
        app.verified_statement_report(
            'synthetic', 1, 'pdf', tmp_path / 'statement.pdf')
