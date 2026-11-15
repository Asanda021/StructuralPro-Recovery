"""Bounded offline OCR read-only recovery: no real Tesseract in CI."""
from types import SimpleNamespace
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
