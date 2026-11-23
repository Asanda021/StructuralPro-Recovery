"""Synthetic regressions of legacy price-code / financial document gates."""
from core.drawings.pdf_excel_crosswalk import reconcile_pdf_excel
from core.drawings.legacy_financial_document_gate import (
    audit_historical_financial_rows, audit_legacy_code_labels,
)


def pdf(**kw):
    d = dict(member_id='C1', scope_id='F1', trade='steel', measure='weight',
             unit='kg', quantity='1', source_ref='synthetic.pdf', page=3,
             revision='A')
    d.update(kw)
    return d


def excel(**kw):
    d = dict(member_id='C1', scope_id='F1', trade='steel', measure='weight',
             unit='kg', quantity='1', source_ref='synthetic.xls', sheet='Test',
             cell='C2', revision='A')
    d.update(kw)
    return d


def test_code_conflict_blocks_even_if_physical_quantity_matches():
    out = reconcile_pdf_excel([pdf(item_code='040101')], [excel(item_code='050101')])
    assert out['rows'][0]['status'] == 'BLOCKED_SOURCE_CODE_CONFLICT'
    assert out['approved_financial_rows'] == 0


def test_source_item_code_missing_on_counterpart_blocks():
    out = reconcile_pdf_excel([pdf(price_code='040101')], [excel()])
    assert out['rows'][0]['status'] == 'BLOCKED_SOURCE_CODE_CONFLICT'


def test_matching_codes_are_candidates_not_approved():
    out = reconcile_pdf_excel([pdf(price_code='۰۴۰۱۰۱')], [excel(item_code='040101')])
    assert out['rows'][0]['status'] == 'AGREED_CANDIDATE'
    assert out['rows'][0]['approved'] is False


def test_alias_conflict_inside_one_source_is_invalid_evidence():
    out = reconcile_pdf_excel(
        [pdf(price_code='040101', item_code='050101')], [excel()]
    )
    assert out['invalid'][0]['status'] == 'BLOCKED_INVALID_EVIDENCE'


def test_duplicate_source_codes_cannot_be_implicitly_matched():
    rows = [
        {'code': '040101', 'pdf_amount': '100', 'excel_amount': '100',
         'pdf_locator': 'p7:1', 'excel_locator': 's!A10'},
        {'code': '040101', 'pdf_amount': '300', 'excel_amount': '300',
         'pdf_locator': 'p7:2', 'excel_locator': 's!A15'},
        {'code': '280101', 'pdf_amount': '1649890', 'excel_amount': '1585760',
         'pdf_locator': 'p20:1', 'excel_locator': 's!A12'},
        {'code': '020103', 'pdf_amount': '100', 'excel_amount': '100',
         'pdf_locator': 'p6:1', 'excel_locator': 's!A1'},
    ]
    audit = audit_historical_financial_rows(rows)
    assert audit['summary'] == {
        'BLOCKED_AMOUNT_CONFLICT': 1,
        'BLOCKED_DUPLICATE_SOURCE_CODE': 2,
        'MATCHED_DOCUMENT_AMOUNT_ONLY': 1,
    }
    assert audit['approved_financial_rows'] == 0
    assert all(not row['financially_payable'] for row in audit['rows'])


def test_missing_locator_fails_closed():
    out = audit_historical_financial_rows([
        {'code': '020103', 'pdf_amount': '1', 'excel_amount': '1',
         'pdf_locator': '', 'excel_locator': 's!A1'}
    ])
    assert out['summary']['BLOCKED_INVALID_EVIDENCE'] == 1


def test_chapter_label_is_display_candidate_only():
    out = audit_legacy_code_labels([
        {'kind': 'code', 'declared': '008310', 'context_code': '080310',
         'source_locator': 'metre!G19'},
        {'kind': 'chapter', 'declared': '25', 'context_chapter': '28',
         'source_locator': 'financial-p20'},
    ])
    assert out['summary']['BLOCKED_SOURCE_CODE_CONFLICT'] == 1
    assert out['summary']['PRESENTATION_LABEL_CORRECTION_CANDIDATE'] == 1
    assert out['approved_code_remappings'] == 0


def test_invalid_amounts_never_become_document_matches():
    for value in [True, -2, float('nan'), '1,000']:
        out = audit_historical_financial_rows([
            {'code': '020103', 'pdf_amount': value, 'excel_amount': '1',
             'pdf_locator': 'p6', 'excel_locator': 's!A1'}
        ])
        assert out['summary']['BLOCKED_INVALID_EVIDENCE'] == 1
