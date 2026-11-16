"""Bounded offline OCR read-only recovery: no real Tesseract in CI."""
import sys
from hashlib import sha256

import pytest

from core.drawings.pdf_rendered_text_recovery import (
    recover_page_rendered_type_words, should_recover_rendered_labels,
)


class FakeRenderedPage:
    rect = (0, 0, 600, 400)
    rotation = 0

    def __init__(self, words, *, failure=False):
        self.words = words
        self.failure = failure
        self.settings = None

    def get_textpage_ocr(self, **settings):
        self.settings = settings
        if self.failure:
            raise RuntimeError("missing local tessdata / OCR engine")
        return "fake-ocr-text-page"

    def get_text(self, kind, *, textpage=None):
        assert kind == "words" and textpage == "fake-ocr-text-page"
        return self.words


def word(token, bbox=(20, 30, 60, 45)):
    return (*bbox, token, 0, 0, 0)


def tsv(width, height, *rows):
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
    page = f"1\t1\t0\t0\t0\t0\t0\t0\t{width}\t{height}\t-1\t"
    return ("\n".join((header, page, *rows)) + "\n").encode("utf-8")


def test_ocr_brace_and_baseplate_are_provenanced_but_never_measured():
    page = FakeRenderedPage([word("BR.1"), word("BP1", (80, 60, 125, 75)),
                             word("B1", (140, 90, 165, 105)), word("BP", (170, 90, 200, 105))])
    out = recover_page_rendered_type_words(
        page, document_id="PDF003", page_number=18, language="eng+fas")
    assert page.settings == {"language": "eng+fas", "dpi": 240, "full": True}
    assert [x["type_tag"] for x in out["type_word_witnesses"]] == ["BR1", "BP1", "B1"]
    assert all(x["status"] == "OCR_TYPE_MARK_UNVERIFIED" for x in out["type_word_witnesses"])
    assert out["all_ocr_words_examined"]
    assert all(x["document_id"] == "PDF003" and x["page"] == 18
               and not x["financially_payable"] and not x["physical_member_verified"]
               for x in out["type_word_witnesses"])


def test_ocr_does_not_merge_split_tokens_or_duplicate_native_evidence():
    page = FakeRenderedPage([word("B"), word("1", (63, 30, 75, 45)),
                             word("BP1", (80, 60, 125, 75))])
    native = [{"type_tag": "BP1", "bbox_pt": [80, 60, 125, 75],
               "document_id": "PDF003", "page": 18}]
    out = recover_page_rendered_type_words(page, document_id="PDF003",
                                            page_number=18, native_witnesses=native)
    assert out["type_word_witness_count"] == 1
    assert out["type_word_witnesses"][0]["status"] == "OCR_DUPLICATE_NATIVE_TYPE_MARK"


@pytest.mark.parametrize("words,status", [
    ([word("BP1"), word("BR.1")], "BLOCKED_OCR_WORD_BUDGET"),
    ([word("BP1", (700, 15, 730, 30))], "BLOCKED_OCR_WORD_OUTSIDE_PAGE"),
    ([("corrupt",)], "BLOCKED_OCR_BAD_WORD_RECORD"),
])
def test_failed_ocr_does_not_publish_partial_witnesses(words, status):
    out = recover_page_rendered_type_words(
        FakeRenderedPage(words), document_id="PDF003", page_number=18,
        max_words=1 if status == "BLOCKED_OCR_WORD_BUDGET" else 30000)
    assert out["status"] == status
    assert out["type_word_witnesses"] == []
    assert not out["all_ocr_words_examined"]


def test_local_ocr_engine_failure_and_large_page_are_explicitly_blocked():
    failed = recover_page_rendered_type_words(
        FakeRenderedPage([], failure=True), document_id="PDF003", page_number=16)
    assert failed["status"] == "BLOCKED_OCR_ENGINE_OR_LANGUAGE_UNAVAILABLE"
    assert failed["type_word_witnesses"] == []
    large = recover_page_rendered_type_words(
        FakeRenderedPage([]), document_id="PDF003", page_number=16,
        max_pixels=100000)
    assert large["status"] == "BLOCKED_OCR_PIXEL_BUDGET"
    with pytest.raises(ValueError):
        recover_page_rendered_type_words(
            FakeRenderedPage([]), document_id="PDF003", page_number=16,
            language="eng; rm -rf /")


