"""Optional offline OCR witnesses for CAD-outlined PDF text (P8/P2-A).

Use ONLY when explicitly requested for dense vector/raster pages. PyMuPDF
renders the original page and delegates OCR to local Tesseract language data.
Recognition is intrinsically fallible: outputs are read-only visual
hypotheses, never trusted drawing declarations, certified detail references,
approved physical instances, or BOQ quantities. The source PDF never changes.
"""
from __future__ import annotations

from math import ceil, isfinite
import re

from core.drawings.pdf_type_word_witness import (
    TYPE_MARK, _box, _overlap, unrotated_page_bounds,
)

_ALLOWED_LANGUAGES = {"eng", "fas", "eng+fas", "fas+eng"}
_TERMINAL_PUNCTUATION = ",;:()[]{}"


def should_recover_rendered_labels(inventory: dict) -> bool:
    """Target probable outlined-text plans and textless scanned sheets."""
    if not isinstance(inventory, dict):
        raise ValueError("PDF rendered OCR needs a page inventory")
    paths = inventory.get("vector_path_count", 0)
    images = inventory.get("image_block_count", 0)
    native_blocks = inventory.get("searchable_text_block_count", 0)
    types = inventory.get("type_word_index") or {}
    if any(type(x) is not int or x < 0 for x in (paths, images, native_blocks)):
        raise ValueError("Invalid PDF page drawing counts")
    # A vector-only sheet may contain searchable member codes while its
    # actual detail headings were converted to thousands of small paths.
    if paths >= 250 and not inventory.get("detail_title_anchors"):
        return True
    if paths >= 250 and types.get("type_word_witness_count", 0) == 0:
        return True
    if images > 0 and native_blocks == 0:
        return True
    return False


def recover_page_rendered_type_words(
    page, *, document_id: str, page_number: int, native_witnesses=(),
    language: str = "eng+fas", dpi: int = 240,
    max_words: int = 30000, max_pixels: int = 35000000,
) -> dict:
    """OCR a *single* selected page with strict provenance and no promotion.

    Returned word rectangles are PDF points (not scaled image pixels). In
    particular an OCR result BR.1 or BP1 is not an actual brace/base-plate
    instance. The caller must retain missing-Tesseract/budget failures.
    """
    if (not isinstance(document_id, str) or not document_id.strip()
            or type(page_number) is not int or page_number < 1):
        raise ValueError("OCR needs a source document/page identity")
    if (language not in _ALLOWED_LANGUAGES or type(dpi) is not int
            or not 150 <= dpi <= 360 or type(max_words) is not int
            or not 1 <= max_words <= 100000 or type(max_pixels) is not int
            or not 100000 <= max_pixels <= 100000000):
        raise ValueError("Invalid PDF OCR language or resource budget")
    box = _box(unrotated_page_bounds(page))
    if box is None:
        raise ValueError("Invalid rendered OCR page geometry")

    def blocked(reason: str, word_count=None):
        return {
            "document_id": document_id, "page": page_number,
            "status": reason, "source_word_count": word_count,
            "type_word_witnesses": [], "type_word_witness_count": 0,
            "all_ocr_words_examined": False,
            "ocr_language": language, "ocr_dpi": dpi,
            "source_quality": "RENDERED_OCR_NOT_VERIFIED",
            "physical_member_verified": False,
            "financially_payable": False,
        }

    page_width, page_height = box[2] - box[0], box[3] - box[1]
    if ceil(page_width * dpi / 72) * ceil(page_height * dpi / 72) > max_pixels:
        return blocked("BLOCKED_OCR_PIXEL_BUDGET")
    try:
        # full=True matters for pages where CAD letters are vector paths,
        # even when a title block has searchable/native text.
        textpage = page.get_textpage_ocr(language=language, dpi=dpi, full=True)
        words = list(page.get_text("words", textpage=textpage))
    except (OSError, RuntimeError, ValueError, TypeError, MemoryError, SystemError):
        return blocked("BLOCKED_OCR_ENGINE_OR_LANGUAGE_UNAVAILABLE")
    if len(words) > max_words:
        return blocked("BLOCKED_OCR_WORD_BUDGET", len(words))

    native = []
    for witness in native_witnesses:
        if (witness.get("document_id") != document_id or
                witness.get("page") != page_number):
            raise ValueError("Foreign native type witness in rendered OCR comparison")
        native_box = _box(witness.get("bbox_pt"))
        if native_box is None:
            raise ValueError("Invalid native type witness coordinates")
        native.append((witness.get("type_tag"), native_box))

    candidates = []
    for index, word in enumerate(words, 1):
        if not isinstance(word, (list, tuple)) or len(word) < 5:
            return blocked("BLOCKED_OCR_BAD_WORD_RECORD", len(words))
        token = str(word[4]).strip().strip(_TERMINAL_PUNCTUATION)
        match = TYPE_MARK.fullmatch(token)
        if not match:
            continue
        word_box = _box(word)
        if (word_box is None or word_box[0] < box[0] - 1 or
                word_box[1] < box[1] - 1 or word_box[2] > box[2] + 1 or
                word_box[3] > box[3] + 1):
            return blocked("BLOCKED_OCR_WORD_OUTSIDE_PAGE", len(words))
        tag = match.group(1).upper() + str(int(match.group(2)))
        duplicate = any(x == tag and _overlap(word_box, src) for x, src in native)
        candidates.append({
            "witness_id": f"{document_id}:p{page_number}:ocrword{index:06d}",
            "document_id": document_id, "page": page_number,
            "source_word_index": index, "source_token": token,
            "type_tag": tag, "bbox_pt": [round(v, 3) for v in word_box],
            "status": ("OCR_DUPLICATE_NATIVE_TYPE_MARK" if duplicate else
                       "OCR_TYPE_MARK_UNVERIFIED"),
            "source_quality": "RENDERED_OCR_NOT_VERIFIED",
            "ocr_language": language, "ocr_dpi": dpi,
            "source_method": "PYMUPDF_TESSERACT_FULL_PAGE",
            "physical_member_verified": False, "quantity_approved": False,
            "financially_payable": False,
        })

    return {
        "document_id": document_id, "page": page_number,
        "status": "INDEXED_RENDERED_OCR_TYPE_CANDIDATES",
        "source_word_count": len(words),
        "type_word_witnesses": candidates,
        "type_word_witness_count": len(candidates),
        "all_ocr_words_examined": True,
        "ocr_language": language, "ocr_dpi": dpi,
        "source_quality": "RENDERED_OCR_NOT_VERIFIED",
        "physical_member_verified": False, "financially_payable": False,
    }
