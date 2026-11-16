"""Source-bound visual readings of printed column identifiers for PDF review."""
from __future__ import annotations

import json
from pathlib import Path
import re

from core.drawings.pdf_type_word_witness import _box


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ValueError("Invalid PDF member review fields")


def _positive_int(value):
    if type(value) is not int or not 1 <= value <= 5000:
        raise ValueError("Invalid PDF member review page, position or count")


def _printed_id(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,23}", value) is None:
        raise ValueError("Invalid printed PDF member identifier")


def _bounds(value):
    if not isinstance(value, list) or len(value) != 4 or any(type(v) not in (int, float) for v in value) or not _box(value):
        raise ValueError("Invalid PDF member review bounds")


def validate_pdf_member_review(review):
    """Validate structural fields before comparing them with immutable intake evidence."""
    _fields(review, "schema_version source_sha256 groups")
    digest = review["source_sha256"]
    if type(review["schema_version"]) is not int or review["schema_version"] != 1:
        raise ValueError("Unsupported PDF member review schema")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid PDF member review source hash")
    groups = review["groups"]
    if not isinstance(groups, list) or not 1 <= len(groups) <= 100:
        raise ValueError("Invalid PDF member review group count")
    seen_types, seen_plan_marks, seen_positions = set(), set(), set()
    total = 0
    for group in groups:
        _fields(group, "type_tag plan detail")
        tag, plan, detail = group["type_tag"], group["plan"], group["detail"]
        if not isinstance(tag, str) or re.fullmatch(r"C[1-9][0-9]{0,2}", tag) is None or tag in seen_types:
            raise ValueError("Invalid or duplicate PDF member review column type")
        seen_types.add(tag)
        _fields(detail, "page bbox_pt printed_count marks")
        _positive_int(detail["page"])
        _positive_int(detail["printed_count"])
        _bounds(detail["bbox_pt"])
        if not isinstance(plan, list) or not plan or not isinstance(detail["marks"], list):
            raise ValueError("Invalid PDF member review witnesses")
        total += len(plan) + len(detail["marks"])
        if total > 2000:
            raise ValueError("PDF member review witness budget exceeded")
        for mark in plan:
            _fields(mark, "page grid_row grid_column printed_id bbox_pt")
            for field in ("page", "grid_row", "grid_column"):
                _positive_int(mark[field])
            _printed_id(mark["printed_id"])
            _bounds(mark["bbox_pt"])
            code, position = (mark["page"], mark["printed_id"]), (mark["page"], mark["grid_row"], mark["grid_column"])
            if code in seen_plan_marks or position in seen_positions:
                raise ValueError("Duplicate PDF plan member identity")
            seen_plan_marks.add(code)
            seen_positions.add(position)
        if len({mark["page"] for mark in plan}) != 1:
            raise ValueError("Each PDF member review group must refer to one plan page")
        detail_ids = set()
        for mark in detail["marks"]:
            _fields(mark, "printed_id bbox_pt")
            _printed_id(mark["printed_id"])
            _bounds(mark["bbox_pt"])
            if mark["printed_id"] in detail_ids:
                raise ValueError("Duplicate printed detail member identity")
            detail_ids.add(mark["printed_id"])
    return review


def load_pdf_member_review(path):
    """Load a bounded local visual-reading receipt and reject duplicate JSON fields."""
    def fields(pairs):
        value = dict(pairs)
        if len(value) != len(pairs):
            raise ValueError("Duplicate JSON key in PDF member review")
        return value

    with Path(path).open("rb") as stream:
        data = stream.read(512 * 1024 + 1)
    if len(data) > 512 * 1024:
        raise ValueError("PDF member review file budget exceeded")
    return validate_pdf_member_review(json.loads(data.decode("utf-8-sig"), object_pairs_hook=fields))
