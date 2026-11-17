"""Source-bound PDF detail and cross-sheet evidence. Never a quantity engine."""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from math import dist
from pathlib import Path
import re
import unicodedata

from core.drawings.pdf_detail_object_index import _family_words, _tag
from core.drawings.pdf_member_review import validate_pdf_member_review
from core.drawings.pdf_occurrence_review import build_pdf_occurrence_reviews
from core.drawings.pdf_structural_plan_review import build_pdf_structural_plan_reviews
from core.drawings.pdf_beam_profile_review import correlate_pdf_beam_profile_witnesses
from core.drawings.pdf_beam_axis_crosscheck import reconcile_pdf_beam_grid_labels
from core.drawings.pdf_beam_end_support_review import review_beam_ends_against_independent_grid
from core.drawings.pdf_beam_span_evidence_requests import build_beam_span_evidence_requests
from core.drawings.pdf_type_word_witness import _box


_CODE = r"[A-Z0-9][A-Z0-9_.-]{0,31}"
_DETAIL = r"(?:[A-Z0-9.-]{0,15}[0-9][A-Z0-9.-]{0,16}|[A-Z]{1,4}-[A-Z]{1,4})"
_TYPE = r"[A-Z]{1,4}[-–.]?[0-9]{1,4}"
_AXIS = r"[A-Z0-9-]{1,16}\s*/\s*[A-Z0-9-]{1,16}"
_DECIMAL = r"[0-9]{1,8}(?:\.[0-9]{1,8})?"
_DISTANCE_UNIT = r"(?:MM|CM|M)"
_DEFINITIONS = (
    ("SHEET_ID", rf"(?:SHEET(?: NO\.)?|شیت)(?:\s*[:#]\s*|\s+)(?P<code>{_CODE})"),
    ("REVISION", rf"(?:REV(?:ISION)?\.?|ویرایش|نسخه)(?:\s*[:#]\s*|\s+)(?P<code>{_CODE})"),
    ("PRINTED_SCALE", r"(?:(?:SCALE|مقیاس)(?:\s*:\s*|\s+)|SC\.\s*)1\s*[:/]\s*(?P<denominator>[1-9][0-9]{0,4})"),
    ("INSTANCE", rf"(?:INSTANCE|عضو)\s+(?P<member>{_CODE})\s+(?:TYPE|تیپ)\s+(?P<tag>{_TYPE})"
                 rf"\s+(?:GRID|آکس)\s+(?P<axis>{_AXIS})\s+(?:LEVEL|تراز)\s+(?P<level>{_CODE})"),
    ("AXIS", rf"(?:GRID|AXIS|آکس)\s+(?P<code>{_AXIS})"),
    ("LEVEL", rf"(?:LEVEL|FLOOR|تراز|طبقه)\s+(?P<code>{_CODE})"),
    ("COLUMN_DIMENSION", rf"COLUMN DIM\s+(?P<member>{_CODE})\s+TYPE\s+(?P<tag>{_TYPE})"
                         rf"\s+(?P<dimension>WIDTH|DEPTH)\s+(?P<value>{_DECIMAL})"
                         rf"(?:\s*(?P<unit>{_DISTANCE_UNIT}))?"),
    ("COLUMN_SPEC", rf"COLUMN SPEC\s+(?P<member>{_CODE})\s+TYPE\s+(?P<tag>{_TYPE})"
                    rf"\s+RECTANGULAR CONCRETE CONNECTIONS INCLUDED DEDUCTIONS\s+(?P<deductions>{_DECIMAL})\s*M3"),
    ("COLUMN_RANGE", rf"COLUMN RANGE\s+(?P<member>{_CODE})\s+GRID\s+(?P<axis>{_AXIS})\s+LEVEL\s+(?P<level>{_CODE})"
                     rf"\s+FROM\s+(?P<bottom>[+-]?{_DECIMAL})\s*(?P<bottom_unit>{_DISTANCE_UNIT})"
                     rf"\s+TO\s+(?P<top>[+-]?{_DECIMAL})\s*(?P<top_unit>{_DISTANCE_UNIT})"
                     rf"\s+LENGTH\s+(?P<length>{_DECIMAL})\s*(?P<length_unit>{_DISTANCE_UNIT})"
                     rf"\s+COUNT\s+(?P<occurrence_count>[1-9][0-9]{{0,3}})"),
    ("CALLOUT", rf"(?:(?:FOR INSTANCE|برای عضو)\s+(?P<member>{_CODE})\s+|(?:SEE|رجوع به)\s+)?"
                rf"(?P<reference>DETAIL|SECTION|ELEVATION|دیتیل|مقطع|نما)\s+(?P<detail>{_DETAIL})"
                rf"\s*(?:/|ON|در شیت)\s*(?P<sheet>{_CODE})"),
    ("SCHEDULE_ROW", rf"(?:SCHEDULE ROW|ردیف جدول)\s+(?:TYPE|تیپ)\s+(?P<tag>{_TYPE})"
                     rf"(?:\s+(?:LEVEL|تراز)\s+(?P<level>{_CODE}))?\s+"
                     rf"(?P<reference>DETAIL|SECTION|دیتیل|مقطع)\s+(?P<detail>{_DETAIL})"
                     rf"\s*(?:/|ON|در شیت)\s*(?P<sheet>{_CODE})"),
    ("DETAIL_TITLE", rf"(?P<reference>DETAIL|SECTION|ELEVATION|دیتیل|جزئیات|مقطع|برش|نما)"
                     rf"\s+(?P<detail>{_DETAIL})(?:\s+(?P<title>.{{1,120}}))?"),
)
_PATTERNS = [(kind, re.compile(pattern, re.I)) for kind, pattern in _DEFINITIONS]
_DETAIL_KIND = {
    "دیتیل": "DETAIL", "جزئیات": "DETAIL", "مقطع": "SECTION", "برش": "SECTION", "نما": "ELEVATION"
}
_PLAN = re.compile(
    r"(?:(?:COLUMN|BEAM|FOUNDATION|ROOF|SLAB|WALL|MECHANICAL|ELECTRICAL|ARCHITECTURAL|FLOOR)"
    r" (?:LAYOUT |TYPE )?PLAN|پلان (?:ستون|تیر|فونداسیون|سقف|معماری|برق|مکانیک))", re.I)
_SCHEDULE = re.compile(
    r"(?:(?:COLUMN|BEAM|REBAR|REINFORCEMENT|DOOR|WINDOW|EQUIPMENT) SCHEDULE|جدول (?:آرماتور|میلگرد|مشخصات))",
    re.I)
_ROLE_BY_TITLE = {
    "AXIS PLAN": "AXIS_PLAN", "پلان آکس بندی": "AXIS_PLAN", "LEGEND": "LEGEND",
    "GENERAL NOTES": "NOTES", "توضیحات عمومی": "NOTES",
    "SECTION": "SECTION", "ELEVATION": "ELEVATION", "نما": "ELEVATION",
}
_LEGACY_ROLES = {
    "axis_plan": "AXIS_PLAN", "column_type_plan": "PLAN", "foundation_plan": "PLAN",
    "beam_layout_plan": "PLAN", "formwork_plan": "PLAN", "roof_drainage_plan": "PLAN",
    "pilot_floor_plan": "PLAN", "ground_floor_plan": "PLAN", "first_floor_plan": "PLAN",
    "column_detail": "DETAIL",
    "floor_preparation_plan": "PLAN", "excavation_plan": "PLAN",
    "building_section": "SECTION", "building_elevation": "ELEVATION", "reinforcement_plan": "PLAN",
}
_FAMILIES = (
    "bracing",     "beam", "column", "foundation", "slab_roof", "wall_opening", "stair_ramp",
    "reinforcement_connection", "architecture_finishes", "mechanical", "electrical", "unknown",
)
_LOCAL_LINK_PAIR_LIMIT = 1_000_000
_VIEW_ROLES = {"CLOSED_CONTOUR", "OPEN_CHAIN", "BRANCHED_STROKES",
               "CURVED_ENDPOINT_CYCLE", "CURVE_CONTROL_HULL", "FILL_BOUNDARY_UNRESOLVED"}
