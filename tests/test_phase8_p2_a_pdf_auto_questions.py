"""Question responses for PDF are not approvals of money or geometry."""
import json
import pytest
from core.drawings.pdf_auto_questions import PDFQuestionDecisionLedger


def report(suggestion=None, digest='a'*64):
    return dict(documents=[{'document_id':'PDF001','sha256':digest}], questions=[
        {'tag':'C1','question':'Which detail governs?', 'suggestion':suggestion,
         'evidence':[{'document_id':'PDF001','page':1}]}])


def test_record_document_request_without_proposed_value():
    s=PDFQuestionDecisionLedger(report())
    row=s.answer('C1','request_document')
    assert row['status']=='REVIEW_ANSWER_RECORDED_NOT_ENGINEERING_APPROVED'
    assert row['financially_payable'] is False
    assert json.loads(s.export_json())['financial_approvals']==0


def test_cannot_confirm_missing_or_unverified_suggestion():
    s=PDFQuestionDecisionLedger(report({'status':'PROPOSED_UNVERIFIED','value':None}))
    with pytest.raises(ValueError):s.answer('C1','confirm_suggestion')
    s=PDFQuestionDecisionLedger(report({'status':'FAKE_APPROVED','value':'5'}))
    with pytest.raises(ValueError):s.answer('C1','confirm_suggestion')


def test_confirm_documented_suggestion_is_still_preliminary():
    s=PDFQuestionDecisionLedger(report({'status':'PROPOSED_UNVERIFIED','value':'10.70'}))
    row=s.answer('C1','confirm_suggestion',reviewer='Operator')
    assert row['answer']=='10.70'
    assert row['status'].startswith('REVIEW_ANSWER')
    assert row['financially_payable'] is False


def test_correction_requires_explicit_response():
    s=PDFQuestionDecisionLedger(report())
    with pytest.raises(ValueError):s.answer('C1','correct',value='   ')
    assert s.answer('C1','correct',value=' 14.00 m ')['answer']=='14.00 m'


def test_changed_pdf_digest_invalidates_preliminary_answers():
    s=PDFQuestionDecisionLedger(report())
    s.answer('C1','request_document')
    assert not s.reconcile_sources(report(digest='b'*64))
    assert s.answers=={}


def test_duplicate_question_tags_are_bad_but_unknown_answers_rejected():
    s=PDFQuestionDecisionLedger(report())
    with pytest.raises(KeyError):s.answer('C2','request_document')
    with pytest.raises(ValueError):s.answer('C1','approve_finance')


def test_missing_source_identity_rejected():
    r=report();r['documents']=[{'document_id':'PDF001'}]
    with pytest.raises(ValueError):PDFQuestionDecisionLedger(r)