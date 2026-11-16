"""Read-only, source-bound structural RFI preparation and designer-reply screening.

No supplied document, signed statement or geometric comparison is a payment,
member, connection or dimensional approval until independent engineer review.
Neither this module nor the UI submits requests or transmits private documents.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
import re

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_REF = re.compile(r"[A-Z0-9][A-Z0-9._/-]{1,79}\Z")
_C2 = (
    "انطباق ستون C2 در پلان صفحه 14 و دیتیل صفحه 19: شماره‌های 2 و 5 در پلان، "
    "5 و 6 در دیتیل؛ شماره 6 در پلان به C1 منتسب است. لطفاً نقشه و جدول اصلاح‌شده "
    "با ارجاع روشن به موقعیت فیزیکی، شماره عضو و نسخه حاکم ارائه شود."
)
_F3 = (
    "مغایرت علامت/تیپ F3 بین صفحات 9 و 12؛ لطفاً پلان، دیتیل، جدول تیپ و "
    "نسخه ابلاغی حاکم را برای تعیین مشخصات و محدوده اجرایی ارائه کنید."
)
_CONFLICTS = (("C2", (14, 19), _C2), ("F3", (9, 12), _F3))


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(data):
    return sha256(_canonical(data).encode("utf-8")).hexdigest()


def _validate_request_register(register, source_sha):
    if not isinstance(register, dict) or register.get("status") != "BLOCKED_AWAITING_GOVERNING_ENGINEERING_DOCUMENTS":
        raise ValueError("An open, nonfinancial beam design-request register is required")
    requests = register.get("requests")
    if not isinstance(requests, list) or not 1 <= len(requests) <= 256:
        raise ValueError("No bounded source-backed beam requests")
    ids = set()
    for row in requests:
        if not isinstance(row, dict) or row.get("source_sha256") != source_sha:
            raise ValueError("Foreign drawing request")
        key = row.get("request_id")
        codes = row.get("required_evidence_codes")
        if (not isinstance(key, str) or not key.startswith("BEAM_MISSING_DOCUMENT:") or key in ids
                or not isinstance(codes, list) or not codes or len(codes) != len(set(codes))
                or any(not isinstance(c, str) or not re.fullmatch("[A-Z0-9_]{5,70}", c) for c in codes)
                or row.get("financially_payable") is not False or row.get("physical_member_verified") is not False
                or row.get("member_quantity") is not None or row.get("quantity_approved") is not False
                or row.get("status") != "BLOCKED_REQUIRES_GOVERNING_ENGINEERING_DOCUMENTS"):
            raise ValueError("Unsafe or duplicated engineering request")
        if (type(row.get("beam_page")) is not int or not 1 <= row["beam_page"] <= 19
                or not isinstance(row.get("span_axes"), str)
                or not re.fullmatch(r"[A-Z]-[A-Z]", row["span_axes"])
                or not isinstance(row.get("printed_axis_row"), str)):
            raise ValueError("Unbound span location")
        ids.add(key)
    return requests


def build_designer_rfi_packet(register, *, source_sha256, source_name="naghshe.pdf", graph_sha256=None):
    """Prepare 12 per-span questions plus C2/F3 reconciliation without inventing answers."""
    if not isinstance(source_sha256, str) or not _SHA.fullmatch(source_sha256):
        raise ValueError("Invalid original drawing SHA-256")
    if graph_sha256 is not None and (not isinstance(graph_sha256, str) or not _SHA.fullmatch(graph_sha256)):
        raise ValueError("Invalid reference graph SHA-256")
    if not isinstance(source_name, str) or source_name != Path(source_name).name or not source_name.endswith(".pdf"):
        raise ValueError("Unsafe original drawing filename")
    originals = _validate_request_register(register, source_sha256)
    rows = []
    for item in originals:
        rows.append({
            "question_id": item["request_id"], "category": "BEAM_SPAN",
            "source_sha256": source_sha256, "sheet_refs": sorted({13, item["beam_page"], item.get("detail_page") or 17}),
            "span_axes": item["span_axes"], "axis_row": item["printed_axis_row"],
            "printed_mark": item.get("printed_mark"), "visual_profile_unverified": item.get("profile_visual"),
            "review_id": item["end_review_id"], "required_evidence_codes": list(item["required_evidence_codes"]),
            "request_fa": "لطفاً مدارک حاکمِ اتصال اختصاصی دو انتهای تیر، تراز نصب، واحد و طول ساخت/برش "
                          "این دهانه را با شناسه دقیق در پلان و دیتیل ارائه کنید؛ نوشته یا مقیاس چاپی به تنهایی ملاک نیست.",
            "status": "UNSENT_PENDING_DESIGNER", "response": None,
            "physical_member_verified": False, "approved_length_m": None, "financially_payable": False,
        })
    for code, pages, issue in _CONFLICTS:
        rows.append({
            "question_id": "ENGINEERING_CONFLICT:"+code+":"+source_sha256[:16],
            "category": "PLAN_DETAIL_CONFLICT", "conflict_code": code,
            "source_sha256": source_sha256, "sheet_refs": list(pages),
            "request_fa": issue,
            "required_evidence_codes": ["GOVERNING_REVISION", "DESIGNER_CORRECTED_PLAN_DETAIL_CROSSREFERENCE"],
            "status": "UNSENT_PENDING_DESIGNER", "response": None,
            "physical_member_verified": False, "approved_length_m": None, "financially_payable": False,
        })
    packet = {"schema_version": 1, "kind": "STRUCTURALPRO_ENGINEERING_RFI_PRIVATE",
              "source_name": source_name, "source_sha256": source_sha256,
              "graph_sha256": graph_sha256, "response_received": False,
              "sender": None, "designer": None, "sent_at": None,
              "questions": rows, "accepted_members": 0, "approved_financial_rows": 0,
              "acceptance": "PARTIAL_NO_GO"}
    packet["packet_sha256"] = _digest(packet)
    return packet


def _unique_pairs(pairs):
    data = dict(pairs)
    if len(pairs) != len(data):
        raise ValueError("Duplicate JSON key in designer reply")
    return data


def load_designer_reply(path):
    """Load a *local* reply JSON without accepting its assertions as design approval."""
    path = Path(path)
    if path.stat().st_size > 256 * 1024:
        raise ValueError("Oversized designer reply file")
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_pairs)


def inspect_designer_reply(packet, reply, *, attachment_directory=None):
    """Screen provided PDF bytes and identifiers; always return unapproved requests.

    Only locally attached, source-hashed PDF files may support a 'received'
    status. Their engineering authenticity, signed authority, and relevance
    still require professional review. No auto-approval path exists.
    """
    if (not isinstance(packet, dict) or packet.get("kind") != "STRUCTURALPRO_ENGINEERING_RFI_PRIVATE"
            or not isinstance(packet.get("packet_sha256"), str)
            or packet["packet_sha256"] != _digest({k:v for k,v in packet.items() if k!="packet_sha256"})
            or packet.get("acceptance") != "PARTIAL_NO_GO"):
        raise ValueError("RFI packet identity has changed")
    if not isinstance(reply, dict) or set(reply) != {"schema_version", "packet_sha256", "reply_reference", "responses"}:
        raise ValueError("Invalid designer reply schema")
    if reply["schema_version"] != 1 or reply["packet_sha256"] != packet["packet_sha256"]:
        raise ValueError("Response belongs to another or superseded RFI")
    ref = reply["reply_reference"]
    if not isinstance(ref, str) or not _REF.fullmatch(ref):
        raise ValueError("Missing reference number for response receipt")
    answers = reply["responses"]
    if not isinstance(answers, list) or len(answers) > len(packet["questions"]):
        raise ValueError("Unbounded response set")
    questions = {x["question_id"]: x for x in packet["questions"]}
    checked, used = [], set()
    folder = Path(attachment_directory).resolve() if attachment_directory is not None else None
    for item in answers:
        allowed = {"question_id", "evidence_code", "attachment_name", "attachment_sha256", "page_number", "document_reference", "document_revision"}
        if not isinstance(item, dict) or set(item) != allowed:
            raise ValueError("Response fields must be evidence-only, never an approval or quantity")
        q = questions.get(item["question_id"])
        key = (item["question_id"], item["evidence_code"])
        if q is None or item["evidence_code"] not in q["required_evidence_codes"] or key in used:
            raise ValueError("Foreign, duplicate or unrequested answer")
        used.add(key)
        name, digest, page = item["attachment_name"], item["attachment_sha256"], item["page_number"]
        if (not isinstance(name, str) or name != Path(name).name or not re.fullmatch(r"[\w .()-]{3,120}\.pdf", name, re.I)
                or not isinstance(digest, str) or not _SHA.fullmatch(digest)
                or type(page) is not int or page < 1
                or any(not isinstance(item[f], str) or not _REF.fullmatch(item[f])
                       for f in ("document_reference", "document_revision"))):
            raise ValueError("Missing local provenance or revision citation")
        if folder is None:
            raise ValueError("Received design PDF bytes must be checked locally")
        asset = folder / name
        if asset.is_symlink() or not asset.is_file() or asset.resolve().parent != folder or asset.stat().st_size > 128*1024*1024:
            raise ValueError("Designer PDF attachment missing, unsafe or oversized")
        if sha256(asset.read_bytes()).hexdigest() != digest:
            raise ValueError("Designer attachment SHA-256 mismatch")
        import pymupdf
        with pymupdf.open(asset) as document:
            if not document.is_pdf or page > len(document) or len(document) < 1:
                raise ValueError("Designer page outside real PDF")
        checked.append({"question_id":item["question_id"], "evidence_code":item["evidence_code"],
                        "attachment_sha256":digest,"page_number":page,
                        "document_reference":item["document_reference"],"document_revision":item["document_revision"],
                        "status":"SOURCE_BYTES_MATCHED_ENGINEERING_REVIEW_REQUIRED", "financially_payable":False})
    answered_questions={item["question_id"] for item in checked}
    return {"status":"RECEIPT_ONLY_NOT_DESIGN_APPROVAL", "packet_sha256":packet["packet_sha256"],
            "received_evidence_count":len(checked), "question_count":len(questions),
            "questions_with_some_response":len(answered_questions),
            "questions_still_without_response":len(questions)-len(answered_questions),
            "responses":checked,"physical_member_verified":False,"approved_financial_rows":0,
            "acceptance":"PARTIAL_NO_GO"}


def write_designer_rfi_package(packet, destination):
    """Write private draft and empty response template, never send."""
    path = Path(destination)
    path.mkdir(parents=True, exist_ok=True)
    (path/"PRIVATE_ENGINEERING_RFI_PACKET.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
    template = {"schema_version":1,"packet_sha256":packet["packet_sha256"],
                "reply_reference":"FILL_REFERENCE", "responses":[]}
    (path/"DESIGNER_RESPONSE_TEMPLATE.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    with (path/"PRIVATE_RFI_QUESTIONS.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["question_id","category","span_axes","axis_row","printed_mark","visual_profile_unverified","sheet_refs","required_evidence_codes","request_fa","status"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in packet["questions"]:
            writer.writerow({key:",".join(row[key]) if key=="required_evidence_codes" else ",".join(map(str,row[key])) if key=="sheet_refs" else row.get(key)
                             for key in fields})
    body = ["# درخواست رسمی رفع ابهام نقشه‌های سازه", "", "**وضعیت:** پیش‌نویس ارسال‌نشده. نام طراح و شماره مکاتبه باید توسط مسئول پروژه تکمیل شود.", "",
            "موضوع: درخواست نسخه حاکم نقشه‌های سازه، رفع تعارض پلان و دیتیل، و مدارک دهانه‌های تیر", "",
            "مدیریت محترم طراحی سازه،", "", "خواهشمند است برای پاسخ‌گویی به ابهامات اجرایی فایل نقشه با شناسه زیر، مدارک اصلاحی ابلاغ‌شده و ارجاعات اختصاصی هر دهانه را اعلام فرمایید.", "",
            f"SHA-256 فایل مرجع: `{packet['source_sha256']}`", "",
            "برای هر دهانه، نوع و هویت تکیه‌گاه در دو انتها، شماره دیتیل اجرایی مختص همان دهانه، تراز نصب، طول برش با کسورات و واحد اندازه‌گیری روشن باشد. هم‌نامی تیپ یا فاصله آکس برای تأیید مقدار کافی نیست.", ""]
    for x in packet["questions"]:
        if x["category"] == "PLAN_DETAIL_CONFLICT":
            body.extend([f"**تعارض {x['conflict_code']} (صفحات {', '.join(map(str,x['sheet_refs']))}):** {x['request_fa']}", ""])
    body.extend([f"۱۲ پرونده دهانه تیر در فایل پیوست `PRIVATE_RFI_QUESTIONS.csv` با شناسه مستقل و مدارک موردنیاز درج شده است.",
                 "", "لطفاً پاسخ را با شماره و تاریخ نامه، شماره/ویرایش شیت‌های اصلاحی و فایل PDF اصلیِ ابلاغ‌شده همراه فرمایید. این پیش‌نویس به‌صورت خودکار ارسال نشده است.", ""])
    (path/"PRIVATE_RFI_TO_STRUCTURAL_DESIGNER_FA.md").write_text("\n".join(body), encoding="utf-8")
    return path