_QUANTITY_PENDING = {
    "quantity_status": "NO_QUANTITY", "quantity_reason": "MISSING_DIMENSION_EVIDENCE",
    "physical_member_verified": False, "member_quantity": None,
}
_AMBIGUOUS_STROKE_REASONS = {
    "AMBIGUOUS_UPRIGHT", "AMBIGUOUS_GLYPH_OWNERSHIP", "MULTIPLE_GLYPH_INTERPRETATIONS",
    "MULTIPLE_NUMERAL_INTERPRETATIONS", "UNEXPECTED_GLYPH_STROKE", "POSSIBLE_ADJACENT_GLYPH",
}
_REASONS = {
    "RASTER_SEMANTICS_UNVERIFIED": ("خوانش معنایی تصویر تأیید نشده است", "رندر یا OCR کنترل‌شده و مدرک اصلی"),
    "RASTER_VECTOR_OVERLAP": ("تصویر در محدوده شاهد برداری حضور دارد", "مقابلهٔ تصویر با هندسهٔ همان نما"),
    "GEOMETRY_EXTRACTION_BLOCKED": ("استخراج مسیرهای برداری کامل نیست", "سند خوانا یا بازرسی مستقل مسیرها"),
    "PAGE_DECLARATIONS_UNREADABLE": ("خوانش نشانی‌های سند در این صفحه کامل نیست", "متن معتبر و بازبینی صفحه"),
    "UNCLASSIFIED_SHEET_ROLE": ("کارکرد شیت یا بخشی از آن نامعلوم است", "عنوان کنترل‌شده و قرائت مستقل صفحه"),
    "UNTITLED_CONTOUR": ("هندسه بدون عنوان یکتای دیتیل باقی مانده است", "عنوان یا مرز تأییدشده دیتیل"),
    "NON_CONTOUR_TOPOLOGY": ("هندسهٔ باز یا منشعب به یک دیتیل یکتا قابل انتساب نیست", "شاهد مرز یا دسته‌بندی مسیر"),
    "DETAIL_GEOMETRY_AMBIGUOUS": ("عنوان و شکل نامزد پیوند یکتا ندارند", "ارجاع صریح یا محدودهٔ تأییدشده دیتیل"),
    "DETAIL_FAMILY_UNRESOLVED": ("خانوادهٔ مهندسی دیتیل با عنوان اثبات نشده است", "عنوان و طبقه‌بندی بازبینی‌شده"),
    "MULTIPLE_DETAIL_TYPE_MARKS": ("عنوان چند شناسهٔ تیپ دارد", "تیپ‌های تفکیک‌شده و نشانی دیتیل مربوط به هر تیپ"),
    "AMBIGUOUS_LOCAL_TYPE_MARK": ("چند پیرامون برای واژه یا چند واژه برای شکل ممکن است", "شناسه و مرز یکتای عضو"),
    "UNBOUND_LOCAL_TYPE_MARK": ("برچسب تیپ به مرز جداشدنی وصل نشده است", "نقشه دارای علامت و محل یکتای تیپ"),
    "LOCAL_LINK_SEARCH_BUDGET": ("بودجه بررسی روابط محلی این صفحه تمام شد", "شیت تفکیک‌شده یا کنترل دستی روابط"),
    "MISSING_VIEW_SCALE": ("برای این نما مقیاس محلی مستند پیدا نشد", "مقیاس یا مرجع کالیبراسیون همان نما"),
    "AMBIGUOUS_VIEW_SCALE": ("چند مقیاس یا چند محدوده برای این نشانهٔ مقیاس ممکن است", "مقیاس مجزای هر نما"),
    "INSTANCE_SCOPE_CONFLICT": ("هویت، تیپ یا آکس وقوع بین شواهد متفاوت است", "سند حاکم و مختصات یا آکس مستقل"),
    "INSTANCE_PLAN_GEOMETRY_MISSING": ("وقوع به هندسهٔ جداشدنی پلان وصل نشده است", "شاهد محل و مرز عضو در پلان"),
    "INSTANCE_GEOMETRY_AMBIGUOUS": ("چند نشانه یا چند شکل برای مکان وقوع ممکن است", "شناسه محل و هندسه یکتای عضو"),
    "UNVERIFIED_DOCUMENT_SCOPE": ("هم‌پروژه و هم‌نسخه بودن مدارک احراز نشده است", "فهرست مدارک حاکم با اثر انگشت"),
    "MISSING_INDEPENDENT_LEVEL": ("تراز وقوع شاهد مستقل ندارد", "برش، نما یا جدول همان نسخه با تراز صریح"),
    "MISSING_INDEPENDENT_AXIS": ("موقعیت آکس شاهد مستقل ندارد", "پلان آکس‌بندی همان نسخه با شناسه صریح"),
    "REFERENCE_TARGET_NOT_FOUND": ("شیت و شناسهٔ دیتیل ارجاع‌شده پیدا نشد", "شیت مقصد و کد دیتیل"),
    "AMBIGUOUS_REFERENCE_TARGET": ("بیش از یک شاهد مقصد با کد ارجاع برابر است", "شیت یا نسخهٔ حاکم و ارجاع یکتا"),
    "REFERENCE_SUBJECT_NOT_FOUND": ("نشانی وقوع ارجاع در همین صفحه احراز نشد", "شناسه وقوع متصل به همان پلان"),
    "TYPE_FAMILY_CONFLICT": ("تیپ یا خانوادهٔ ارجاع و دیتیل ناسازگار است", "تطبیق مشخصات تیپ و خانواده"),
    "REFERENCE_TARGET_UNRESOLVED": ("هندسهٔ مقصد ارجاع تعیین تکلیف نشده است", "دیتیل دارای مرز و شواهد منبع"),
    "REFERENCE_SOURCE_UNRESOLVED": ("رابطهٔ وقوع با شکل پلان حل نشده است", "محدوده و شواهد یکتای وقوع در پلان"),
    "SCHEDULE_CONTEXT_UNVERIFIED": ("نقش جدول برای این ردیف صریح احراز نشده است", "عنوان و دامنهٔ جدول حاکم"),
    "MISSING_TARGET_TYPE": ("تیپ مقصد به‌صراحت اعلام نشده است", "شناسه تیپ در عنوان یا جدول نسخهٔ حاکم"),
    "CONFLICTING_DETAIL_REFERENCES": ("برای تیپ یا وقوع در یک تراز چند ارجاع هم‌نقش وجود دارد", "مرجع تفکیک دیتیل‌ها یا اصلاحیهٔ حاکم"),
    "NOTE_APPLICABILITY_UNRESOLVED": ("دامنهٔ کاربرد یادداشت تعیین نشده است", "ارجاع صریح به شیت، دیتیل یا تیپ"),
    "SUPERSEDED_SOURCE": ("حداقل یک سند منسوخ ثبت شده است", "مدرک حاکم جاری"),
    "REVISION_CONFLICT": ("ویرایش چاپ‌شده یا ویرایش دو سند ناسازگار است", "برگهٔ ابلاغ و ویرایش حاکم"),
    "DIFFERENT_PROJECT_OR_ISSUE": ("شناسهٔ پروژه یا مجموعه ابلاغ دو سند متفاوت است", "شاهد عضویت در مجموعه حاکم"),
    "DUPLICATE_CURRENT_SHEET_ID": ("بیش از یک صفحه با شناسهٔ شیت یکسان در مجموعه ابلاغ جاری ثبت شده است", "فهرست مصوب شیت‌های جاری و تعیین نسخهٔ حاکم هر شیت"),
    "LEGACY_GRID_LEVEL_UNKNOWN": ("شاهد موقعیت شبکه برای تکرار عضو در ترازها کافی نیست", "شناسه عضو و تراز اجرایی مستقل"),
    "RENDERED_OCR_TYPE_UNVERIFIED": ("تشخیص برچسب از تصویر/خطوط PDF با OCR محلی احتمالی است", "مقابله با متن خوانای نقشه حاکم و محل دقیق عضو"),
    "AMBIGUOUS_GLYPH": ("نوشته بیش از یک خوانش ممکن دارد", "خوانش مستقیم شکل حروف و برچسب نقشه"),
    "MISSING_DIMENSION_EVIDENCE": ("ابعاد اجرایی، واحد، تراز یا کسورات این رخداد سند کافی ندارند", "ابعاد دارای واحد و کالیبراسیون و محدوده اجرایی همان عضو"),
    "COLUMN_DETAIL_MARK_UNRESOLVED": ("برچسب تیپ در یک ردیف یکتای دیتیل پیدا نشد", "شیت دیتیل و عنوان تیپ با محدودهٔ مشخص"),
    "BLOCKED_PRINTED_MEMBER_ID_CONFLICT": ("شناسه‌های چاپی پلان و دیتیل برای این تیپ یکسان نیستند", "اصلاحیه یا تعیین تکلیف شناسه‌ها در سند حاکم"),
    "BLOCKED_PRINTED_MEMBER_COUNT_CONFLICT": ("شمار چاپی دیتیل با شاهد پلان یا فهرست دیتیل نمی‌خواند", "ردیف و شمار بازبینی‌شده در نقشه حاکم"),
    "DESIGN_AUTHORITY_REQUIRED": ("انتساب چاپی عضو بین پلان و دیتیل متعارض است",
                                  "تخصیص صریح شناسه‌های درگیر در پاسخ ابلاغی طراح و شماره و تاریخ ویرایش نقشه حاکم"),
}
_REVIEWABLE = {
    "REVISION_CONFLICT", "SUPERSEDED_SOURCE", "DIFFERENT_PROJECT_OR_ISSUE", "UNVERIFIED_DOCUMENT_SCOPE",
    "DUPLICATE_CURRENT_SHEET_ID",
    "TYPE_FAMILY_CONFLICT", "MULTIPLE_DETAIL_TYPE_MARKS", "AMBIGUOUS_LOCAL_TYPE_MARK",
    "REFERENCE_TARGET_NOT_FOUND", "AMBIGUOUS_REFERENCE_TARGET", "REFERENCE_SUBJECT_NOT_FOUND",
    "REFERENCE_TARGET_UNRESOLVED", "REFERENCE_SOURCE_UNRESOLVED", "CONFLICTING_DETAIL_REFERENCES",
    "INSTANCE_SCOPE_CONFLICT", "INSTANCE_GEOMETRY_AMBIGUOUS", "AMBIGUOUS_VIEW_SCALE", "MISSING_TARGET_TYPE",
    "SCHEDULE_CONTEXT_UNVERIFIED", "RENDERED_OCR_TYPE_UNVERIFIED", "AMBIGUOUS_GLYPH",
    "BLOCKED_PRINTED_MEMBER_ID_CONFLICT", "BLOCKED_PRINTED_MEMBER_COUNT_CONFLICT", "DESIGN_AUTHORITY_REQUIRED",
}


