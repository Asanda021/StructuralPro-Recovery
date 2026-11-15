"""P8/P2-A: evidence crosswalk contract; synthetic only, no private source data."""
from core.drawings.pdf_excel_crosswalk import reconcile_pdf_excel


def pdf(**overrides):
    row = dict(member_id='C1', scope_id='F2', trade='structure', measure='volume',
               unit='m3', quantity='1.250', source_ref='synthetic-plan.pdf', page=3,
               revision='A')
    row.update(overrides)
    return row


def excel(**overrides):
    row = dict(member_id='C1', scope_id='F2', trade='structure', measure='volume',
               unit='m³', quantity='1.25', source_ref='synthetic-quantities.xlsx',
               sheet='Volumes', cell='F17', revision='A')
    row.update(overrides)
    return row


def test_agreement_is_candidate_not_financial_approval():
    r = reconcile_pdf_excel([pdf()], [excel()])
    assert r['summary'] == {'AGREED_CANDIDATE': 1}
    assert r['questions'] == []
    assert r['rows'][0]['approved'] is False
    assert r['approved_financial_rows'] == 0
    assert r['acceptance'] == 'NOT_VERIFIED'
    assert r['input_pairs_reconciled'] is True
    assert r['complete'] is False  # Pair agreement does not prove whole-project coverage.


def test_real_difference_has_excel_suggestion_but_cannot_pay():
    r = reconcile_pdf_excel([pdf(quantity='0.70')], [excel(quantity='10.70')])
    row = r['rows'][0]
    assert row['status'] == 'BLOCKED_QUANTITY_CONFLICT'
    assert row['suggestion']['quantity'] == '10.70'
    assert row['suggestion']['status'] == 'PROPOSED_UNVERIFIED'
    assert row['approved'] is False and row['financially_payable'] is False
    assert len(r['questions']) == 1
    assert r['questions'][0]['evidence'][1]['locator'] == 'Volumes!F17'


def test_no_false_match_on_same_quantity_different_floor():
    r = reconcile_pdf_excel([pdf()], [excel(scope_id='F3')])
    assert r['summary']['BLOCKED_MISSING_COUNTERPART'] == 2
    assert r['approved_financial_rows'] == 0


def test_no_false_match_on_distinct_member_or_measure():
    r = reconcile_pdf_excel([pdf()], [excel(member_id='C2')])
    assert len(r['questions']) == 2
    r = reconcile_pdf_excel([pdf()], [excel(measure='area')])
    assert len(r['questions']) == 2


def test_multiple_pdf_sources_not_double_counted():
    r = reconcile_pdf_excel([pdf(page=3), pdf(page=5)], [excel()])
    assert r['rows'][0]['status'] == 'BLOCKED_MULTIPLE_CANDIDATES'
    assert r['rows'][0]['suggestion'] is None


def test_conflicting_revisions_are_not_silently_equal():
    r = reconcile_pdf_excel([pdf()], [excel(revision='B')])
    assert r['rows'][0]['status'] == 'BLOCKED_REVISION_CONFLICT'


def test_ambiguous_excel_decimal_comma_blocked():
    r = reconcile_pdf_excel([pdf()], [excel(quantity='1,250')])
    assert r['invalid'][0]['status'] == 'BLOCKED_INVALID_EVIDENCE'
    assert 'separator' in r['invalid'][0]['reason']


def test_persian_digit_decimal_and_unit_normalization():
    r = reconcile_pdf_excel([pdf(quantity='۱٫۲۵۰', unit='متر مکعب')], [excel()])
    assert r['rows'][0]['status'] == 'AGREED_CANDIDATE'


def test_formula_disagreement_is_blocked_not_quietly_corrected():
    r = reconcile_pdf_excel([pdf()], [excel(factors=['2', '1'], deductions=['0.5'])])
    assert r['invalid'][0]['status'] == 'BLOCKED_INVALID_EVIDENCE'
    assert 'arithmetic' in r['invalid'][0]['reason']


def test_checked_arithmetic_can_corrobate_but_not_approve():
    r = reconcile_pdf_excel([pdf()], [excel(factors=['2.5', '0.5'])])
    assert r['rows'][0]['status'] == 'AGREED_CANDIDATE'
    assert r['rows'][0]['evidence'][1]['formula_checked'] is True
    assert r['approved_financial_rows'] == 0


def test_pdf_missing_page_and_excel_missing_cell_are_invalid():
    r = reconcile_pdf_excel([pdf(page=0)], [excel(cell='bad')])
    assert len(r['invalid']) == 2 and r['rows'] == []
    assert r['complete'] is False


def test_negative_nonfinite_and_bool_quantities_are_blocked():
    for v in ['NaN', 'Infinity', '-1', True, None]:
        r = reconcile_pdf_excel([pdf(quantity=v)], [excel()])
        assert r['invalid'][0]['status'] == 'BLOCKED_INVALID_EVIDENCE'


def test_missing_member_identity_does_not_fuzzy_join():
    r = reconcile_pdf_excel([pdf(member_id='')], [excel()])
    assert r['invalid'][0]['status'] == 'BLOCKED_INVALID_EVIDENCE'
    assert len(r['questions']) == 1


def test_no_input_does_not_report_complete():
    r = reconcile_pdf_excel([], [])
    assert r['complete'] is False and r['approved_financial_rows'] == 0


def test_mixed_batch_does_not_block_other_items():
    r = reconcile_pdf_excel([pdf(), pdf(member_id='D1', quantity='2')], [excel()])
    assert r['summary']['AGREED_CANDIDATE'] == 1
    assert r['summary']['BLOCKED_MISSING_COUNTERPART'] == 1