def test_dense_outlined_pdf_and_scanned_textless_pdf_need_recovery():
    assert should_recover_rendered_labels({
        "vector_path_count": 1251, "image_block_count": 0,
        "searchable_text_block_count": 7, "detail_title_anchors": [],
        "type_word_index": {"type_word_witness_count": 0},
    })
    assert should_recover_rendered_labels({
        "vector_path_count": 0, "image_block_count": 1,
        "searchable_text_block_count": 0,
    })
    assert not should_recover_rendered_labels({
        "vector_path_count": 3, "image_block_count": 0,
        "searchable_text_block_count": 15,
    })


def test_rendered_words_preserve_raw_text_and_never_resolve_ambiguous_glyphs():
    page = FakeRenderedPage([
        word(" (b–2), "), word("F−۳"), word("Ｔ－４"),
        word("Cl"), word("CI"), word("C-Ⅰ"), word("B"), word("3"),
    ])
    out = recover_page_rendered_type_words(page, document_id="PDF003", page_number=18)
    marks = out["type_word_witnesses"]
    assert [mark["type_tag"] for mark in marks] == ["B2", "F3", "T4", None, None, None]
    assert marks[0]["raw_token"] == " (b–2), "
    assert marks[0]["source_token"] == "b–2"
    assert marks[0]["normalized_tag"] == "B2"
    assert out["ambiguous_glyph_count"] == 3
    for mark in marks[3:]:
        assert mark["status"] == "AMBIGUOUS_GLYPH"
        assert mark["normalized_tag"] is None
        assert mark["glyph_interpretations"] == ["C1", "CI", "Cl"]
        assert not mark["quantity_approved"] and not mark["financially_payable"]


def test_incomplete_word_stream_cannot_publish_prior_candidates():
    out = recover_page_rendered_type_words(
        FakeRenderedPage([word("B1"), word("irrelevant", (700, 15, 730, 30))]),
        document_id="PDF003", page_number=18)
    assert out["status"] == "BLOCKED_OCR_WORD_OUTSIDE_PAGE"
    assert not out["all_ocr_words_examined"] and not out["type_word_witnesses"]


def test_legacy_word_stream_stops_at_budget_without_exhausting_generator():
    def over_budget():
        yield word("B1")
        yield word("B2")
        pytest.fail("word source was consumed past the maximum + 1")

    out = recover_page_rendered_type_words(
        FakeRenderedPage(over_budget()), document_id="PDF003", page_number=18, max_words=1,
    )
    assert out["status"] == "BLOCKED_OCR_WORD_BUDGET"
    assert not out["all_ocr_words_examined"] and not out["type_word_witnesses"]


def test_wrong_source_digest_blocks_rendering(monkeypatch):
    import pymupdf
    import core.drawings.pdf_rendered_text_recovery as recovery

    with pymupdf.open() as pdf:
        pdf.new_page(width=200, height=160)
        content = pdf.tobytes()
    monkeypatch.setattr(recovery, "_run_tesseract", lambda *a, **kw: pytest.fail("OCR was invoked"), raising=False)
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        out = recover_page_rendered_type_words(
            pdf[0], document_id="PDF003", page_number=1, source_sha256="0" * 64,
        )
    assert out["status"] == "BLOCKED_OCR_SOURCE_MISMATCH"
    assert not out["all_ocr_words_examined"] and not out["type_word_witnesses"]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_real_rotated_page_and_cropped_pixels_map_to_unrotated_points(rotation, monkeypatch):
    import pymupdf
    import core.drawings.pdf_rendered_text_recovery as recovery

    with pymupdf.open() as pdf:
        page = pdf.new_page(width=200, height=160)
        page.insert_text((35, 70), "B-3")
        page.set_rotation(rotation)
        content = pdf.tobytes()
    digest = sha256(content).hexdigest()

    def ocr(image_path, *, language, dpi, max_seconds, max_output_bytes):
        with image_path.open("rb") as file:
            assert file.readline() == b"P5\n"
            assert file.readline().split() == [b"200", b"125"]
        return tsv(200, 125, "5\t1\t1\t1\t1\t1\t25\t25\t20\t25\t90.000\tB-3")

    monkeypatch.setattr(recovery, "_run_tesseract", ocr, raising=False)
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        out = recover_page_rendered_type_words(
            pdf[0], document_id="PDF003", page_number=1, source_sha256=digest,
            language="eng", dpi=180, render_bbox_pt=(24, 40, 104, 90),
        )
        assert pdf[0].rotation == rotation
    assert out["source_sha256"] == digest
    assert out["render_bbox_pt"] == [24, 40, 104, 90]
    assert out["coverage_scope"] == "RENDERED_REGION_ONLY"
    assert out["all_ocr_words_examined"]
    mark, = out["type_word_witnesses"]
    assert mark["source_sha256"] == digest
    assert mark["coordinate_space"] == "unrotated_pdf_points"
    assert mark["type_tag"] == "B3" and mark["bbox_pt"] == [34, 50, 42, 60]