def _stable(kind, *value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{kind}:{sha256(data).hexdigest()[:32]}"


def _normalized(raw):
    text = unicodedata.normalize("NFKC", raw).translate(str.maketrans(
        "يىك۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "ییک01234567890123456789"))
    return " ".join(text.replace("\u200c", " ").replace("ـ", "").split()).strip()


def _scope_token(value, field):
    if not isinstance(value, str):
        raise ValueError(f"Invalid PDF registry {field}")
    value = _normalized(value).upper()
    if not re.fullmatch(_CODE, value):
        raise ValueError(f"Invalid PDF registry {field}")
    return value


def _parse_registry(data):
    if data is None:
        return {}
    if (not isinstance(data, dict) or set(data) != {"schema_version", "documents"}
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or not isinstance(data["documents"], list) or not 1 <= len(data["documents"]) <= 100):
        raise ValueError("Invalid PDF revision registry")
    by_hash = {}
    for item in data["documents"]:
        if not isinstance(item, dict) or set(item) != {
                "sha256", "project_id", "issue_id", "revision", "status", "authority_reference"}:
            raise ValueError("Invalid PDF revision registry entry")
        digest, authority, status = item["sha256"], item["authority_reference"], item["status"]
        if (not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest)
                or digest in by_hash or status not in ("CURRENT", "SUPERSEDED")
                or not isinstance(authority, str) or not 3 <= len(authority.strip()) <= 250
                or any(ord(char) < 32 for char in authority)):
            raise ValueError("Invalid or duplicate PDF source SHA or revision authority")
        by_hash[digest] = {
            **item, "authority_reference": authority.strip(),
            **{key: _scope_token(item[key], key) for key in ("project_id", "issue_id", "revision")},
        }
    return by_hash


def load_pdf_revision_register(path):
    """Load an operator-provided controlling document register without side effects."""
    def unique(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Duplicate key in PDF revision registry")
        return result

    with Path(path).open("rb") as stream:
        data = stream.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        raise ValueError("PDF revision registry exceeds file budget")
    parsed = json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique)
    _parse_registry(parsed)
    return parsed


def read_pdf_page_declarations(page, *, max_lines=12000):
    """Extract complete printed lines, preserving unrotated location and orientation."""
    import pymupdf
    declarations = []
    count = 0
    try:
        flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
        document = page.get_text("dict", flags=flags)
        for block in document.get("blocks", ()):
            for line in block.get("lines", ()):
                count += 1
                if count > max_lines:
                    return {"status": "BLOCKED_DECLARATION_LINE_BUDGET", "declarations": []}
                raw = "".join(span["text"] for span in line["spans"])
                box = _box(line.get("bbox"))
                normalized = _normalized(raw)
                if not normalized:
                    continue
                if box is None:
                    return {"status": "BLOCKED_INVALID_DECLARATION_BOX", "declarations": []}
                matched = []
                for part in normalized.split("|"):
                    part = part.strip()
                    for kind, regex in _PATTERNS:
                        match = regex.fullmatch(part)
                        if match:
                            matched.append((kind, match.groupdict()))
                            break
                    else:
                        role = _ROLE_BY_TITLE.get(part.upper())
                        if role or _PLAN.fullmatch(part) or _SCHEDULE.fullmatch(part):
                            matched.append(("PAGE_ROLE", {"role": role or (
                                "PLAN" if _PLAN.fullmatch(part) else "SCHEDULE")}))
                for index, (kind, values) in enumerate(matched, 1):
                    declarations.append({
                        **{k: v.upper() if v and k != "title" else v for k, v in values.items()},
                        "kind": kind, "source_line": count, "part": index,
                        "bbox_pt": list(box), "direction": list(line.get("dir", (1, 0))),
                        "printed": raw[:250],
                    })
    except (RuntimeError, ValueError, TypeError, MemoryError, KeyError):
        return {"status": "BLOCKED_DECLARATION_EXTRACTION", "declarations": []}
    return {"status": "EXAMINED", "declarations": declarations}


def _type(raw):
    return (raw or "").upper().replace("-", "").replace("–", "").replace(".", "")


def _title_types(title):
    return sorted({_type(x.group()) for x in re.finditer(rf"\b{_TYPE}\b", title or "", re.I)})


def _near(rect, other, limit):
    if not rect or not other:
        return False
    dx = max(0, rect[0] - other[2], other[0] - rect[2])
    dy = max(0, rect[1] - other[3], other[1] - rect[3])
    return dx * dx + dy * dy <= limit * limit


def _overlapping_images(page, box):
    return [item for item in page["raw"]["image_placements"]
            if all(max(box[i], item["bbox_pt"][i]) < min(box[i + 2], item["bbox_pt"][i + 2]) for i in (0, 1))]


def _nearby(bounded, anchors, *, limit):
    by_anchor = defaultdict(list)
    by_shape = defaultdict(list)
    # Intentionally conservative. Relationships also require a unique reverse
    # association. Distances are used only within one PDF page and coordinate frame.
    for anchor in anchors:
        for node in bounded:
            if _near(node["bbox_pt"], anchor["bbox_pt"], limit):
                by_anchor[anchor["anchor_id"]].append(node)
                by_shape[node["node_id"]].append(anchor)
    return by_anchor, by_shape


class _Graph:
    def __init__(self, max_records):
        self.nodes, self.edges, self.issues = {}, [], {}
        self.max_records = max_records

    def node(self, kind, identity, label, status, anchors=(), **fields):
        key = _stable(kind, *identity)
        if key in self.nodes:
            raise ValueError("Duplicate PDF evidence graph node")
        result = {"node_id": key, "kind": kind, "label": label, "status": status,
                  "anchors": list(anchors), "financially_payable": False, **fields}
        self.nodes[key] = result
        self.check_budget()
        return result

    def issue(self, subject, code, anchors=(), status="UNRESOLVED"):
        key = _stable("ISSUE", subject["node_id"], code)
        reason, needed = _REASONS[code]
        incoming = anchors or subject["anchors"]
        current = self.issues.get(key)
        if current:
            refs = {a["anchor_id"]: a for a in [*current["anchors"], *incoming]}
            current["anchors"] = list(refs.values())
            if status == "BLOCKED":
                current["status"] = status
            return
        self.issues[key] = {
            "issue_id": key, "node_id": subject["node_id"], "status": status,
            "reason_code": code, "reason": reason, "required_evidence": needed,
            "anchors": list(incoming), "financially_payable": False,
        }
        self.check_budget()

    def edge(self, relationship, source, target, anchors, *, status, reason, code=None, candidates=()):
        target_id = target["node_id"] if target is not None else None
        refs = {anchor["anchor_id"]: anchor for anchor in anchors}
        edge = {"edge_id": _stable("EDGE", relationship, source["node_id"], target_id, sorted(refs)),
                "relationship": relationship, "source_id": source["node_id"], "target_id": target_id,
                "status": status, "reason_code": code, "reason": reason,
                "anchors": list(refs.values()), "candidate_ids": list(candidates),
                "financially_payable": False, "quantity_approved": False}
        self.edges.append(edge)
        self.check_budget()
        return edge

    def check_budget(self):
        if len(self.nodes) + len(self.edges) + len(self.issues) > self.max_records:
            raise ValueError("Combined PDF evidence graph record budget exceeded; no graph published")


def _document_scope(page):
    # An issue can legitimately contain sheets with different *per-sheet*
    # revision numbers. Each sheet revision is separately checked against
    # its authoritative registration in _page_record. The shared scope for
    # cross-sheet identities is the governing project + issue, NOT revision.
    registration = page["authority"]
    if registration and not page["authority_block"]:
        return registration["project_id"], registration["issue_id"]
    return ("UNREGISTERED_DOCUMENT", page["sha256"])


def _scope_disagreement(left, right):
    for page in (left, right):
        if page["authority_block"]:
            return page["authority_block"]
    a, b = left["authority"], right["authority"]
    if not a or not b:
        return "UNVERIFIED_DOCUMENT_SCOPE"
    if (a["project_id"], a["issue_id"]) != (b["project_id"], b["issue_id"]):
        return "DIFFERENT_PROJECT_OR_ISSUE"
    # Do not require the same drawing revision across *different* sheets:
    # R1 of S-101 and R3 of S-201 can be jointly current in one issue.
    # A mismatch against each sheet's own printed revision is already vetoed
    # through authority_block on that page.
    return None


def _ambiguous_stroke_words(index):
    return [word for word in index.get("rejections", ()) if word.get("reason") in _AMBIGUOUS_STROKE_REASONS]


def _page_record(g, doc, raw, authority):
    doc_id, number = doc["document_id"], raw["page"]
    digest = doc["sha256"]
    topo = raw["detail_topology"]
    if (topo.get("document_id"), topo.get("page")) != (doc_id, number):
        raise ValueError("Foreign PDF topology page")
    extraction = raw["sheet_declarations"]
    anchors = [{
        **item, "anchor_id": _stable("LINE", digest, number, item["source_line"], item["part"]),
        "document_id": doc_id, "page": number, "coordinate_space": "unrotated_pdf_points",
        "source_sha256": digest, "source_name": doc["source_name"],
    } for item in extraction["declarations"]]
    if len({item["anchor_id"] for item in anchors}) != len(anchors):
        raise ValueError("Duplicate PDF declaration source line")
    lookup = defaultdict(list)
    for item in anchors:
        lookup[item["kind"]].append(item)
    sheet_ids = {item["code"] for item in lookup["SHEET_ID"]}
    printed_revisions = {item["code"] for item in lookup["REVISION"]}
    sheet_id = next(iter(sheet_ids)) if len(sheet_ids) == 1 else None
    roles = {item["role"] for item in lookup["PAGE_ROLE"]}
    if not roles:
        explicit_titles = {_DETAIL_KIND.get(w["reference"], w["reference"]) for w in lookup["DETAIL_TITLE"]}
        roles = explicit_titles or {_LEGACY_ROLES.get(raw.get("sheet_kind"), "UNKNOWN")}
    role = next(iter(roles)) if len(roles) == 1 else "MIXED_VIEWS"
    conflict = ("SUPERSEDED_SOURCE" if authority and authority["status"] == "SUPERSEDED" else
                "REVISION_CONFLICT" if len(printed_revisions) > 1 or (
                    authority and printed_revisions and printed_revisions != {authority["revision"]})
                else None)
    geometry_blocked = str(topo["status"]).startswith("BLOCKED")
    raster = raw["image_block_count"] > 0
    raster_only = raster and not raw["vector_path_count"]
    extraction_blocked = extraction["status"] != "EXAMINED" or bool(raw["extraction_errors"])
    word_witnesses = raw["type_word_index"]["type_word_witnesses"]
    rendered_ocr = raw.get("rendered_type_word_index") or {}
    ocr_witnesses = rendered_ocr.get("type_word_witnesses", ())
    vector_index = raw.get("vector_type_word_index") or {}
    vector_witnesses = vector_index.get("type_word_witnesses", ())
    geometric_labels = sum(len(lookup[kind]) for kind in ("DETAIL_TITLE", "PRINTED_SCALE", "INSTANCE"))
    structured_count = sum(len(lookup[kind]) for kind in ("DETAIL_TITLE", "INSTANCE", "SCHEDULE_ROW"))
    word_count = len(word_witnesses) + len(ocr_witnesses) + len(vector_witnesses)
    local_pairs = (len(topo["groups"]) * (geometric_labels + word_count + len(raw["image_placements"])) +
                   word_count * structured_count)
    local_links_blocked = local_pairs > _LOCAL_LINK_PAIR_LIMIT
    state = ("BLOCKED" if conflict or raster_only or extraction_blocked or geometry_blocked or local_links_blocked
             else "UNRESOLVED" if raster or role == "UNKNOWN" else "EXAMINED")
    page_anchor = {"anchor_id": _stable("PAGE", digest, number), "document_id": doc_id, "page": number,
                   "kind": "SHEET_EXTENT", "bbox_pt": raw["source_bbox_pt"]}
    node = g.node("SHEET", (digest, number), sheet_id or f"{doc_id} p{number}", state,
                  [page_anchor, *lookup["SHEET_ID"], *lookup["REVISION"]])
    if raster:
        g.issue(node, "RASTER_SEMANTICS_UNVERIFIED", raw.get("image_placements", ()), status="BLOCKED")
    if extraction_blocked:
        g.issue(node, "PAGE_DECLARATIONS_UNREADABLE", status="BLOCKED")
    if geometry_blocked:
        g.issue(node, "GEOMETRY_EXTRACTION_BLOCKED", status="BLOCKED")
    if local_links_blocked:
        g.issue(node, "LOCAL_LINK_SEARCH_BUDGET", status="BLOCKED")
    if conflict:
        g.issue(node, conflict, status="BLOCKED")
    if role == "UNKNOWN":
        g.issue(node, "UNCLASSIFIED_SHEET_ROLE")
    if len(sheet_ids) > 1:
        g.issue(node, "AMBIGUOUS_REFERENCE_TARGET", lookup["SHEET_ID"], status="BLOCKED")
    return {
        "node_id": node["node_id"], "document_id": doc_id, "page": number, "sheet_id": sheet_id,
        "page_role": role, "sheet_kind": raw["sheet_kind"], "status": state, "rotation": topo.get("rotation", 0),
        "source_bbox_pt": raw["source_bbox_pt"],
        "content_kind": "HYBRID" if raster and not raster_only else "RASTER" if raster else
                        "VECTOR" if raw["vector_path_count"] else "TEXT" if raw["searchable_text_block_count"]
                        else "NO_DETECTED_CONTENT",
        "source_path_count": topo.get("source_path_count"),
        "source_operator_count": topo.get("source_operator_count"),
        "source_operators_accounted_for": topo.get("source_operators_accounted_for"),
        "all_source_operators_decoded": topo.get("all_source_operators_decoded", False),
        "source_degenerate_operator_count": topo.get("source_degenerate_operator_count", 0),
        "source_degenerate_operator_ids": topo.get("source_degenerate_operator_ids", []),
        "source_degenerate_quads_review_required": topo.get(
            "source_degenerate_quads_review_required", False),
        "topology_status": topo["status"], "topology_group_count": len(topo["groups"]),
        "printed_revisions": sorted(printed_revisions),
        "authority_status": conflict or (authority["status"] if authority else "UNREGISTERED"),
        "authority": authority, "sha256": digest, "source_name": doc["source_name"], "authority_block": conflict,
        "anchors_by_kind": lookup, "raw": raw, "node": node,
        "linkable": not (extraction_blocked or geometry_blocked or raster_only or local_links_blocked),
        "topology_reason_code": topo["reason_code"],
        "source_errors": sorted(set(raw["extraction_errors"] + (
            [extraction["status"]] if extraction["status"] != "EXAMINED" else []))),
        "printed_scales": sorted({f'1:{item["denominator"]}' for item in lookup["PRINTED_SCALE"]}),
        "rendered_ocr_status": rendered_ocr.get("status", "NOT_REQUESTED"),
        "rendered_ocr_type_count": len(ocr_witnesses),
        "rendered_ocr_ambiguous_glyph_count": sum(w.get("status") == "AMBIGUOUS_GLYPH" for w in ocr_witnesses),
        "vector_text_status": vector_index.get("status", "NOT_INDEXED"),
        "vector_text_type_count": sum(bool(w.get("type_tag")) for w in vector_witnesses),
        "vector_text_ambiguous_count": len(_ambiguous_stroke_words(vector_index)),
        "native_pdf_word_count": raw["type_word_index"].get("source_word_count"),
        "native_type_word_count": len(word_witnesses),
    }


def _add_views(g, page, type_sources):
    digest, number = page["sha256"], page["page"]
    topo, by_kind = page["raw"]["detail_topology"], page["anchors_by_kind"]
    shapes = []
    for number_on_page, item in enumerate(topo["groups"], 1):
        if (item.get("document_id"), item.get("page")) != (page["document_id"], number):
            raise ValueError("Foreign PDF geometry group")
        role = item["role"]
        if role not in _VIEW_ROLES:
            continue  # Controls and unresolved non-view roles stay in topology receipt.
        anchor = {
            "anchor_id": _stable("PATH", digest, number, number_on_page),
            "document_id": page["document_id"], "page": number, "kind": "VECTOR_TOPOLOGY",
            "bbox_pt": item["bbox_pt"], "source_operator_ids": [op["source_id"] for op in item["source_operators"]],
            "coordinate_space": "unrotated_pdf_points", "source_sha256": digest, "source_name": page["source_name"],
        }
        raster = _overlapping_images(page, item["bbox_pt"]) if role == "CLOSED_CONTOUR" and page["linkable"] else []
        shape = g.node("VIEW", (digest, number, number_on_page), role,
                       "BLOCKED" if raster else item["status"], [anchor],
                       topology_role=role, bbox_pt=item["bbox_pt"], family="unknown",
                       geometry_candidate_id=item["candidate_id"], detail_code=None, printed_scale=None)
        if raster:
            g.issue(shape, "RASTER_VECTOR_OVERLAP", [anchor, *raster], status="BLOCKED")
        elif role == "CLOSED_CONTOUR" and item["status"] != "BLOCKED":
            shapes.append(shape)
        else:
            g.issue(shape, "NON_CONTOUR_TOPOLOGY", status=item["status"])
    headers = by_kind["DETAIL_TITLE"]
    # Do not use textual distance for either association across pages.
    linkable_shapes = shapes if page["linkable"] else []
    by_title, by_shape = _nearby(linkable_shapes, headers, limit=24)
    by_scale, scales_by_shape = _nearby(linkable_shapes, by_kind["PRINTED_SCALE"], limit=38)
    details = []
    for header in headers:
        groups = by_title[header["anchor_id"]]
        shape = groups[0] if len(groups) == 1 else None
        unique = shape and len(by_shape[shape["node_id"]]) == 1 and page["linkable"]
        code = header["detail"]
        family = _family_words(header.get("title"))
        types = _title_types(header.get("title"))
        tag = types[0] if len(types) == 1 else None
        if not unique:
            shape = g.node("VIEW", (digest, number, header["anchor_id"]), header["printed"],
                           "UNRESOLVED" if page["linkable"] else "BLOCKED",
                           [header], topology_role=None, bbox_pt=header["bbox_pt"],
                           family="unknown", detail_code=code, printed_scale=None)
            g.issue(shape, "DETAIL_GEOMETRY_AMBIGUOUS", [header, *(a for n in groups for a in n["anchors"])])
        else:
            shape["anchors"].append(header)
            shape["label"] = header["printed"]
            shape["detail_code"] = code
            if len(family) == 1:
                shape["status"] = "EXAMINED"  # candidate inspected, association is provisional
        declared_family = family[0] if len(family) == 1 else None
        implied_family = (_tag(tag) or (None, None))[1]
        shape.update(family=declared_family or "unknown", family_candidates=family, type_tag=tag, type_family_conflict=bool(
            implied_family and declared_family and implied_family != declared_family),
            reference_kind=_DETAIL_KIND.get(header["reference"], header["reference"]),
            detail_binding="PROPOSED_LOCAL_HEADING_CONTOUR" if unique else "UNRESOLVED_LOCAL_HEADING_CONTOUR")
        if not declared_family:
            g.issue(shape, "DETAIL_FAMILY_UNRESOLVED")
        if len(types) > 1:
            shape["status"] = "BLOCKED"
            g.issue(shape, "MULTIPLE_DETAIL_TYPE_MARKS", [header], status="BLOCKED")
        if shape["type_family_conflict"]:
            shape["status"] = "BLOCKED"
            g.issue(shape, "TYPE_FAMILY_CONFLICT", status="BLOCKED")
        if tag and declared_family and not shape["type_family_conflict"] and page["linkable"] and not page["authority_block"]:
            type_sources[(_document_scope(page), tag, declared_family)].append(shape)
        details.append(shape)
    for shape in shapes:
        if not shape["detail_code"] and page["page_role"] not in {"PLAN", "AXIS_PLAN"}:
            g.issue(shape, "UNTITLED_CONTOUR")
        scales = scales_by_shape[shape["node_id"]]
        headings = [a for a in shape["anchors"] if a["kind"] == "DETAIL_TITLE"]
        direction_agrees = not headings or not scales or headings[0]["direction"] == scales[0]["direction"]
        if len(scales) == 1 and len(by_scale[scales[0]["anchor_id"]]) == 1 and direction_agrees:
            shape["anchors"].append(scales[0])
            shape["printed_scale"] = "1:" + scales[0]["denominator"]
            shape["scale_status"] = "PRINTED_SCALE_UNCALIBRATED"
        elif scales:
            g.issue(shape, "AMBIGUOUS_VIEW_SCALE", scales, status="BLOCKED")
        elif shape["detail_code"]:
            g.issue(shape, "MISSING_VIEW_SCALE")
    # A standalone legacy title and its coarse index remain independent
    # evidence. It cannot authorize an exact cross-sheet callout target.
    for legacy in page["raw"]["detail_title_anchors"]:
        if any(_near(legacy["bbox_pt"], item["bbox_pt"], 0) for item in headers):
            continue
        anchor = {**legacy, "anchor_id": _stable("LEGACY_TITLE", digest, number, legacy["anchor_id"].split(":")[-1]),
                  "kind": "UNCODED_DETAIL_HEADING"}
        family = _family_words(legacy["title_preview"], sheet_kind=page["raw"].get("sheet_kind"))
        node = g.node("EVIDENCE", (anchor["anchor_id"],), legacy["title_preview"], "UNRESOLVED", [anchor],
                      family=family[0] if len(family) == 1 else "unknown")
        g.issue(node, "DETAIL_GEOMETRY_AMBIGUOUS")
    return shapes, details


def _mark_family(page, tag):
    implied = (_tag(tag) or (None, None))[1]
    if tag and re.fullmatch(r"B[0-9]+", tag) and page["sheet_kind"] == "floor_preparation_plan":
        return "architecture_finishes"
    if tag and re.fullmatch(r"T[0-9]+", tag) and page["sheet_kind"] in {"foundation_plan", "excavation_plan"}:
        return "foundation"
    return implied


def _source_word_anchor(page, mark, kind):
    ordinal = mark.get("source_word_index")
    if ordinal is None:
        ordinal = [operator.split(":d", 1)[-1] for operator in mark["source_operator_ids"]]
    return {
        **mark, "kind": kind, "source_sha256": page["sha256"], "source_name": page["source_name"],
        "raw_token": mark.get("raw_token") or mark.get("source_token") or mark.get("text"),
        "normalized_tag": mark.get("type_tag"),
        "coordinate_space": "unrotated_pdf_points",
        "anchor_id": _stable(kind, page["sha256"], page["page"], ordinal),
    }


def _add_local_evidence(g, page, shapes):
    raw, digest, number = page["raw"], page["sha256"], page["page"]
    words = []
    declarations = page["anchors_by_kind"]
    structured = [*declarations["DETAIL_TITLE"], *declarations["INSTANCE"], *declarations["SCHEDULE_ROW"]]
    for mark in raw["type_word_index"]["type_word_witnesses"]:
        if mark["title_anchor_ids"] or (page["linkable"] and structured and
                any(_near(mark["bbox_pt"], line["bbox_pt"], 0) for line in structured)):
            continue
        words.append(_source_word_anchor(page, mark, "TYPE_WORD"))
    scanned = raw.get("vector_type_word_index") or {}
    undecided = _ambiguous_stroke_words(scanned)
    for mark in [*scanned.get("type_word_witnesses", ()), *undecided]:
        if ((mark.get("document_id"), mark.get("page")) != (page["document_id"], number)
                or mark.get("financially_payable") is not False
                or not _box(mark.get("bbox_pt")) or not mark.get("source_operator_ids")):
            raise ValueError("Foreign or unsupported PDF stroke word evidence")
        item = _source_word_anchor(page, mark, "VECTOR_STROKE_TYPE_WORD")
        if mark.get("reason") in _AMBIGUOUS_STROKE_REASONS:
            item.update(status="AMBIGUOUS_GLYPH", type_tag=None, normalized_tag=None,
                        glyph_ambiguity_reason=mark["reason"])
        words.append(item)
    # OCR is deliberately separate from the authoritative native text index.
    # Unknown/duplicate OCR words are still preserved in the recovery receipt,
    # but cannot fabricate another member or a type-definition node.
    ocr = raw.get("rendered_type_word_index") or {}
    for mark in ocr.get("type_word_witnesses", ()):
        if (mark.get("document_id") != page["document_id"] or mark.get("page") != number
                or mark.get("financially_payable") is not False
                or mark.get("source_sha256", digest) != digest
                or mark.get("source_quality") != "RENDERED_OCR_NOT_VERIFIED"):
            raise ValueError("Foreign or unsupported PDF OCR evidence")
        if mark.get("status") == "OCR_DUPLICATE_NATIVE_TYPE_MARK":
            continue
        if mark.get("status") not in {"OCR_TYPE_MARK_UNVERIFIED", "AMBIGUOUS_GLYPH"}:
            raise ValueError("Invalid OCR type witness status")
        words.append(_source_word_anchor(page, mark, "RENDERED_OCR_TYPE_WORD"))
    reviewable_words = [w for w in words if w.get("type_tag") and w.get("status") != "AMBIGUOUS_GLYPH"]
    by_word, by_shape = _nearby(shapes if page["linkable"] else [], reviewable_words, limit=16)
    for word in words:
        tag = word.get("type_tag")
        family = _mark_family(page, tag)
        if word.get("status") == "AMBIGUOUS_GLYPH":
            evidence = g.node("EVIDENCE", (word["anchor_id"],), word.get("raw_token"), "BLOCKED", [word],
                              family="unknown", type_tag=None, evidence_quality="AMBIGUOUS_GLYPH")
            g.issue(evidence, "AMBIGUOUS_GLYPH", status="BLOCKED")
            continue
        options = by_word[word["anchor_id"]]
        unique = len(options) == 1 and len(by_shape[options[0]["node_id"]]) == 1
        code = ("UNBOUND_LOCAL_TYPE_MARK" if not options else "AMBIGUOUS_LOCAL_TYPE_MARK" if not unique else
                "TYPE_FAMILY_CONFLICT" if family and options[0]["family"] not in {"unknown", family} else None)
        status = ("BLOCKED" if not page["linkable"] or (options and code) else "UNRESOLVED")
        is_ocr = word["kind"] == "RENDERED_OCR_TYPE_WORD"
        is_vector = word["kind"] == "VECTOR_STROKE_TYPE_WORD"
        evidence = g.node("EVIDENCE", (word["anchor_id"],), tag, status, [word],
                          family=family or "unknown", type_tag=tag,
                          evidence_quality=("RENDERED_OCR_NOT_VERIFIED" if is_ocr else
                                            "VECTOR_GLYPH_WITNESS" if is_vector else
                                            "PDF_NATIVE_WORD_BBOX_NOT_MEMBER"))
        if is_ocr:
            g.issue(evidence, "RENDERED_OCR_TYPE_UNVERIFIED", status="UNRESOLVED")
        refs = [word, *(a for option in options for a in option["anchors"])]
        if code:
            g.issue(evidence, code, refs, status=status)
        if options:
            g.edge("RENDERED_OCR_TYPE_NEAR_VIEW" if is_ocr else
                   "VECTOR_TYPE_NEAR_VIEW" if is_vector else "TYPE_WORD_NEAR_VIEW",
                   evidence, options[0] if unique else None, refs,
                   status="REJECTED" if code == "TYPE_FAMILY_CONFLICT" else "AMBIGUOUS" if code else "PROPOSED",
                   reason=_REASONS[code][0] if code else (
                       "برچسب OCR نامطمئن و مجاورت شکل؛ نیازمند تأیید مستقل" if is_ocr else
                       "جای واژه و شکل در مختصات یک صفحه"),
                   code=code, candidates=[option["node_id"] for option in options])
    for note in raw["note_anchors"]:
        anchor = {**note, "kind": "NOTE", "anchor_id": _stable("NOTE", digest, number, note["anchor_id"].split(":")[-1])}
        node = g.node("EVIDENCE", (anchor["anchor_id"],), note["text_preview"], "UNRESOLVED", [anchor])
        g.edge("NOTE_ON_SHEET", node, page["node"], [anchor], status="PROPOSED",
               reason="محل یادداشت در سند؛ کاربرد برای عضو نیازمند ارجاع صریح است")
        g.issue(node, "NOTE_APPLICABILITY_UNRESOLVED")


def _add_instances(g, pages, shapes, type_nodes):
    proposals, local_nodes, axes_levels = defaultdict(list), {}, defaultdict(list)
    for key, page in pages.items():
        witnesses = page["anchors_by_kind"]
        scope = _document_scope(page)
        for kind, valid_roles in (("AXIS", {"AXIS_PLAN"}), ("LEVEL", {"SECTION", "ELEVATION", "SCHEDULE"})):
            if page["page_role"] not in valid_roles or not page["linkable"]:
                continue
            for anchor in witnesses[kind]:
                code = anchor["code"].replace(" ", "")
                witness = g.node(kind, (anchor["anchor_id"],), code, "EXAMINED", [anchor])
                axes_levels[(scope, kind, code)].append((key, witness))
        labels = witnesses["INSTANCE"]
        candidates, reverses = _nearby(shapes[key] if page["linkable"] else [], labels, limit=20)
        for label in labels:
            near = candidates[label["anchor_id"]]
            shape = near[0] if len(near) == 1 and len(reverses[near[0]["node_id"]]) == 1 else None
            # Identical explicit member labels only deduplicate in the same controlled
            # issue and level; legacy/unknown/changed documents do not participate.
            mergeable = page["authority"] and not page["authority_block"] and page["linkable"]
            identity = (scope, label["member"], label["level"]) if mergeable else (label["anchor_id"],)
            if near and not shape:
                label["ambiguous_geometry"] = True
            proposals[identity].append((key, label, shape))
    for identity, entries in proposals.items():
        marks = {(entry["axis"].replace(" ", ""), _type(entry["tag"])) for _, entry, _ in entries}
        conflict = len(marks) > 1
        axis, tag = next(iter(marks)) if not conflict else (None, None)
        _, sample, _ = entries[0]
        supported = [(key, form) for key, _, form in entries if (
            form and pages[key]["page_role"] == "PLAN" and pages[key]["linkable"] and not pages[key]["authority_block"])]
        bound = bool(supported) and not conflict
        family = (_tag(tag) or (None, None))[1]
        blocked = conflict or any(pages[key]["authority_block"] or not pages[key]["linkable"] or
                                  label.get("ambiguous_geometry") for key, label, _ in entries)
        instance = g.node("INSTANCE_CANDIDATE", identity, sample["member"],
                          "BLOCKED" if blocked else "EXAMINED" if bound else "UNRESOLVED",
                          [record for _, record, _ in entries], type_tag=tag, family=family or "unknown",
                          level=sample["level"], axis=axis, identity_witness_count=len(entries),
                          plan_geometry_present=bound, **_QUANTITY_PENDING)
        for key, entry, form in entries:
            local_nodes.setdefault((key, entry["member"]), {})[instance["node_id"]] = instance
            if form and pages[key]["linkable"]:
                g.edge("INSTANCE_SHOWN_IN_VIEW", instance, form, [entry, form["anchors"][0]],
                       status="BLOCKED" if blocked else "PROPOSED",
                       reason="شاهد متن و شکل در مختصات محلی همین صفحه")
        if conflict:
            g.issue(instance, "INSTANCE_SCOPE_CONFLICT", status="BLOCKED")
            continue
        if not bound:
            g.issue(instance, "INSTANCE_PLAN_GEOMETRY_MISSING")
        if any(label.get("ambiguous_geometry") for _, label, _ in entries):
            g.issue(instance, "INSTANCE_GEOMETRY_AMBIGUOUS", status="BLOCKED")
        page = pages[entries[0][0]]
        scope = _document_scope(page)
        if not page["authority"] or page["authority_block"]:
            g.issue(instance, page["authority_block"] or "UNVERIFIED_DOCUMENT_SCOPE", status="BLOCKED")
        definition = type_nodes.get((scope, tag, family))
        if definition:
            g.edge("INSTANCE_TYPE_CANDIDATE", instance, definition, instance["anchors"],
                   status="PROPOSED", reason="شناسه تیپ چاپ‌شده در همان مجموعه سند")
        plan_keys = {k for k, _ in supported}
        for kind, code in (("AXIS", axis), ("LEVEL", sample["level"])):
            options = [(k, witness) for k, witness in axes_levels[(scope, kind, code)]
                       if k not in plan_keys and bound and not blocked and _scope_disagreement(page, pages[k]) is None]
            if not options:
                g.issue(instance, "MISSING_INDEPENDENT_" + kind)
            for _, target in options:
                g.edge("AT_" + kind, instance, target, [*instance["anchors"], *target["anchors"]],
                       status="VALIDATED_REFERENCE", reason="آکس یا تراز صریح از صفحه مستقل همان ابلاغ")
    return local_nodes


def _add_callouts(g, pages, details, local_nodes):
    by_reference = defaultdict(list)
    for key, page_details in details.items():
        if pages[key]["sheet_id"]:
            for item in page_details:
                by_reference[(pages[key]["sheet_id"], item["reference_kind"], item["detail_code"])].append((key, item))
    selected = defaultdict(list)
    for key, page in pages.items():
        witnesses = page["anchors_by_kind"]
        for callout in [*witnesses["CALLOUT"], *witnesses["SCHEDULE_ROW"]]:
            member = callout.get("member")
            objects = list(local_nodes.get((key, member), {}).values()) if member else []
            source = objects[0] if len(objects) == 1 else page["node"]
            ref_kind = _DETAIL_KIND.get(callout["reference"], callout["reference"])
            matches = by_reference[(callout["sheet"], ref_kind, callout["detail"])]
            eligible = [(k, n) for k, n in matches if _scope_disagreement(page, pages[k]) is None]
            # Prefer the controlled issue, but retain mismatched candidates in the receipt.
            options = eligible or matches
            target = options[0][1] if len(options) == 1 else None
            reason, status = None, "VALIDATED_REFERENCE"
            if callout["kind"] == "SCHEDULE_ROW" and page["page_role"] != "SCHEDULE":
                reason = "SCHEDULE_CONTEXT_UNVERIFIED"
            elif member and len(objects) != 1:
                reason = "REFERENCE_SUBJECT_NOT_FOUND"
            elif not matches:
                reason = "REFERENCE_TARGET_NOT_FOUND"
            elif len(options) > 1:
                reason, status = "AMBIGUOUS_REFERENCE_TARGET", "AMBIGUOUS"
            else:
                other = pages[options[0][0]]
                reason = _scope_disagreement(page, other)
                if not reason and member and (not source.get("plan_geometry_present") or source["status"] == "BLOCKED"):
                    reason = "REFERENCE_SOURCE_UNRESOLVED"
                if not reason:
                    tag = _type(callout.get("tag")) or source.get("type_tag")
                    if target["type_family_conflict"] or (
                            tag and target.get("type_tag") and target["type_tag"] != tag):
                        reason, status = "TYPE_FAMILY_CONFLICT", "REJECTED"
                    elif not page["linkable"] or not other["linkable"] or target["status"] != "EXAMINED":
                        reason = "REFERENCE_TARGET_UNRESOLVED"
                    elif tag and not target.get("type_tag"):
                        reason = "MISSING_TARGET_TYPE"
                elif reason == "UNVERIFIED_DOCUMENT_SCOPE" and key[0] == options[0][0][0]:
                    status = "PROPOSED"
            refs = [callout, *(a for _, item in options for a in item["anchors"])]
            if reason:
                status = "BLOCKED" if status == "VALIDATED_REFERENCE" else status
                g.issue(source, reason, refs, status="BLOCKED")
            relationship = "SCHEDULE_DETAIL_CALLOUT" if callout["kind"] == "SCHEDULE_ROW" else "DETAIL_CALLOUT"
            relation = g.edge(relationship, source, target, refs, status=status, code=reason,
                              reason=_REASONS[reason][0] if reason else "شیت و کد ارجاع صریح در نسخهٔ حاکم ثبت‌شده",
                              candidates=[item["node_id"] for _, item in matches])
            if not reason and (member or callout["kind"] == "SCHEDULE_ROW"):
                tag = _type(callout.get("tag")) or source["type_tag"]
                level = callout.get("level") or source.get("level")
                # At a named level, plan and table witnesses for the same
                # type must agree before an equivalent detail link is usable.
                identity = (_document_scope(page), tag, level, ref_kind, None if level else source["node_id"])
                selected[identity].append((source, relation))
    for links in selected.values():
        by_member = defaultdict(list)
        schedules = []
        for subject, edge in links:
            if edge["relationship"] == "SCHEDULE_DETAIL_CALLOUT":
                schedules.append((subject, edge))
            else:
                by_member[subject["node_id"]].append((subject, edge))
        related = {edge["edge_id"]: (subject, edge)
                   for group in [schedules, *by_member.values()]
                   if len({edge["target_id"] for _, edge in group}) > 1 for subject, edge in group}
        schedule_targets = {edge["target_id"] for _, edge in schedules}
        for group in by_member.values():
            if schedule_targets and {edge["target_id"] for _, edge in group} != schedule_targets:
                related.update((edge["edge_id"], (subject, edge)) for subject, edge in [*group, *schedules])
        code = "CONFLICTING_DETAIL_REFERENCES"
        refs = {a["anchor_id"]: a for _, edge in related.values() for a in edge["anchors"]}
        for subject, edge in related.values():
            edge.update(status="AMBIGUOUS", reason_code=code, reason=_REASONS[code][0])
            g.issue(subject, code, refs.values(), status="BLOCKED")


def _column_detail_marks(g, pages, report):
    hints = defaultdict(list)
    dimensions = defaultdict(list)
    for item in report.get("member_type_candidates", ()):
        if item["status"] == "TYPE_DIMENSION_CANDIDATE" and _box(item.get("dimension_bbox_pt")):
            dimensions[(item["document_id"], item["page"], item["tag"])].append(item)
    for key, page in pages.items():
        if page["sheet_kind"] != "column_detail" or not page["linkable"] or page["authority_block"]:
            continue
        for mark in page["raw"]["type_word_index"]["type_word_witnesses"]:
            tag = mark["type_tag"]
            if not re.fullmatch(r"C[1-9][0-9]{0,2}", tag):
                continue
            anchor = _source_word_anchor(page, mark, "COLUMN_DETAIL_TYPE_MARK")
            same_type_dims = dimensions[(*key, tag)]
            refs = [anchor]
            for item in same_type_dims:
                refs.append({
                    "anchor_id": _stable("PRINTED_DIMENSION", page["sha256"], key[1], tag, item["dimension_bbox_pt"]),
                    "document_id": key[0], "page": key[1], "kind": "NATIVE_TYPE_DETAIL_DIMENSION",
                    "source_sha256": page["sha256"], "source_name": page["source_name"],
                    "bbox_pt": item["dimension_bbox_pt"], "raw_token": item["dimension_text"],
                    "dimension_m": item["dimension_m"], "dimension_kind": item["dimension_kind"],
                })
            node = g.node("EVIDENCE", (anchor["anchor_id"],), tag, "EXAMINED", refs, family="column",
                          type_tag=tag, evidence_quality="PRINTED_COLUMN_DETAIL_TYPE", dimension_scope="TYPE_DETAIL_ONLY")
            hints[(key[0], tag)].append((key, node))
    return hints


def _column_plan_locations(g, pages, report, detail_hints):
    positions, axes = {}, {}
    axis_grids = {(x["document_id"], x["page"]): x for x in report.get("vector_grid_summaries", ())}
    ledger = {x["candidate_id"]: x for x in report.get("column_position_ledger", {}).get("positions", ())}
    for candidate in report.get("grid_location_candidates", ()):
        if not candidate.get("column_context_candidate"):
            continue
        key = candidate["document_id"], candidate["page"]
        page = pages[key]
        row, col = candidate["row"], candidate["column"]
        position = (*key, row, col)
        if position in positions:
            continue
        x, y = candidate["x_pt"], candidate["y_pt"]
        bounds = [x - 1, y - 1, x + 1, y + 1]
        anchor = {"anchor_id": _stable("GRID_LOC", page["sha256"], key[1], row, col),
                  "document_id": key[0], "page": key[1], "kind": "GRID_LOCATION_CANDIDATE",
                  "source_sha256": page["sha256"], "source_name": page["source_name"], "bbox_pt": bounds,
                  "independent_axis_grid_witness": candidate.get("independent_axis_grid_witness")}
        evidenced = ledger.get(candidate["candidate_id"])
        tag = evidenced["proposed_type"] if evidenced else candidate.get("suggested_type")
        anchors = [anchor]
        glyph = evidenced and evidenced["type_evidence"]
        if glyph and _box(glyph.get("bbox_pt")):
            anchors.append({
                **glyph, "anchor_id": _stable("COLUMN_PLAN_GLYPH", page["sha256"], key[1], row, col),
                "kind": "COLUMN_PLAN_GLYPH", "document_id": key[0], "page": key[1],
                "source_sha256": page["sha256"], "source_name": page["source_name"], "normalized_tag": tag,
            })
        status = "UNRESOLVED" if page["linkable"] and not page["authority_block"] else "BLOCKED"
        node = g.node("INSTANCE_CANDIDATE", (anchor["anchor_id"],), "موقعیت احتمالی ستون", status,
                      anchors, family="column", type_tag=tag, level=None, identity_witness_count=len(anchors),
                      location_pt=[x, y], grid_row=row, grid_column=col, **_QUANTITY_PENDING)
        positions[position] = node
        g.edge("GRID_LOCATION_ON_SHEET", node, page["node"], anchors, status="PROPOSED" if status != "BLOCKED" else status,
               reason="مختصات محلی و شاهد نماد؛ تراز اجرایی به مدرک مستقل نیاز دارد")
        g.issue(node, "LEGACY_GRID_LEVEL_UNKNOWN")
        g.issue(node, "MISSING_DIMENSION_EVIDENCE")
        if not evidenced or status == "BLOCKED":
            continue
        axis = evidenced["axis_evidence"]
        if axis:
            axis_key = axis["document_id"], axis["page"]
            axis_page = pages[axis_key]
            grid = axis_grids.get(axis_key)
            if (grid and axis_page["linkable"] and not axis_page["authority_block"]
                    and 1 <= col <= len(grid["axes_x_pt"]) and 1 <= row <= len(grid["levels_y_pt"])):
                cx, cy = grid["axes_x_pt"][col-1], grid["levels_y_pt"][row-1]
                axis_id = (*axis_key, row, col)
                if axis_id not in axes:
                    axis_anchor = {
                        "anchor_id": _stable("INDEPENDENT_GRID", axis_page["sha256"], axis_key[1], row, col),
                        "document_id": axis_key[0], "page": axis_key[1], "kind": "INDEPENDENT_GRID_POSITION",
                        "bbox_pt": [cx-1, cy-1, cx+1, cy+1], "source_sha256": axis_page["sha256"],
                        "source_name": axis_page["source_name"], "grid_row": row, "grid_column": col,
                    }
                    axes[axis_id] = g.node("AXIS", (axis_anchor["anchor_id"],), "آکس مستقل", "EXAMINED", [axis_anchor])
                target = axes[axis_id]
                node["independent_axis_reference_found"] = True
                g.edge("COLUMN_AXIS_CORROBORATION", node, target, [*anchors, *target["anchors"]], status="PROPOSED",
                       reason="انطباق هندسی شبکه در دو شیت مستقل از همان PDF")
        match = detail_hints.get((key[0], tag), ())
        if len(match) == 1 and match[0][0] != key:
            _, target = match[0]
            g.edge("COLUMN_DETAIL_TYPE_REFERENCE", node, target, [*anchors, *target["anchors"]], status="PROPOSED",
                   reason="برچسب تیپ موضعی پلان و مرجع یکتای هم‌نام در شیت دیتیلِ همان فایل")
        elif tag:
            g.issue(node, "COLUMN_DETAIL_MARK_UNRESOLVED")
    return positions


def _inside(bounds, region):
    return all(bounds[i] >= region[i] and bounds[i+2] <= region[i+2] for i in (0, 1))


def _unique_plan_location(bounds, positions, candidate):
    center = [(bounds[i] + bounds[i+2]) / 2 for i in (0, 1)]
    best = dist(center, candidate["location_pt"])
    return best <= 45 and all(
        other is candidate or dist(center, other["location_pt"]) > best + 4 for other in positions
    )


def _add_column_id_review(g, pages, positions, detail_hints, review):
    if review is None:
        return []
    checked = validate_pdf_member_review(review)
    doc_ids = {p["document_id"] for p in pages.values() if p["sha256"] == checked["source_sha256"]}
    if len(doc_ids) != 1:
        raise ValueError("PDF member review source hash does not match the selected documents")
    doc_id = doc_ids.pop()
    plan_locations = defaultdict(list)
    for position, node in positions.items():
        plan_locations[position[:2]].append(node)
    rows, plan_observations, disputes = [], {}, []
    for group in checked["groups"]:
        tag, detail = group["type_tag"], group["detail"]
        detail_key = doc_id, detail["page"]
        detail_page = pages.get(detail_key)
        box = detail["bbox_pt"]
        if not detail_page or not _inside(box, detail_page["source_bbox_pt"]):
            raise ValueError("PDF member review detail is outside source bounds")
        if detail_page["authority_block"] or not detail_page["linkable"]:
            raise ValueError("PDF member review detail source is blocked")
        candidates = [n for key, n in detail_hints.get((doc_id, tag), ())
                      if key == detail_key and _inside(n["anchors"][0]["bbox_pt"], box)]
        if len(candidates) != 1:
            raise ValueError("PDF member review detail type is not unique in its row bounds")
        target = candidates[0]
        plan_mark_nodes, detail_marks = {}, {}
        for mark in group["plan"]:
            key = doc_id, mark["page"]
            plan_page = pages.get(key)
            candidate = positions.get((*key, mark["grid_row"], mark["grid_column"]))
            mark_box = mark["bbox_pt"]
            mark_id = mark["printed_id"]
            if (not candidate or candidate["type_tag"] != tag or candidate["status"] == "BLOCKED"
                    or not candidate.get("independent_axis_reference_found")
                    or not plan_page or mark["page"] == detail["page"]
                    or not _inside(mark_box, plan_page["source_bbox_pt"])
                    or not _unique_plan_location(mark_box, plan_locations[key], candidate)):
                raise ValueError("PDF member review plan mark does not match a source location or bounds")
            anchor = {
                **mark, "anchor_id": _stable("PLAN_PRINTED_MEMBER_ID", checked["source_sha256"], *key[1:], mark_id),
                "kind": "VISUALLY_READ_PLAN_MEMBER_ID", "document_id": doc_id,
                "source_sha256": checked["source_sha256"], "source_name": plan_page["source_name"],
                "raw_token": mark_id, "type_tag": tag, "coordinate_space": "unrotated_pdf_points",
            }
            plan_mark_nodes[mark_id] = (candidate, anchor)
            plan_observations[(mark["page"], mark_id)] = (candidate, anchor)
        for mark in detail["marks"]:
            if not _inside(mark["bbox_pt"], box):
                raise ValueError("PDF member review identifier is outside its detail row bounds")
            mid = mark["printed_id"]
            detail_marks[mid] = {
                **mark, "anchor_id": _stable("DETAIL_PRINTED_MEMBER_ID", checked["source_sha256"], detail["page"], tag, mid),
                "kind": "VISUALLY_READ_DETAIL_MEMBER_ID", "document_id": doc_id, "page": detail["page"],
                "source_sha256": checked["source_sha256"], "source_name": detail_page["source_name"],
                "raw_token": mid, "type_tag": tag, "coordinate_space": "unrotated_pdf_points",
            }
        all_anchors = [*target["anchors"], *(a for _, a in plan_mark_nodes.values()), *detail_marks.values()]
        shared = sorted(plan_mark_nodes.keys() & detail_marks.keys())
        plan_only = sorted(plan_mark_nodes.keys() - detail_marks.keys()) if detail_marks else []
        detail_only = sorted(detail_marks.keys() - plan_mark_nodes.keys())
        if len(plan_mark_nodes) != detail["printed_count"] or detail_marks and len(detail_marks) != detail["printed_count"]:
            status = "BLOCKED_PRINTED_MEMBER_COUNT_CONFLICT"
        elif not detail_marks:
            status = "TYPE_COUNT_ONLY"
        elif plan_only or detail_only:
            status = "BLOCKED_PRINTED_MEMBER_ID_CONFLICT"
        else:
            status = "CORROBORATED_DRAWN_IDS"
        blocked = status.startswith("BLOCKED")
        rows.append({
            "type_tag": tag, "status": status, "plan_mark_count": len(plan_mark_nodes),
            "detail_printed_count": detail["printed_count"], "detail_id_count": len(detail_marks),
            "shared_printed_ids": shared, "plan_only_printed_ids": plan_only, "detail_only_printed_ids": detail_only,
            "detail_page": detail["page"], "anchors": all_anchors, "verified_physical_member_count": 0,
            "financially_payable": False,
        })
        if blocked:
            g.issue(target, status, all_anchors, status="BLOCKED")
            disputes.append((group["plan"][0]["page"], tag, set(plan_mark_nodes) | set(detail_marks),
                             target, all_anchors))
        for mid, (candidate, anchor) in plan_mark_nodes.items():
            candidate["anchors"].append(anchor)
            candidate["printed_member_id"] = mid
            candidate["printed_id_review_status"] = status
            if blocked:
                candidate["status"] = "BLOCKED"
                g.issue(candidate, status, [anchor, *target["anchors"], *detail_marks.values()], status="BLOCKED")
            refs = [anchor, *target["anchors"]]
            if mid in detail_marks:
                refs.append(detail_marks[mid])
            if blocked or mid in detail_marks:
                edge = g.edge("PLAN_DETAIL_PRINTED_MEMBER_ID", candidate, target, refs,
                              status="BLOCKED" if blocked else "PROPOSED",
                              reason=_REASONS[status][0] if blocked else "تطبیق مستقیم شناسه‌های خوانده‌شده از پلان و دیتیل همان فایل",
                              code=status if blocked else None)
                edge["printed_id_review_status"] = status
    # A disputed schedule can name a position which the plan assigns to a
    # different type. Apply the conflict only after all plan groups are mapped.
    for plan_page, tag, printed_ids, target, anchors in disputes:
        reason = f"{tag}_PRINTED_SCHEDULE_CONFLICT"
        root = {"reason_code": reason, "type_tag": tag, "anchors": list(anchors)}
        for mid in sorted(printed_ids):
            bound = plan_observations.get((plan_page, mid))
            if bound is None:
                continue
            candidate, own_anchor = bound
            refs = [own_anchor, *anchors]
            candidate["status"] = "BLOCKED"
            candidate.setdefault("printed_schedule_conflicts", []).append({**root, "anchors": refs})
            g.issue(candidate, "DESIGN_AUTHORITY_REQUIRED", refs, status="BLOCKED")
            g.edge("PRINTED_SCHEDULE_CONFLICT", candidate, target, refs, status="BLOCKED", code=reason,
                   reason=_REASONS["DESIGN_AUTHORITY_REQUIRED"][0])
    return rows


def _add_structural_plan_reviews(g, pages):
    reviews = build_pdf_structural_plan_reviews(pages)
    for review in reviews:
        source = review["anchors"][0]
        page_key = source["document_id"], source["page"]
        sheet = pages[page_key]["node"]
        others = {(a["document_id"], a["page"]) for a in review["anchors"]} - {page_key}
        target = pages[next(iter(others))]["node"] if len(others) == 1 else None
        node = g.node("STRUCTURAL_PLAN_REVIEW", (review["review_id"],), review["type_tag"] or review["role"],
                      review["status"], review["anchors"], family=review["family"],
                      type_tag=review["type_tag"], reason_code=review["reason_code"], reason=review["reason"])
        edge = g.edge("STRUCTURAL_SHEET_REVIEW", sheet, node, review["anchors"],
                      status="BLOCKED" if review["status"] == "BLOCKED" else "PROPOSED",
                      code=review["reason_code"], reason=review["reason"])
        review.update(node_id=node["node_id"], source_id=sheet["node_id"],
                      target_id=target["node_id"] if target else None, edge_ids=[edge["edge_id"]])
    return reviews


def build_pdf_detail_evidence_graph(report, page_evidence, *, revision_registry=None, member_review=None,
                                    beam_profile_witnesses=None, beam_axis_labels=None,
                                    beam_detail_profile_witnesses=None, max_records=80000):
    """Combine immutable PDF primitives with explicit, issue-scoped source relationships."""
    authorities = _parse_registry(revision_registry)
    documents = {doc["document_id"]: doc for doc in report["documents"]}
    digests = {doc["sha256"] for doc in documents.values()}
    if len(documents) != len(report["documents"]) or len(digests) != len(documents):
        raise ValueError("Duplicate PDF source identity")
    if set(authorities) - digests:
        raise ValueError("PDF revision registry SHA does not match the selected sources")
    g = _Graph(max_records)
    document_nodes = {}
    for doc in documents.values():
        auth = authorities.get(doc["sha256"])
        document_nodes[doc["document_id"]] = g.node(
            "DOCUMENT", (doc["sha256"],), doc["source_name"], "EXAMINED" if auth else "UNRESOLVED",
            document_id=doc["document_id"], page_count=doc["page_count"], authority=auth,
            metadata=doc.get("metadata", {}))
    expected = {(doc_id, index) for doc_id, doc in documents.items()
                for index in range(1, doc["page_count"] + 1)}
    actual = [(item["document_id"], item["page"]) for item in page_evidence]
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError("Missing, duplicate or foreign PDF evidence page")
    pages, shapes, details = {}, {}, {}
    type_sources = defaultdict(list)
    for raw in page_evidence:
        key = (raw["document_id"], raw["page"])
        doc = documents[key[0]]
        page = _page_record(g, doc, raw, authorities.get(doc["sha256"]))
        pages[key] = page
        g.edge("DOCUMENT_SHEET", document_nodes[key[0]], page["node"], page["node"]["anchors"],
               status="VALIDATED_REFERENCE", reason="شماره صفحه در فایل منبع")
        shapes[key], details[key] = _add_views(g, page, type_sources)
        _add_local_evidence(g, page, shapes[key])
    # Two CURRENT pages claiming the same sheet ID in one registered issue
    # cannot both act as the governing source. Veto them before constructing
    # member identities or accepting cross-sheet references, even if only one
    # happens to contain the requested detail callout.
    current_sheets = defaultdict(list)
    for key, page in pages.items():
        auth = page["authority"]
        if (auth and auth["status"] == "CURRENT" and page["sheet_id"]
                and not page["authority_block"]):
            current_sheets[(auth["project_id"], auth["issue_id"], page["sheet_id"])].append(key)
    for candidates in current_sheets.values():
        if len(candidates) <= 1:
            continue
        for key in candidates:
            page = pages[key]
            page["authority_block"] = "DUPLICATE_CURRENT_SHEET_ID"
            page["status"] = "BLOCKED"
            page["authority_status"] = "DUPLICATE_CURRENT_SHEET_ID"
            page["node"]["status"] = "BLOCKED"
            g.issue(page["node"], "DUPLICATE_CURRENT_SHEET_ID", status="BLOCKED")
    type_nodes = {}
    for identity, views in type_sources.items():
        _, tag, family = identity
        anchors = [anchor for view in views for anchor in view["anchors"] if anchor["kind"] == "DETAIL_TITLE"]
        definition = g.node("TYPE_DEFINITION", identity, tag, "EXAMINED", anchors, family=family, type_tag=tag)
        type_nodes[identity] = definition
        for view in views:
            g.edge("DETAIL_TYPE_DEFINITION", view, definition, view["anchors"],
                   status="PROPOSED", reason="تیپ در عنوان دیتیل ثبت شده است")
    local_instances = _add_instances(g, pages, shapes, type_nodes)
    _add_callouts(g, pages, details, local_instances)
    detail_hints = _column_detail_marks(g, pages, report)
    positions = _column_plan_locations(g, pages, report, detail_hints)
    member_review_groups = _add_column_id_review(g, pages, positions, detail_hints, member_review)
    occurrence_reviews = build_pdf_occurrence_reviews(pages, g.nodes, g.edges)
    structural_plan_reviews = _add_structural_plan_reviews(g, pages)
    beam_profile_reviews = correlate_pdf_beam_profile_witnesses(pages, structural_plan_reviews, beam_profile_witnesses)
    for row in beam_profile_reviews:
        first = row["anchors"][0]
        sheet = pages[(first["document_id"], first["page"])]["node"]
        node = g.node("BEAM_PROFILE_REVIEW", (row["review_id"],), row["profile_text"],
                      "BLOCKED" if row["status"] == "BLOCKED" else "UNRESOLVED", row["anchors"],
                      family="beam", evidence_quality="VISUAL_REVIEW_NOT_ENGINEERING_APPROVAL",
                      physical_member_verified=False, member_quantity=None)
        edge = g.edge("BEAM_PROFILE_NEAR_VECTOR_REGION", sheet, node, row["anchors"],
                      status="BLOCKED" if row["status"] == "BLOCKED" else "PROPOSED",
                      code=row["reason_code"], reason="مجاورت هندسی؛ انتساب اجرایی تأیید نشده")
        row.update(node_id=node["node_id"], source_id=sheet["node_id"], edge_ids=[edge["edge_id"]])
    independent_axis_crosscheck = None
    if beam_axis_labels is not None:
        grids = [grid for grid in report.get("beam_axis_grid_candidates", ())
                 if grid.get("status") == "PROPOSED_UNLABELED_AXIS_GRID"]
        if len(grids) != 1 or not beam_profile_witnesses or len(beam_profile_reviews) != len(beam_profile_witnesses):
            raise ValueError("Unique independent axis grid and beam visual observations required")
        grid = grids[0]
        axis_key = (grid["document_id"], grid["page"])
        beam_key = (grid["document_id"], beam_axis_labels.get("beam_page"))
        if (axis_key not in pages or beam_key not in pages or
                pages[axis_key]["sha256"] != grid["source_sha256"] or
                pages[beam_key]["sha256"] != grid["source_sha256"] or
                pages[axis_key]["sheet_kind"] != "axis_plan" or
                pages[beam_key]["sheet_kind"] != "beam_layout_plan" or
                pages[axis_key]["authority_block"] or pages[beam_key]["authority_block"] or
                not pages[axis_key]["linkable"] or not pages[beam_key]["linkable"]):
            raise ValueError("Foreign, unclassified or blocked independent axis/beam sheet")
        independent_axis_crosscheck = reconcile_pdf_beam_grid_labels(
            grid, beam_axis_labels, beam_profile_witnesses,
        )
        if independent_axis_crosscheck["status"].startswith("BLOCKED_"):
            for review in beam_profile_reviews:
                review["spatial_reason_code"] = review["reason_code"]
                review["status"] = "BLOCKED"
                review["reason_code"] = "BEAM_AXIS_PRINTED_CHAIN_BLOCKED"
                g.nodes[review["node_id"]]["status"] = "BLOCKED"
        else:
            if len(independent_axis_crosscheck["profiles"]) != len(beam_profile_reviews):
                raise ValueError("Axis profile evidence count mismatch")
            for row, match in zip(beam_profile_reviews, independent_axis_crosscheck["profiles"], strict=True):
                row["independent_axis_status"] = match["status"]
                row["independent_axis_review_id"] = match["review_id"]
                row["independent_axis_page"] = grid["page"]
                if match["status"].startswith("BLOCKED_"):
                    row["spatial_reason_code"] = row["reason_code"]
                    row["status"] = "BLOCKED"
                    row["reason_code"] = "BEAM_AXIS_LOCATION_REVIEW_BLOCKED"
                    g.nodes[row["node_id"]]["status"] = "BLOCKED"
                source = pages[axis_key]["node"]
                target = g.nodes[row["node_id"]]
                anchor = {"anchor_id": _stable("BEAM_AXIS_GRID_WITNESS", grid["source_sha256"], grid["page"]),
                          "document_id": grid["document_id"], "page": grid["page"],
                          "source_name": grid["source_name"], "source_sha256": grid["source_sha256"],
                          "kind": "INDEPENDENT_AXIS_GRID_BOUNDS",
                          "bbox_pt": grid["source_bounds_pt"],
                          "coordinate_space": "unrotated_pdf_points"}
                edge = g.edge("BEAM_PROFILE_INDEPENDENT_AXIS_LOCATION", source, target,
                              [anchor, *row["anchors"]], status="BLOCKED" if row["status"] == "BLOCKED" else "PROPOSED",
                              reason="تطبیق موقعیت با شبکه آکس مستقل؛ بدون اثبات تراز، طول یا واحد")
                row["edge_ids"].append(edge["edge_id"])
    beam_end_review = None
    if beam_detail_profile_witnesses is not None and beam_axis_labels is None:
        raise ValueError("Independent axis labels are required for beam-connection review")
    if beam_axis_labels is not None and independent_axis_crosscheck is not None:
        witnesses = report.get("beam_end_marker_pages", ())
        correct = [m for m in witnesses
                   if (m["document_id"], m["page"]) == (grid["document_id"], beam_axis_labels["beam_page"])
                   and m["source_sha256"] == grid["source_sha256"]]
        if len(correct) != 1 or correct[0]["status"] != "PROPOSED_UNVERIFIED_SQUARE_MARKERS":
            raise ValueError("Missing unique beam end-marker source")
        marker_page = correct[0]
        detail_samples = beam_detail_profile_witnesses or []
        if detail_samples:
            page_ids = {sample.get("page") for sample in detail_samples if isinstance(sample, dict)}
            if len(page_ids) != 1:
                raise ValueError("Ambiguous beam connection detail page")
            detail_page_number = next(iter(page_ids))
            key = (grid["document_id"], detail_page_number)
            detail_source = pages.get(key)
            if (detail_source is None or detail_source["sha256"] != grid["source_sha256"]
                    or detail_source["authority_block"]):
                raise ValueError("Foreign or blocked beam connection detail source")
            for sample in detail_samples:
                bbox = _box(sample.get("bbox_pt")) if isinstance(sample, dict) else None
                if bbox is None or not all(detail_source["source_bbox_pt"][i] <= bbox[i]
                    and bbox[i+2] <= detail_source["source_bbox_pt"][i+2] for i in (0, 1)):
                    raise ValueError("Beam detail crop outside original PDF source")
        beam_end_review = review_beam_ends_against_independent_grid(
            marker_page, grid, beam_axis_labels, beam_profile_witnesses,
            detail_samples, detail_page=detail_samples[0]["page"] if detail_samples else None,
        )
        if len(beam_end_review["profiles"]) != len(beam_profile_reviews):
            raise ValueError("Inconsistent beam support and profile witness counts")
        marker_index = {m["candidate_id"]: m for m in marker_page["marker_candidates"]}
        for end, profile in zip(beam_end_review["profiles"], beam_profile_reviews, strict=True):
            base = profile["anchors"][0]
            related = [base]
            for marker_id in end["endpoint_marker_ids"]:
                if marker_id is None:
                    continue
                marker = marker_index.get(marker_id)
                if marker is None:
                    raise ValueError("Missing beam end-marker provenance")
                related.append({
                    "anchor_id": _stable("BEAM_GRID_END_MARKER", marker_id),
                    "document_id": marker["document_id"], "page": marker["page"],
                    "source_name": marker["source_name"], "source_sha256": marker["source_sha256"],
                    "kind": "FILLED_GRID_END_MARKER_CANDIDATE", "bbox_pt": marker["bbox_pt"],
                    "source_operator_refs": marker["source_refs"],
                })
            for detail_box in end["detail_bbox_candidates_pt"]:
                related.append({
                    "anchor_id": _stable("BEAM_TYPE_ONLY_DETAIL", grid["source_sha256"], end["detail_page"], detail_box, end["profile_text"]),
                    "document_id": grid["document_id"], "page": end["detail_page"],
                    "source_name": grid["source_name"], "source_sha256": grid["source_sha256"],
                    "kind": "VISUAL_TYPE_ONLY_CONNECTION_DETAIL", "bbox_pt": detail_box,
                })
            node = g.node("BEAM_END_SUPPORT_REVIEW", (end["review_id"],),
                          end["profile_text"], "BLOCKED" if end["status"].startswith("BLOCKED_") else "UNRESOLVED",
                          related, family="beam", physical_member_verified=False,
                          support_verified=False, connection_detail_verified=False, member_quantity=None)
            plan_node = pages[(grid["document_id"], marker_page["page"])]["node"]
            edge = g.edge("BEAM_END_GRID_SYMBOL_CORROBORATION", plan_node, node, related,
                          status="BLOCKED" if end["status"].startswith("BLOCKED_") else "PROPOSED",
                          code=end["status"] if end["status"].startswith("BLOCKED_") else None,
                          reason="دو نماد انتهایی نامزد؛ تکیه‌گاه واقعی و طول نصب نامعلوم")
            end.update(node_id=node["node_id"], source_id=plan_node["node_id"],
                       edge_ids=[edge["edge_id"]], anchors=related)
            if end["candidate_detail_count"]:
                detail_node = pages[(grid["document_id"], end["detail_page"])]["node"]
                detail_anchors = [a for a in related if a["kind"] == "VISUAL_TYPE_ONLY_CONNECTION_DETAIL"]
                # A type-only visual match cannot prove that this detail governs
                # this physical span. Keep even unique same-name matches BLOCKED.
                type_edge = g.edge("BEAM_TYPE_ONLY_CONNECTION_REFERENCE", detail_node, node,
                                   detail_anchors, status="BLOCKED",
                                   code="BEAM_DETAIL_NOT_SPAN_SPECIFIC",
                                   reason="صرفاً هم‌نامی پروفیل؛ ارجاع اختصاصی به دهانه و مرجع ابلاغ احراز نشده")
                end["edge_ids"].append(type_edge["edge_id"])
    temporary = sum(row["status"] == "COMPLETE_NONFINANCIAL" for row in occurrence_reviews)
    if len({edge["edge_id"] for edge in g.edges}) != len(g.edges):
        raise ValueError("Duplicate PDF evidence graph edge")
    result = {
        "schema_version": 1, "nodes": list(g.nodes.values()), "edges": g.edges, "issues": list(g.issues.values()),
        "pages": [{k: v for k, v in page.items() if k not in {
                   "raw", "node", "sha256", "source_name", "anchors_by_kind", "authority_block", "linkable", "authority"}}
                  for page in pages.values()],
        "topology_pages": [page["raw"]["detail_topology"] for page in pages.values()],
        "vector_type_word_pages": [page["raw"].get("vector_type_word_index") for page in pages.values()
                                   if page["raw"].get("vector_type_word_index") is not None],
        "families": {family: dict(Counter(n["status"] for n in g.nodes.values()
                                      if n.get("family") == family)) for family in _FAMILIES},
        "physical_member_count": None, "floor_repetition_multiplier": None,
        "member_review_groups": member_review_groups,
        "occurrence_reviews": occurrence_reviews,
        "structural_plan_reviews": structural_plan_reviews,
        "beam_profile_reviews": beam_profile_reviews,
        "beam_axis_grid_candidates": list(report.get("beam_axis_grid_candidates", ())),
        "beam_axis_profile_crosscheck": independent_axis_crosscheck,
        "beam_end_marker_pages": list(report.get("beam_end_marker_pages", ())),
        "beam_end_support_reviews": beam_end_review["profiles"] if beam_end_review else [],
        "beam_end_support_summary": ({k:v for k,v in beam_end_review.items() if k != "profiles"}
                                      if beam_end_review else None),
        "fully_evidenced_member_count": temporary, "temporary_quantity_count": temporary,
        "quantity_approval_count": 0, "complete": False, "acceptance": "PARTIAL_NO_GO",
    }
    # Source-bound, nonpayable requests for the exact missing evidence of each
    # visually reviewed span. Neither same-name details nor axis spacing prove
    # the physical connection or fabrication length.
    beam_requests = build_beam_span_evidence_requests(result)
    result["beam_span_evidence_requests"] = beam_requests["requests"]
    result["beam_span_request_status"] = beam_requests["status"]
    result["beam_span_request_summary"] = beam_requests["summary"]
    result["review_questions"] = _group_review_questions(result["issues"])
    result["graph_sha256"] = sha256(json.dumps(
        result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return result


def _group_review_questions(issues):
    """Group correctable issues without a separate prompt for each outline."""
    grouped = {}
    for issue in issues:
        code = issue["reason_code"]
        if code not in _REVIEWABLE or not issue["anchors"]:
            continue
        first = issue["anchors"][0]
        key = code, first["document_id"], first["page"]
        query = grouped.setdefault(key, {
            "tag": "PDF_GRAPH_" + _stable(code, *key[1:]), "status": "REVIEW_REQUIRED",
            "question": issue["required_evidence"],
            "suggestion": {"status": "PROPOSED_UNVERIFIED", "value": None, "reason": issue["reason"]},
            "evidence": [], "options": ["correct", "request_document"],
        })
        issue["review_tag"] = query["tag"]
        query["evidence"].append(dict(document_id=first["document_id"], page=first["page"],
                                      bbox_pt=first["bbox_pt"], issue_id=issue["issue_id"]))
    return list(grouped.values())
