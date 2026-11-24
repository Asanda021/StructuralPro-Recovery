"""Synthetic PDF source tests, no private engineering files in public test suite."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import pytest
import pymupdf
from core.drawings.pdf_private_19sheet_replay import preflight_pdf, run_private_replay, verify_engine_result


def _fake_pdf(tmp_path, count=19):
    src = tmp_path / 'fake.pdf'
    with pymupdf.open() as doc:
        for i in range(count):
            page = doc.new_page(width=420, height=297)
            page.insert_text((20, 40), 'PLAN SHEET ' + str(i + 1))
            page.draw_line((20, 100), (200, 100))
        doc.save(src)
    return src, sha256(src.read_bytes()).hexdigest()


def _report(digest, count=19):
    return {'documents': [{'sha256': digest, 'page_count': count, 'document_id':'PDF001', 'source_name':'fake.pdf'}], 'page_count': count,
            'quantity_approval_count': 0, 'detail_evidence_graph': {
                'graph_sha256': 'a' * 64, 'pages': [{'document_id':'PDF001','page':i+1} for i in range(count)],
                'acceptance': 'PARTIAL_NO_GO', 'complete': False,
                'quantity_approval_count': 0, 'fully_evidenced_member_count': 0,
                'beam_profile_reviews': [], 'beam_end_support_reviews': [],
                'occurrence_reviews': [], 'nodes': [], 'edges': [], 'issues': []}}


def test_original_pages_are_read_exactly_and_without_quantities(tmp_path):
    path, digest = _fake_pdf(tmp_path)
    receipt = preflight_pdf(path, digest)
    assert receipt['page_count'] == 19
    assert len(receipt['pages']) == 19
    assert receipt['native_words'] == 19 * 3
    assert receipt['vector_drawings'] == 19
    assert receipt['source_status'] == 'INDEPENDENT_SOURCE_PREFLIGHT_ONLY'
    assert receipt['quantity_approval_count'] == 0
    assert receipt['financially_payable'] is False


def test_wrong_digest_or_wrong_sheet_count_fails_before_engine(tmp_path):
    path, digest = _fake_pdf(tmp_path)
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        preflight_pdf(path, 'b' * 64)
    path, digest = _fake_pdf(tmp_path, 18)
    with pytest.raises(ValueError, match='Expected 19'):
        preflight_pdf(path, digest)


def test_engine_replay_with_identity_and_no_financial_rows(tmp_path):
    path, digest = _fake_pdf(tmp_path)
    kwargs = []
    def fake_inspect(paths, **options):
        kwargs.append((paths, options))
        return _report(digest)
    result = run_private_replay(path, digest, inspect=fake_inspect)
    assert result['engine_status'] == 'COMPLETE_READONLY_REPLAY_NONFINANCIAL'
    assert result['engine_page_count'] == 19
    assert result['acceptance'] == 'PARTIAL_NO_GO'
    assert kwargs[0][1]['rendered_ocr'] is False
    assert kwargs[0][1]['max_pages'] == 19


def test_preflight_only_cannot_claim_full_engine_run(tmp_path):
    path, digest = _fake_pdf(tmp_path)
    result = run_private_replay(path, digest)
    assert result['engine_status'] == 'NOT_RUN_ENGINE_UNAVAILABLE'
    assert 'graph_sha256' not in result


@pytest.mark.parametrize('alter', [
    lambda r: r['documents'][0].update(sha256='b' * 64),
    lambda r: r.update(page_count=18),
    lambda r: r['detail_evidence_graph'].update(pages=[{}] * 18),
    lambda r: r['detail_evidence_graph'].update(complete=True),
    lambda r: r['detail_evidence_graph'].update(acceptance='GO'),
    lambda r: r['detail_evidence_graph'].update(quantity_approval_count=1),
    lambda r: r['detail_evidence_graph'].update(graph_sha256='unverified'),
    lambda r: r.update(quantity_approval_count=1),
    lambda r: r['detail_evidence_graph']['pages'][1].update(page=1),
    lambda r: r['detail_evidence_graph']['edges'].append({'financially_payable':True}),
    lambda r: r['documents'][0].update(source_name='foreign.pdf'),
    lambda r: r['detail_evidence_graph']['beam_profile_reviews'].append({'financially_payable':True}),
    lambda r: r['detail_evidence_graph']['beam_end_support_reviews'].append({'financially_payable':False,'physical_member_verified':True}),
    lambda r: r['detail_evidence_graph']['occurrence_reviews'].append({'financially_payable':False,'quantity_approved':True}),
])
def test_unsafe_engine_result_never_receives_valid_receipt(tmp_path, alter):
    path, digest = _fake_pdf(tmp_path)
    preliminary = preflight_pdf(path, digest)
    report = _report(digest)
    alter(report)
    with pytest.raises(ValueError):
        verify_engine_result(report, preliminary)


def test_partial_beam_review_receipt_is_not_full_replay(tmp_path):
    path, digest = _fake_pdf(tmp_path)
    preliminary = preflight_pdf(path, digest)
    report = _report(digest)
    with pytest.raises(ValueError, match='Beam witness coverage'):
        verify_engine_result(report, preliminary, expected_beam_witnesses=12)


def test_duplicate_or_oversize_or_wrong_witness_json_is_rejected(tmp_path):
    path, digest = _fake_pdf(tmp_path)
    profile = tmp_path / 'input.json'
    profile.write_text(json.dumps({'bad': 'root'}), encoding='utf-8')
    with pytest.raises(ValueError, match='wrong JSON root'):
        run_private_replay(path, digest, profile_json=str(profile), inspect=lambda *a,**k: _report(digest))
    profile.write_bytes(b' ' * (128 * 1024 + 1))
    with pytest.raises(ValueError, match='exceeds'):
        run_private_replay(path, digest, profile_json=str(profile), inspect=lambda *a,**k: _report(digest))


def test_detail_provenance_requires_axis_and_beam_inputs(tmp_path):
    path, digest = _fake_pdf(tmp_path)
    detail = tmp_path / 'detail.json'
    detail.write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError, match='requires beam profile and axis'):
        run_private_replay(path, digest, detail_json=str(detail), inspect=lambda *a, **k: _report(digest))