def test_explicit_quarter_turn_of_source_region_preserves_source_coordinates(monkeypatch):
    import pymupdf
    import core.drawings.pdf_rendered_text_recovery as recovery

    with pymupdf.open() as pdf:
        page = pdf.new_page(width=200, height=160)
        page.insert_text((35, 70), "C-2")
        page.set_rotation(180)
        content = pdf.tobytes()

    def ocr(image_path, **_settings):
        with image_path.open("rb") as file:
            assert file.readline() == b"P5\n"
            assert file.readline().split() == [b"125", b"200"]
        return tsv(125, 200, "5\t1\t1\t1\t1\t1\t75\t25\t25\t20\t90.000\tC-2")

    monkeypatch.setattr(recovery, "_run_tesseract", ocr)
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        out = recover_page_rendered_type_words(
            pdf[0], document_id="PDF003", page_number=1, language="eng", dpi=180,
            render_bbox_pt=(24, 40, 104, 90), render_rotation_degrees=90,
        )
    assert out["render_rotation_degrees"] == 90
    assert out["type_word_witnesses"][0]["bbox_pt"] == [34, 50, 42, 60]


@pytest.mark.parametrize("fault", ["missing_page_record", "wrong_extent", "truncated_last_record"])
def test_invalid_tsv_cannot_claim_a_complete_ocr_pass(fault, monkeypatch):
    import pymupdf
    import core.drawings.pdf_rendered_text_recovery as recovery

    with pymupdf.open() as pdf:
        pdf.new_page(width=200, height=160)
        content = pdf.tobytes()
    valid = tsv(500, 400, "5\t1\t1\t1\t1\t1\t25\t25\t20\t25\t90\tB-3")
    output = {
        "missing_page_record": valid.split(b"\n", 1)[0] + b"\n",
        "wrong_extent": valid.replace(b"\t500\t400\t", b"\t50\t400\t"),
        "truncated_last_record": valid + b"5\t1\t",
    }[fault]
    monkeypatch.setattr(recovery, "_run_tesseract", lambda *args, **kwargs: output)
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        out = recover_page_rendered_type_words(
            pdf[0], document_id="PDF003", page_number=1, language="eng", dpi=180,
        )
    assert out["status"] == "BLOCKED_OCR_BAD_WORD_RECORD"
    assert not out["all_ocr_words_examined"] and not out["type_word_witnesses"]


@pytest.mark.parametrize("fault, reason", [
    ("bytes", "BLOCKED_OCR_OUTPUT_BYTE_BUDGET"),
    ("timeout", "BLOCKED_OCR_TIMEOUT"),
    ("exit", "BLOCKED_OCR_ENGINE_OR_LANGUAGE_UNAVAILABLE"),
])
def test_local_output_is_bounded_without_retaining_partial_bytes(fault, reason, monkeypatch, tmp_path):
    import core.drawings.pdf_rendered_text_recovery as recovery

    command = {
        "bytes": "import sys, time; sys.stdout.buffer.write(b'a' * 4096); sys.stdout.flush(); time.sleep(2)",
        "timeout": "import time; time.sleep(5)",
        "exit": "raise SystemExit(4)",
    }[fault]
    actual_popen = recovery.subprocess.Popen

    def substitute(_command, **options):
        return actual_popen([sys.executable, "-c", command], **options)

    monkeypatch.setattr(recovery.subprocess, "Popen", substitute)
    with pytest.raises(recovery._OCRBlocked) as raised:
        recovery._run_tesseract(tmp_path / "synthetic.pgm", language="eng", dpi=180,
                                max_seconds=0.2 if fault == "timeout" else 5, max_output_bytes=1024)
    assert raised.value.reason == reason


def test_explicit_bilingual_ocr_never_silently_falls_back_to_english(monkeypatch, tmp_path):
    import core.drawings.pdf_rendered_text_recovery as recovery

    def list_installed(command, _deadline, _byte_limit):
        assert command == ["tesseract", "--list-langs"]
        return b"List of available languages in test folder (1):\neng\n"

    monkeypatch.setattr(recovery, "_bounded_process", list_installed)
    with pytest.raises(recovery._OCRBlocked) as raised:
        recovery._run_tesseract(tmp_path / "synthetic.pgm", language="eng+fas", dpi=180,
                                max_seconds=1, max_output_bytes=1024)
    assert raised.value.reason == "BLOCKED_OCR_ENGINE_OR_LANGUAGE_UNAVAILABLE"


