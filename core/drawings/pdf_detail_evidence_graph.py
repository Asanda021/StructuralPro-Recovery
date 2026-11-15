"""Source-bound PDF detail and cross-sheet evidence. Never a quantity engine."""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

from core.drawings.pdf_detail_object_index import _family_words, _tag
from core.drawings.pdf_type_word_witness import _box


_CODE = r"[A-Z0-9][A-Z0-9_.-]{0,31}"
_DETAIL = r"(?:[A-Z0-9.-]{0,15}[0-9][A-Z0-9.-]{0,16}|[A-Z]{1,4}-[A-Z]{1,4})"
_TYPE = r"[A-Z]{1,4}[-–]?[0-9]{1,4}"
_AXIS = r"[A-Z0-9-]{1,16}\s*/\s*[A-Z0-9-]{1,16}"
_DEFINITIONS = (
    ("SHEET_ID", rf"(?:SHEET(?: NO\.)?|شیت)(?:\s*[:#]\s*|\s+)(?P<code>{_CODE})"),
    ("REVISION", rf"(?:REV(?:ISION)?\.?|ویرایش|نسخه)(?:\s*[:#]\s*|\s+)(?P<code>{_CODE})"),
    ("PRINTED_SCALE", r"(?:SCALE|مقیاس)(?:\s*:\s*|\s+)1\s*[:/]\s*(?P<denominator>[1-9][0-9]{0,4})"),
    ("INSTANCE", rf"(?:INSTANCE|عضو)\s+(?P<member>{_CODE})\s+(?:TYPE|تیپ)\s+(?P<tag>{_TYPE})"
                 rf"\s+(?:GRID|آکس)\s+(?P<axis>{_AXIS})\s+(?:LEVEL|تراز)\s+(?P<level>{_CODE})"),
    ("AXIS", rf"(?:GRID|AXIS|آکس)\s+(?P<code>{_AXIS})"),
    ("LEVEL", rf"(?:LEVEL|FLOOR|تراز|طبقه)\s+(?P<code>{_CODE})"),
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
}
_FAMILIES = (
    "beam", "column", "foundation", "slab_roof", "wall_opening", "stair_ramp",
    "reinforcement_connection", "architecture_finishes", "mechanical", "electrical", "unknown",
)
_LOCAL_LINK_PAIR_LIMIT = 1_000_000
_VIEW_ROLES = {"CLOSED_CONTOUR", "OPEN_CHAIN", "BRANCHED_STROKES",
               "CURVED_ENDPOINT_CYCLE", "CURVE_CONTROL_HULL", "FILL_BOUNDARY_UNRESOLVED"}
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
    "LEGACY_GRID_LEVEL_UNKNOWN": ("شاهد موقعیت شبکه برای تکرار عضو در ترازها کافی نیست", "شناسه عضو و تراز اجرایی مستقل"),
}
_REVIEWABLE = {
    "REVISION_CONFLICT", "SUPERSEDED_SOURCE", "DIFFERENT_PROJECT_OR_ISSUE", "UNVERIFIED_DOCUMENT_SCOPE",
    "TYPE_FAMILY_CONFLICT", "MULTIPLE_DETAIL_TYPE_MARKS", "AMBIGUOUS_LOCAL_TYPE_MARK",
    "REFERENCE_TARGET_NOT_FOUND", "AMBIGUOUS_REFERENCE_TARGET", "REFERENCE_SUBJECT_NOT_FOUND",
    "REFERENCE_TARGET_UNRESOLVED", "REFERENCE_SOURCE_UNRESOLVED", "CONFLICTING_DETAIL_REFERENCES",
    "INSTANCE_SCOPE_CONFLICT", "INSTANCE_GEOMETRY_AMBIGUOUS", "AMBIGUOUS_VIEW_SCALE", "MISSING_TARGET_TYPE",
    "SCHEDULE_CONTEXT_UNVERIFIED",
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
    return (raw or "").upper().replace("-", "").replace("–", "")


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
    registration = page["authority"]
    if registration and not page["authority_block"]:
        return tuple(registration[k] for k in ("project_id", "issue_id", "revision"))
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
    if a["revision"] != b["revision"]:
        return "REVISION_CONFLICT"
    return None


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
    geometric_labels = sum(len(lookup[kind]) for kind in ("DETAIL_TITLE", "PRINTED_SCALE", "INSTANCE"))
    structured_count = sum(len(lookup[kind]) for kind in ("DETAIL_TITLE", "INSTANCE", "SCHEDULE_ROW"))
    local_pairs = (len(topo["groups"]) * (geometric_labels + len(word_witnesses) + len(raw["image_placements"])) +
                   len(word_witnesses) * structured_count)
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
        "page_role": role, "status": state, "rotation": topo.get("rotation", 0),
        "source_bbox_pt": raw["source_bbox_pt"],
        "content_kind": "HYBRID" if raster and not raster_only else "RASTER" if raster else
                        "VECTOR" if raw["vector_path_count"] else "TEXT" if raw["searchable_text_block_count"]
                        else "NO_DETECTED_CONTENT",
        "source_path_count": topo.get("source_path_count"),
        "source_operator_count": topo.get("source_operator_count"),
        "topology_status": topo["status"], "topology_group_count": len(topo["groups"]),
        "printed_revisions": sorted(printed_revisions),
        "authority_status": conflict or (authority["status"] if authority else "UNREGISTERED"),
        "authority": authority, "sha256": digest, "authority_block": conflict,
        "anchors_by_kind": lookup, "raw": raw, "node": node,
        "linkable": not (extraction_blocked or geometry_blocked or raster_only or local_links_blocked),
        "topology_reason_code": topo["reason_code"],
        "source_errors": sorted(set(raw["extraction_errors"] + (
            [extraction["status"]] if extraction["status"] != "EXAMINED" else []))),
        "printed_scales": sorted({f'1:{item["denominator"]}' for item in lookup["PRINTED_SCALE"]}),
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
            "coordinate_space": "unrotated_pdf_points",
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


def _add_local_evidence(g, page, shapes):
    raw, digest, number = page["raw"], page["sha256"], page["page"]
    words = []
    declarations = page["anchors_by_kind"]
    structured = [*declarations["DETAIL_TITLE"], *declarations["INSTANCE"], *declarations["SCHEDULE_ROW"]]
    for mark in raw["type_word_index"]["type_word_witnesses"]:
        if mark["title_anchor_ids"] or (page["linkable"] and structured and
                any(_near(mark["bbox_pt"], line["bbox_pt"], 0) for line in structured)):
            continue
        words.append({
            **mark, "kind": "TYPE_WORD", "anchor_id": _stable("WORD", digest, number, mark["source_word_index"]),
        })
    by_word, by_shape = _nearby(shapes if page["linkable"] else [], words, limit=16)
    for word in words:
        _, family = _tag(word["type_tag"])
        options = by_word[word["anchor_id"]]
        unique = len(options) == 1 and len(by_shape[options[0]["node_id"]]) == 1
        code = ("UNBOUND_LOCAL_TYPE_MARK" if not options else "AMBIGUOUS_LOCAL_TYPE_MARK" if not unique else
                "TYPE_FAMILY_CONFLICT" if family and options[0]["family"] not in {"unknown", family} else None)
        status = ("BLOCKED" if not page["linkable"] or (options and code) else "UNRESOLVED")
        evidence = g.node("EVIDENCE", (word["anchor_id"],), word["type_tag"], status, [word],
                          family=family or "unknown", type_tag=word["type_tag"])
        refs = [word, *(a for option in options for a in option["anchors"])]
        if code:
            g.issue(evidence, code, refs, status=status)
        if options:
            g.edge("TYPE_WORD_NEAR_VIEW", evidence, options[0] if unique else None, refs,
                   status="REJECTED" if code == "TYPE_FAMILY_CONFLICT" else "AMBIGUOUS" if code else "PROPOSED",
                   reason=_REASONS[code][0] if code else "جای واژه و شکل در مختصات یک صفحه",
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
                          plan_geometry_present=bound, physical_member_verified=False)
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


def build_pdf_detail_evidence_graph(report, page_evidence, *, revision_registry=None, max_records=80000):
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
    # Previously detected column locations also enter the same graph. They do
    # not merge with explicit instances based on tag or approximate coordinates.
    for candidate in report.get("grid_location_candidates", ()):
        if not candidate.get("column_context_candidate"):
            continue
        key = candidate["document_id"], candidate["page"]
        page = pages[key]
        x, y = candidate["x_pt"], candidate["y_pt"]
        anchor = {"anchor_id": _stable("GRID_LOC", page["sha256"], key[1], candidate["row"], candidate["column"]),
                  "document_id": key[0], "page": key[1], "kind": "GRID_LOCATION_CANDIDATE",
                  "bbox_pt": [x - 1, y - 1, x + 1, y + 1],
                  "independent_axis_grid_witness": candidate.get("independent_axis_grid_witness")}
        node = g.node("INSTANCE_CANDIDATE", (anchor["anchor_id"],), "موقعیت احتمالی ستون", "UNRESOLVED",
                      [anchor], family="column", type_tag=candidate.get("suggested_type"),
                      physical_member_verified=False, level=None, identity_witness_count=1)
        g.edge("GRID_LOCATION_ON_SHEET", node, page["node"], [anchor], status="PROPOSED",
               reason="مختصات محلی و شاهد نماد؛ تراز اجرایی به مدرک مستقل نیاز دارد")
        g.issue(node, "LEGACY_GRID_LEVEL_UNKNOWN")
    if len({edge["edge_id"] for edge in g.edges}) != len(g.edges):
        raise ValueError("Duplicate PDF evidence graph edge")
    result = {
        "schema_version": 1, "nodes": list(g.nodes.values()), "edges": g.edges, "issues": list(g.issues.values()),
        "pages": [{k: v for k, v in page.items() if k not in {
                   "raw", "node", "sha256", "anchors_by_kind", "authority_block", "linkable", "authority"}}
                  for page in pages.values()],
        "topology_pages": [page["raw"]["detail_topology"] for page in pages.values()],
        "families": {family: dict(Counter(n["status"] for n in g.nodes.values()
                                      if n.get("family") == family)) for family in _FAMILIES},
        "physical_member_count": None, "floor_repetition_multiplier": None,
        "quantity_approval_count": 0, "complete": False, "acceptance": "PARTIAL_NO_GO",
    }
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
