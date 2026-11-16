"""Optional, offline OCR witnesses for CAD-outlined PDF text.

Raster recognition is never a drawing declaration, physical member, approved
quantity, or BOQ input. Each production witness refers to the immutable PDF
bytes and one page, in the same unrotated coordinate space as native words.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from math import ceil, floor, isfinite
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic
from unicodedata import normalize

from core.drawings.pdf_type_word_witness import (
    TYPE_MARK, _box, _overlap, unrotated_page_bounds,
)

_ALLOWED_LANGUAGES = {"eng", "fas", "eng+fas", "fas+eng"}
_TERMINAL_PUNCTUATION = ",;:()[]{}،؛"
_TAG_CHARACTERS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩‐‑‒–—−", "01234567890123456789------")
_ONE_LIKE = re.compile(r"^(BR|BP|SC|SW|C|B|F|T|W|S|P)[-.]?([Il|])$")
_TSV_COLUMNS = (
    "level", "page_num", "block_num", "par_num", "line_num", "word_num",
    "left", "top", "width", "height", "conf", "text",
)
_QUALITY = "RENDERED_OCR_NOT_VERIFIED"
_COORDINATES = "unrotated_pdf_points"
_SOURCE_COPY_LIMIT = 100 * 1024 * 1024


class _OCRBlocked(RuntimeError):
    def __init__(self, reason: str, word_count=None):
        super().__init__(reason)
        self.reason = reason
        self.word_count = word_count


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
    # Dense vector sheets may still have searchable metadata in the title block.
    return (paths >= 250 and (not inventory.get("detail_title_anchors") or
            types.get("type_word_witness_count", 0) == 0)) or (images > 0 and native_blocks == 0)


def _bounded_process(command, deadline, max_output_bytes):
    """Run a local child without buffering unlimited stdout."""
    try:
        with subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ) as child, ThreadPoolExecutor(max_workers=1) as reader:
            try:
                output = reader.submit(child.stdout.read, max_output_bytes + 1).result(
                    timeout=max(0.0, deadline - monotonic()))
                if len(output) > max_output_bytes:
                    raise _OCRBlocked("BLOCKED_OCR_OUTPUT_BYTE_BUDGET")
                if child.wait(timeout=max(0.0, deadline - monotonic())) != 0:
                    raise _OCRBlocked("BLOCKED_OCR_ENGINE_OR_LANGUAGE_UNAVAILABLE")
                return output
            except (TimeoutError, subprocess.TimeoutExpired) as exc:
                raise _OCRBlocked("BLOCKED_OCR_TIMEOUT") from exc
            finally:
                if child.poll() is None:
                    child.kill()
    except OSError as exc:
        raise _OCRBlocked("BLOCKED_OCR_ENGINE_OR_LANGUAGE_UNAVAILABLE") from exc


def _run_tesseract(path, *, language, dpi, max_seconds, max_output_bytes):
    """Use one deadline for the requested language check and OCR."""
    deadline = monotonic() + max_seconds
    if "+" in language:
        listed = _bounded_process(["tesseract", "--list-langs"], deadline, max_output_bytes)
        languages = {value.strip() for value in listed.splitlines()[1:]}
        if not set(language.encode("ascii").split(b"+")) <= languages:
            # Tesseract otherwise succeeds using whichever language did load.
            raise _OCRBlocked("BLOCKED_OCR_ENGINE_OR_LANGUAGE_UNAVAILABLE")
    return _bounded_process(
        ["tesseract", str(path), "stdout", "-l", language,
         "--dpi", str(dpi), "--psm", "11", "tsv"], deadline, max_output_bytes)


def _inside(inner, outer, slop=0.0):
    return all(outer[i] - slop <= inner[i] for i in (0, 1)) and all(
        inner[i] <= outer[i] + slop for i in (2, 3))


def _read_tsv(output, width, height, to_source):
    """Validate word records and translate rendered pixels back to the source page."""
    try:
        if not output.endswith(b"\n"):
            raise _OCRBlocked("BLOCKED_OCR_BAD_WORD_RECORD")
        rows = iter(output.decode("utf-8").splitlines())
    except (AttributeError, UnicodeDecodeError) as exc:
        raise _OCRBlocked("BLOCKED_OCR_BAD_WORD_RECORD") from exc
    if tuple(next(rows, "").split("\t")) != _TSV_COLUMNS:
        raise _OCRBlocked("BLOCKED_OCR_BAD_WORD_RECORD")
    page = next(rows, "").split("\t")
    if (len(page) != 12 or page[:6] != ["1", "1", "0", "0", "0", "0"] or
            page[6:10] != ["0", "0", str(width), str(height)]):
        raise _OCRBlocked("BLOCKED_OCR_BAD_WORD_RECORD")
    for row in rows:
        cols = row.split("\t", 11)
        if len(cols) != 12 or cols[0] not in {"2", "3", "4", "5"} or cols[1] != "1":
            raise _OCRBlocked("BLOCKED_OCR_BAD_WORD_RECORD")
        if cols[0] != "5":
            continue
        try:
            left, top, wide, tall = map(int, cols[6:10])
            confidence = float(cols[10])
            if not isfinite(confidence) or not 0 <= confidence <= 100 or not cols[11].strip():
                raise ValueError("Invalid Tesseract token or confidence")
        except ValueError as exc:
            raise _OCRBlocked("BLOCKED_OCR_BAD_WORD_RECORD") from exc
        if (left < 0 or top < 0 or wide <= 0 or tall <= 0 or
                left + wide > width or top + tall > height):
            raise _OCRBlocked("BLOCKED_OCR_WORD_OUTSIDE_PAGE")
        yield (*to_source(left, top, left + wide, top + tall), cols[11])


def _read_real_page(page, region, *, language, dpi, max_pixels, max_seconds, max_output_bytes,
                    render_rotation_degrees):
    import pymupdf

    scale = dpi / 72
    matrix = pymupdf.Matrix(scale, scale).prerotate(render_rotation_degrees - page.rotation)
    clip = pymupdf.Rect(region) * page.rotation_matrix
    extent = clip * matrix
    predicted_width = ceil(extent.x1) - floor(extent.x0)
    predicted_height = ceil(extent.y1) - floor(extent.y0)
    if predicted_width * predicted_height > max_pixels:
        raise _OCRBlocked("BLOCKED_OCR_PIXEL_BUDGET")
    pixmap = page.get_pixmap(matrix=matrix, clip=clip, colorspace=pymupdf.csGRAY,
                             alpha=False, annots=False)
    pixels = pixmap.width * pixmap.height
    if not 0 < pixels <= max_pixels:
        raise _OCRBlocked("BLOCKED_OCR_PIXEL_BUDGET")
    if pixmap.n != 1 or pixmap.stride != pixmap.width:
        raise _OCRBlocked("BLOCKED_OCR_RENDER_LAYOUT")
    inverse = ~matrix * page.derotation_matrix

    def to_source(left, top, right, bottom):
        return tuple(pymupdf.Rect(
            pixmap.x + left, pixmap.y + top, pixmap.x + right, pixmap.y + bottom,
        ) * inverse)

    image_bytes = pixmap.tobytes("pgm")
    # 8-bit grayscale PGM carries exactly one byte per pixel plus a short header.
    if not pixels < len(image_bytes) <= pixels + 64:
        raise _OCRBlocked("BLOCKED_OCR_RENDER_BYTE_BUDGET")
    with TemporaryDirectory(prefix="structuralpro_pdf_ocr_") as folder:
        image_path = Path(folder) / "page.pgm"
        image_path.write_bytes(image_bytes)
        output = _run_tesseract(image_path, language=language, dpi=dpi,
                                max_seconds=max_seconds, max_output_bytes=max_output_bytes)
    return _read_tsv(output, pixmap.width, pixmap.height, to_source), pixels, len(output)


def _match_word(raw):
    token = raw.strip().strip(_TERMINAL_PUNCTUATION).strip()
    normalized = normalize("NFKC", token).translate(_TAG_CHARACTERS)
    clear = TYPE_MARK.fullmatch(normalized)
    if clear:
        return token, clear[1].upper() + clear[2], []
    if normalized:
        # Only the prefix is case-normalized. A lower-case l is not the same
        # OCR observation as an upper-case Roman I.
        ambiguous = _ONE_LIKE.fullmatch(normalized[:-1].upper() + normalized[-1:])
        if ambiguous:
            prefix = ambiguous[1]
            return token, None, [prefix + suffix for suffix in ("1", "I", "l")]
    return token, None, []


def _source_binding(page, page_number, expected_sha):
    """Identify the immutable input bytes for an actual PyMuPDF page."""
    doc = page.parent
    if (doc is None or not doc.is_pdf or doc.needs_pass or doc.is_repaired or doc.is_dirty or
            page.number != page_number - 1):
        raise _OCRBlocked("BLOCKED_OCR_SOURCE_UNVERIFIED")
    source = doc.stream
    path = None
    if not isinstance(source, bytes):
        if not doc.name:
            raise _OCRBlocked("BLOCKED_OCR_SOURCE_UNVERIFIED")
        path = Path(doc.name)
        # File-backed documents need a stable snapshot to avoid mixing an
        # already-open page with bytes from a later version at the same path.
        with path.open("rb") as stream:
            source = stream.read(_SOURCE_COPY_LIMIT + 1)
        if len(source) > _SOURCE_COPY_LIMIT:
            raise _OCRBlocked("BLOCKED_OCR_SOURCE_BYTE_BUDGET")
    digest = sha256(source).hexdigest()
    if expected_sha is not None and expected_sha != digest:
        raise _OCRBlocked("BLOCKED_OCR_SOURCE_MISMATCH")
    return digest, source, path


def recover_page_rendered_type_words(
    page, *, document_id: str, page_number: int, native_witnesses=(),
    language: str = "eng+fas", dpi: int = 240,
    max_words: int = 30000, max_pixels: int = 35000000,
    source_sha256: str | None = None, render_bbox_pt=None,
    max_seconds: float = 20, max_output_bytes: int = 8 * 1024 * 1024,
    render_rotation_degrees: int = 0,
) -> dict:
    """Index unverified words from a whole page or an explicit unrotated region.

    Clear tags are lexical candidates only. Confusable Cl/CI observations keep
    their raw token and alternatives with no normalized type assigned. Optional
    quarter turns rotate the render clockwise without changing page coordinates.
    """
    if (not isinstance(document_id, str) or not document_id.strip()
            or type(page_number) is not int or page_number < 1
            or (source_sha256 is not None and (not isinstance(source_sha256, str) or
                re.fullmatch(r"[a-fA-F0-9]{64}", source_sha256) is None))):
        raise ValueError("OCR needs a source document/page identity")
    if (language not in _ALLOWED_LANGUAGES or type(dpi) is not int
            or not 150 <= dpi <= 360 or type(max_words) is not int
            or not 1 <= max_words <= 100000 or type(max_pixels) is not int
            or not 100000 <= max_pixels <= 100000000
            or type(max_seconds) not in {int, float} or not 0.01 <= max_seconds <= 120
            or type(render_rotation_degrees) is not int or render_rotation_degrees not in {0, 90, 180, 270}
            or type(max_output_bytes) is not int or not 1024 <= max_output_bytes <= 32 * 1024 * 1024):
        raise ValueError("Invalid PDF OCR language or resource budget")
    import pymupdf

    try:
        source_box = _box(unrotated_page_bounds(page))
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("Invalid rendered OCR page geometry") from exc
    if source_box is None:
        raise ValueError("Invalid rendered OCR page geometry")
    region = source_box if render_bbox_pt is None else _box(render_bbox_pt)
    if region is None or not _inside(region, source_box):
        raise ValueError("OCR render region is outside the source page")
    actual_digest = None
    backend = "LOCAL_TESSERACT_TSV" if isinstance(page, pymupdf.Page) else "PYMUPDF_TESSERACT_FULL_PAGE"
    settings = {
        "document_id": document_id, "page": page_number,
        "source_quality": _QUALITY, "coordinate_space": _COORDINATES,
        "render_bbox_pt": list(region),
        "render_rotation_degrees": render_rotation_degrees,
        "coverage_scope": "FULL_PAGE" if region == source_box else "RENDERED_REGION_ONLY",
        "ocr_language": language, "ocr_dpi": dpi, "source_method": backend,
        "physical_member_verified": False, "quantity_approved": False, "financially_payable": False,
    }

    def result(status, candidates, *, complete=False, count=None, pixels=None, output_bytes=None):
        return {
            **settings, "status": status, "source_sha256": actual_digest,
            "source_word_count": count if complete else None,
            "source_word_count_at_least": count if count is not None and not complete else None,
            "type_word_witnesses": candidates, "type_word_witness_count": len(candidates),
            "ambiguous_glyph_count": sum(x["status"] == "AMBIGUOUS_GLYPH" for x in candidates),
            "all_ocr_words_examined": complete,
            "rendered_pixel_count": pixels, "ocr_output_bytes": output_bytes,
        }

    native = []
    for witness in native_witnesses:
        if (not isinstance(witness, dict) or witness.get("document_id") != document_id
                or witness.get("page") != page_number):
            raise ValueError("Foreign native type witness in rendered OCR comparison")
        native_box = _box(witness.get("bbox_pt"))
        if native_box is None or not _inside(native_box, source_box, 1):
            raise ValueError("Invalid native type witness coordinates")
        native.append((witness.get("type_tag"), native_box))

    try:
        pixels = output_bytes = None
        if isinstance(page, pymupdf.Page):
            actual_digest, data, source_path = _source_binding(
                page, page_number, source_sha256.lower() if source_sha256 else None)
            render_settings = dict(language=language, dpi=dpi, max_pixels=max_pixels,
                                   max_seconds=max_seconds, max_output_bytes=max_output_bytes,
                                   render_rotation_degrees=render_rotation_degrees)
            if source_path is None:
                words, pixels, output_bytes = _read_real_page(page, region, **render_settings)
            else:
                with pymupdf.open(stream=data, filetype="pdf") as stable:
                    if stable.is_repaired or stable.needs_pass or page_number > len(stable):
                        raise _OCRBlocked("BLOCKED_OCR_SOURCE_UNVERIFIED")
                    stable_page = stable[page_number - 1]
                    if _box(unrotated_page_bounds(stable_page)) != source_box or stable_page.rotation != page.rotation:
                        raise _OCRBlocked("BLOCKED_OCR_SOURCE_MISMATCH")
                    words, pixels, output_bytes = _read_real_page(stable_page, region, **render_settings)
                with source_path.open("rb") as stream:
                    if stream.read(len(data) + 1) != data:
                        raise _OCRBlocked("BLOCKED_OCR_SOURCE_MISMATCH")
        else:
            # Legacy reader protocol for compatible adapters. An adapter may
            # retain its own page-coordinate witnesses, never an asserted SHA.
            if source_sha256 is not None or render_bbox_pt is not None or render_rotation_degrees:
                raise _OCRBlocked("BLOCKED_OCR_SOURCE_UNVERIFIED")
            width, height = source_box[2] - source_box[0], source_box[3] - source_box[1]
            if ceil(width * dpi / 72) * ceil(height * dpi / 72) > max_pixels:
                raise _OCRBlocked("BLOCKED_OCR_PIXEL_BUDGET")
            textpage = page.get_textpage_ocr(language=language, dpi=dpi, full=True)
            words = page.get_text("words", textpage=textpage)

        candidates = []
        count = encoded_bytes = 0
        for count, word in enumerate(words, 1):
            if count > max_words:
                raise _OCRBlocked("BLOCKED_OCR_WORD_BUDGET", count)
            if not isinstance(word, (list, tuple)) or len(word) < 5 or not isinstance(word[4], str):
                raise _OCRBlocked("BLOCKED_OCR_BAD_WORD_RECORD", count)
            raw = word[4]
            if len(raw) > max_output_bytes:
                raise _OCRBlocked("BLOCKED_OCR_OUTPUT_BYTE_BUDGET", count)
            encoded_bytes += len(raw.encode("utf-8"))
            if encoded_bytes > max_output_bytes:
                raise _OCRBlocked("BLOCKED_OCR_OUTPUT_BYTE_BUDGET", count)
            word_box = _box(word)
            # Render clipping can round outward by one pixel.
            if word_box is None or not _inside(word_box, region, 1):
                raise _OCRBlocked("BLOCKED_OCR_WORD_OUTSIDE_PAGE", count)
            token, tag, alternatives = _match_word(raw)
            if tag is None and not alternatives:
                continue
            duplicate = tag is not None and any(x == tag and _overlap(word_box, src) for x, src in native)
            candidates.append({
                **settings, "witness_id": f"{document_id}:p{page_number}:ocrword{count:06d}",
                "source_sha256": actual_digest,
                "source_word_index": count, "source_token": token, "raw_token": raw,
                "type_tag": tag, "normalized_tag": tag, "glyph_interpretations": alternatives,
                "bbox_pt": [round(v, 3) for v in word_box],
                "status": ("AMBIGUOUS_GLYPH" if alternatives else
                           "OCR_DUPLICATE_NATIVE_TYPE_MARK" if duplicate else "OCR_TYPE_MARK_UNVERIFIED"),
            })
        return result("INDEXED_RENDERED_OCR_TYPE_CANDIDATES", candidates, complete=True, count=count,
                      pixels=pixels, output_bytes=output_bytes)
    except _OCRBlocked as exc:
        return result(exc.reason, [], count=exc.word_count)
    except (OSError, RuntimeError, ValueError, TypeError, MemoryError, SystemError, AttributeError):
        return result("BLOCKED_OCR_ENGINE_OR_LANGUAGE_UNAVAILABLE", [])