def test_ocr_cad_outline_evidence_enters_graph_only_as_proposed(tmp_path, monkeypatch):
    import pymupdf
    import core.drawings.pdf_auto_intake as intake

    drawing=tmp_path/"cad-outlined-labels.pdf"
    with pymupdf.open() as pdf:
        page=pdf.new_page(width=600,height=400)
        page.draw_rect(pymupdf.Rect(20,20,110,110))
        pdf.save(drawing)

    monkeypatch.setattr(intake, "should_recover_rendered_labels", lambda _: True)

    def synthetic_ocr(page, *, document_id, page_number, native_witnesses, language, source_sha256):
        assert document_id=="PDF001" and page_number==1
        assert language=="eng"
        assert len(source_sha256) == 64
        assert native_witnesses==[]
        return {
            "document_id":document_id, "page":page_number,
            "status":"INDEXED_RENDERED_OCR_TYPE_CANDIDATES",
            "type_word_witness_count":1, "all_ocr_words_examined":True,
            "type_word_witnesses":[{
                "document_id":document_id, "page":page_number,
                "source_word_index":1,"source_token":"BP1",
                "witness_id":"PDF001:p1:ocrword000001", "type_tag":"BP1",
                "bbox_pt":[35,35,64,49],"status":"OCR_TYPE_MARK_UNVERIFIED",
                "source_quality":"RENDERED_OCR_NOT_VERIFIED",
                "financially_payable":False,"quantity_approved":False,
                "physical_member_verified":False,
            }],
        }
    monkeypatch.setattr(intake, "recover_page_rendered_type_words", synthetic_ocr)
    result=intake.inspect_pdf_sheet_set([drawing], rendered_ocr=True, ocr_language="eng")
    assert result["rendered_ocr_enabled"] is True
    assert result["rendered_ocr_candidate_count"]==1
    graph=result["detail_evidence_graph"]
    assert graph["quantity_approval_count"]==0
    assert graph["physical_member_count"] is None
    ocr_nodes=[n for n in graph["nodes"] if
               n.get("evidence_quality")=="RENDERED_OCR_NOT_VERIFIED"]
    assert len(ocr_nodes)==1
    assert ocr_nodes[0]["type_tag"]=="BP1"
    assert ocr_nodes[0]["family"]=="reinforcement_connection"
    assert any(i["reason_code"]=="RENDERED_OCR_TYPE_UNVERIFIED" for i in graph["issues"])
    assert all(n["financially_payable"] is False for n in ocr_nodes)
    assert not [n for n in graph["nodes"] if n["kind"]=="INSTANCE_CANDIDATE"]
    assert not [n for n in graph["nodes"] if n["kind"]=="TYPE_DEFINITION"]
    assert any(q["tag"].startswith("PDF_GRAPH_") for q in graph["review_questions"])


def test_ocr_ci_keeps_competing_readings_in_graph_without_geometry_or_member(tmp_path, monkeypatch):
    import pymupdf
    import core.drawings.pdf_auto_intake as intake

    source = tmp_path / "ambiguous-mark.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=250)
        page.draw_rect((20, 20, 90, 95))
        pdf.save(source)

    def recognized(page, *, document_id, page_number, source_sha256, **_options):
        return {
            "status": "INDEXED_RENDERED_OCR_TYPE_CANDIDATES", "type_word_witness_count": 1,
            "all_ocr_words_examined": True, "ambiguous_glyph_count": 1,
            "type_word_witnesses": [{
                "document_id": document_id, "page": page_number, "source_sha256": source_sha256,
                "source_word_index": 1, "source_token": "CI", "type_tag": None, "bbox_pt": [35, 35, 55, 48],
                "source_quality": "RENDERED_OCR_NOT_VERIFIED", "financially_payable": False,
                "status": "AMBIGUOUS_GLYPH", "glyph_interpretations": ["C1", "CI", "Cl"],
            }],
        }

    monkeypatch.setattr(intake, "should_recover_rendered_labels", lambda _: True)
    monkeypatch.setattr(intake, "recover_page_rendered_type_words", recognized)
    graph = intake.inspect_pdf_sheet_set([source], rendered_ocr=True, ocr_language="eng")["detail_evidence_graph"]
    evidence, = [n for n in graph["nodes"] if n.get("evidence_quality") == "AMBIGUOUS_GLYPH"]
    assert evidence["status"] == "BLOCKED" and evidence["type_tag"] is None
    assert evidence["anchors"][0]["glyph_interpretations"] == ["C1", "CI", "Cl"]
    assert all(e["source_id"] != evidence["node_id"] for e in graph["edges"])
    assert not [n for n in graph["nodes"] if n["kind"] == "INSTANCE_CANDIDATE"]
    assert graph["pages"][0]["rendered_ocr_ambiguous_glyph_count"] == 1
