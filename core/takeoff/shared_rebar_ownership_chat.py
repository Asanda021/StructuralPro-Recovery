"""Read-only reconciliation of *documented physical* rebar between RC members.

This is a conservative pre-integration aid, NOT a BOQ/SQLite commit guard. A
second reference to the same physical bar is never another payable quantity.
All cut lengths, weights, parts, members, links and owners must be documented.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Context, Decimal, InvalidOperation, localcontext
import hashlib
import json

POLICY = "shared_rebar_ownership_chat_v1"
KINDS = frozenset({"beam", "column", "shear_wall", "stair", "bored_pile", "pile_cap", "foundation", "tie_beam", "slab"})
PARTS = frozenset({"straight", "bend", "hook", "anchorage", "lap", "other"})
CONNECTIONS = frozenset({"lap", "anchorage", "starter", "continuity"})
HEX = frozenset("0123456789abcdef")
MAX_DIGITS = 60

class RebarOwnershipError(ValueError):
    """A missing engineering assertion or duplicate payment, not an estimated zero."""


def _object(v, keys, title):
    if not isinstance(v, dict) or set(v) != set(keys):
        raise RebarOwnershipError(f"{title}: کلیدهای قرارداد باید دقیقاً کامل باشند")
    return v


def _name(v, title):
    if not isinstance(v, str) or not v or v != v.strip():
        raise RebarOwnershipError(f"{title}: شناسه/منبع صریح و بدون فاصله لازم است")
    return v


def _sha(v, title):
    if not isinstance(v, str) or len(v) != 64 or any(ch not in HEX for ch in v):
        raise RebarOwnershipError(f"{title}: SHA-256 واقعی با ۶۴ رقم کوچک لازم است")
    return v


def _num(v, title):
    if isinstance(v, (bool, float)) or not isinstance(v, (str, Decimal, int)):
        raise RebarOwnershipError(f"{title}: داده عددی باید Decimal/int/string باشد")
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError) as exc:
        raise RebarOwnershipError(f"{title}: عدد نامعتبر") from exc
    if not d.is_finite() or d <= 0 or len(d.as_tuple().digits) > MAX_DIGITS or abs(d.adjusted()) > 60:
        raise RebarOwnershipError(f"{title}: عدد مثبت متناهی در محدوده قرارداد الزامی است")
    return d


def _integer(v, title):
    d = _num(v, title)
    if d != d.to_integral_value():
        raise RebarOwnershipError(f"{title}: تعداد باید عدد صحیح مثبت باشد")
    return int(d)


def _num_string(d: Decimal):
    return format(d, "f")


def _canon(v):
    """Canonical JSON for source SHA; no numeric float/implicit serialization."""
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=lambda x: format(x, "f") if isinstance(x, Decimal) else _unsupported(x))


def _unsupported(x):
    raise TypeError(f"unsupported source value {type(x).__name__}")


def _fingerprint(v):
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()


def _claim(c):
    _object(c, ("physical_bar_id", "physical_piece_id", "member_kind", "member_id", "floor_id",
                "source_id", "connection_id", "role", "payer_source_id", "participant_source_ids",
                "detail_ref", "detail_sha256", "approved_by", "group", "diameter_mm",
                "count", "unit_mass_kg_m", "unit_mass_ref", "cut_parts"), "ادعای میلگرد")
    for k in ("physical_bar_id", "physical_piece_id", "member_id", "floor_id", "source_id",
              "connection_id", "payer_source_id", "detail_ref", "approved_by", "group", "unit_mass_ref"):
        _name(c[k], k)
    if c["member_kind"] not in KINDS:
        raise RebarOwnershipError("نوع عضو سازه‌ای خارج از دامنه قرارداد است")
    if c["role"] not in ("payer", "reference"):
        raise RebarOwnershipError("نقش پرداخت باید payer یا reference باشد")
    _sha(c["detail_sha256"], "هش دیتایل میلگرد")
    raw_participants=c["participant_source_ids"]
    if not isinstance(raw_participants, list) or not raw_participants:
        raise RebarOwnershipError("فهرست تمام اعضای مرتبط با میلگرد لازم است")
    for x in raw_participants: _name(x,"شناسه منبع عضو مرتبط")
    if len(raw_participants)!=len(set(raw_participants)) or raw_participants!=sorted(raw_participants):
        raise RebarOwnershipError("شناسه اعضای مرتبط باید بدون تکرار و مرتب باشند")
    if c["source_id"] not in raw_participants or c["payer_source_id"] not in raw_participants:
        raise RebarOwnershipError("منبع و مالک پرداخت باید در اعضای مرتبط ذکر شوند")
    if c["role"] == "payer" and c["source_id"] != c["payer_source_id"]:
        raise RebarOwnershipError("مالک مالی نمی‌تواند شناسه دیگری را به‌عنوان payer ثبت کند")
    if c["role"] == "reference" and c["source_id"] == c["payer_source_id"]:
        raise RebarOwnershipError("مالک پرداخت نمی‌تواند فقط ردیف ارجاعی اعلام کند")
    d=_num(c["diameter_mm"], "قطر مستند میلگرد")
    count=_integer(c["count"], "تعداد فیزیکی میلگرد")
    mass=_num(c["unit_mass_kg_m"], "جرم واحد طول معتبر")
    parts=c["cut_parts"]
    if not isinstance(parts,list) or not parts:
        raise RebarOwnershipError("اجزای واقعی طول برش الزامی است")
    seen=set(); pvals=[]
    for p in parts:
        _object(p,("piece_part_id","kind","length_m","source_ref"),"جزء طول برش")
        pid=_name(p["piece_part_id"],"هویت جزء طول برش")
        if pid in seen:raise RebarOwnershipError("جزء طول برش دوباره آمده است")
        seen.add(pid)
        if p["kind"] not in PARTS:raise RebarOwnershipError("نوع جزء طول برش نامعتبر است")
        pvals.append((pid,p["kind"],_num(p["length_m"],"طول جزء"),_name(p["source_ref"],"مرجع طول")))
    # The exact component list, rather than a nominal anchorage coefficient, is payable.
    with localcontext(Context(prec=256)):
        cut=sum((p[2] for p in pvals),Decimal(0))
        total=cut*mass*count
    if not total.is_finite() or total <= 0:
        raise RebarOwnershipError("جرم مستند میلگرد معتبر نیست")
    signature=(str(d.normalize()),str(mass.normalize()),count,c["unit_mass_ref"],
               c["detail_sha256"],c["detail_ref"],c["group"],c["physical_piece_id"],
               tuple(sorted((p[0],p[1],str(p[2].normalize()),p[3]) for p in pvals)),
               c["payer_source_id"],tuple(raw_participants),c["connection_id"])
    return {"bar_id":c["physical_bar_id"],"piece_id":c["physical_piece_id"],
            "source_id":c["source_id"],"role":c["role"],"payer":c["payer_source_id"],
            "connection_id":c["connection_id"],"review_approver":c["approved_by"],
            "signature":signature,"cut_length_m":cut,"mass_kg":total,"count":count,
            "participants":set(raw_participants)}


def reconcile(data: dict, project: dict | None = None, *, source_document: bytes | None = None) -> dict:
    """Produce informational audit only. NEVER a payable takeoff or commit authorization.

    `project`, when provided, is a read-only *snapshot*. Missing bar identities in
    existing rebar rows are surfaced as blockers, never silently assumed clear.
    """
    _object(data,("project_id","snapshot_ref","source_sha256","independent_reviewer",
                  "review_ref","claims","connections"),"دفتر مالکیت مشترک")
    for k in ("project_id","snapshot_ref","independent_reviewer","review_ref"):_name(data[k],k)
    _sha(data["source_sha256"],"هش پرونده ارتباط")
    if not isinstance(data["claims"],list) or not data["claims"]:
        raise RebarOwnershipError("ادعاهای فیزیکی میلگرد الزامی است")
    if not isinstance(data["connections"],list):
        raise RebarOwnershipError("فهرست اتصالات باید فهرست معتبر باشد")
    if source_document is not None:
        if not isinstance(source_document, bytes) or hashlib.sha256(source_document).hexdigest()!=data["source_sha256"]:
            raise RebarOwnershipError("محتوای مدرک منبع با SHA-256 ثبت‌شده مطابقت ندارد")
    recs=[_claim(c) for c in data["claims"]]
    reviewer=data["independent_reviewer"].casefold()
    if any(reviewer == r["review_approver"].casefold() for r in recs):
        raise RebarOwnershipError("بازبین مستقل با تأییدکننده دیتایل یکسان است")
    group=defaultdict(list); used_source=set();piece_to_bar={}
    for r in recs:
        key=(r["bar_id"],r["source_id"])
        if key in used_source:raise RebarOwnershipError("یک عضو، میلگرد فیزیکی یکسان را دوبار ادعا کرده است")
        used_source.add(key)
        other=piece_to_bar.setdefault(r["piece_id"],r["bar_id"])
        if other!=r["bar_id"]:
            raise RebarOwnershipError("یک قطعه فیزیکی به دو شناسه میلگرد نسبت داده شده است")
        group[r["bar_id"]].append(r)
    # Connection evidence is descriptive; does not invent or add lap/anchorage quantities.
    known_connections={}; referenced={}
    for c in data["connections"]:
        _object(c,("connection_id","type","bar_ids","detail_ref","detail_sha256","approved_by"),"اتصال")
        cid=_name(c["connection_id"],"هویت اتصال")
        if cid in known_connections:raise RebarOwnershipError("اتصال تکراری است")
        typ=c["type"]
        if typ not in CONNECTIONS:raise RebarOwnershipError("نوع اتصال نامعتبر است")
        bars=c["bar_ids"]
        if not isinstance(bars,list) or len(bars)!=(2 if typ=="lap" else 1) or len(bars)!=len(set(bars)):
            raise RebarOwnershipError("تعداد یا هویت میلگردهای اتصال ناقص است")
        for bar in bars:
            _name(bar,"هویت میلگرد اتصال")
            if bar not in group:raise RebarOwnershipError("اتصال به میلگرد ثبت‌نشده ارجاع می‌دهد")
            referenced.setdefault(bar,set()).add(cid)
        _name(c["detail_ref"],"مرجع اتصال")
        _sha(c["detail_sha256"],"هش اتصال")
        if reviewer==_name(c["approved_by"],"تأییدکننده اتصال").casefold():
            raise RebarOwnershipError("بازبین مستقل نباید تأییدکننده اتصال باشد")
        if typ in ("lap", "anchorage"):
            required_part = "lap" if typ == "lap" else "anchorage"
            for bar in bars:
                for physical_claim in data["claims"]:
                    if physical_claim["physical_bar_id"] == bar and not any(
                        part["kind"] == required_part for part in physical_claim["cut_parts"]
                    ):
                        raise RebarOwnershipError("جزء واقعی طول وصله یا مهاری برای اتصال مستند نیست")
        known_connections[cid]={"type":typ,"bar_ids":list(bars),"detail_ref":c["detail_ref"]}
    paid=[]; information=[]
    with localcontext(Context(prec=256)):
        total=Decimal(0)
        for bar, rows in sorted(group.items()):
            signatures={r["signature"] for r in rows}
            if len(signatures)!=1:
                raise RebarOwnershipError("دیتایل، تعداد، طول، جرم یا مالک میلگرد مشترک متناقض است")
            participants=rows[0]["participants"]
            if {r["source_id"] for r in rows}!=participants:
                raise RebarOwnershipError("یکی از اعضای مرتبط با این میلگرد هنوز شناسایی و بررسی نشده است")
            owners=[r for r in rows if r["role"]=="payer"]
            if len(owners)!=1 or owners[0]["source_id"]!=rows[0]["payer"]:
                raise RebarOwnershipError("مالک پرداخت یکتا و مستند وجود ندارد")
            if {r["connection_id"] for r in rows} != {rows[0]["connection_id"]}:
                raise RebarOwnershipError("شناسه اتصال بین اعضا ناسازگار است")
            if rows[0]["connection_id"] not in referenced.get(bar,set()):
                raise RebarOwnershipError("اتصال ثبت‌شده برای میلگرد فاقد مستند متصل است")
            owner=owners[0]
            total+=owner["mass_kg"]
            paid.append({"physical_bar_id":bar,"paying_source_id":owner["source_id"],
                         "cut_length_m":_num_string(owner["cut_length_m"]),
                         "mass_kg":_num_string(owner["mass_kg"]),"unit":"kg",
                         "connection_id":owner["connection_id"],
                         "participants":sorted(participants),"physical_piece_id":owner["piece_id"]})
            information.extend({"physical_bar_id":bar,"referencing_source_id":r["source_id"],
                                "payable":False} for r in rows if r["role"]=="reference")
    blockers=["ثبت قطعی ممنوع: نیازمند تطبیق با تمام ردیف‌های قدیمی و واقعی پروژه و تأیید مستقل مالکیت"]
    if source_document is None:
        blockers.append("مدرک اصلی منبع در پیش‌نمایش ارائه نشده؛ SHA فقط از نظر شکل بررسی شده است")
    blockers.append("مدارک جزئی میلگرد و اتصال و استقلال امضای بازبین نیازمند بررسی واقعی فایل‌هاست")
    if project is not None:
        if not isinstance(project,dict) or project.get("id") != data["project_id"]:
            raise RebarOwnershipError("تصویر پروژه با هویت ورودی سازگار نیست")
        stored=project.get("takeoffs",[])
        if not isinstance(stored,list):raise RebarOwnershipError("ریزمتره ذخیره‌شده ساختار معتبر ندارد")
        for i,row in enumerate(stored):
            if not isinstance(row,dict):raise RebarOwnershipError("ریزمتره موجود نامعتبر است")
            params=row.get("params") or {}
            if not isinstance(params,dict):raise RebarOwnershipError("پارامترهای ریزمتره نامعتبر است")
            q=row.get("quantities") or []
            if not isinstance(q,list):raise RebarOwnershipError("ریزکمیت موجود نامعتبر است")
            if any(isinstance(x,dict) and ("rebar" in str(x.get("code", "")).lower() or "میلگرد" in str(x.get("title", ""))) for x in q):
                physical=params.get("physical_bar_id")
                if not isinstance(physical,str) or not physical.strip():
                    blockers.append(f"ردیف میلگرد قبلی {i} فاقد هویت فیزیکی قابل مقایسه است")
                elif physical in group:
                    blockers.append(f"میلگرد {physical} در برداشت قبلی وجود دارد؛ وضعیت مالی باید مستقل بررسی شود")
        # A BOQ row may survive even if an older/imported takeoff is absent.
        # A shared physical bar found here is a possible double payment,
        # never a reason to update accounting or clear ownership.
        boq = project.get("boq", [])
        if not isinstance(boq, list):
            raise RebarOwnershipError("دفتر BOQ برای تطبیق میلگرد معتبر نیست")
        if boq:
            blockers.append("دفتر BOQ دارای "+str(len(boq))+" ردیف است؛ تطبیق مستقل مالکیت مالی لازم است")
        for i, row in enumerate(boq):
            if not isinstance(row, dict):
                raise RebarOwnershipError("ردیف BOQ برای کنترل مالکیت نامعتبر است")
            raw_params = row.get("params")
            params = {} if raw_params is None else raw_params
            if not isinstance(params, dict):
                raise RebarOwnershipError("پارامترهای BOQ برای کنترل میلگرد نامعتبر است")
            identities = [x for x in (row.get("physical_bar_id"), params.get("physical_bar_id"))
                          if x is not None]
            if any(not isinstance(x, str) or not x or x != x.strip() for x in identities):
                raise RebarOwnershipError("هویت فیزیکی میلگرد BOQ نامعتبر است")
            if len(set(identities)) > 1:
                raise RebarOwnershipError("دو هویت فیزیکی ناسازگار در یک ردیف BOQ ثبت شده است")
            if identities and identities[0] in group:
                blockers.append("میلگرد "+identities[0]+" در BOQ قبلی نیز آمده؛ احتمال پرداخت تکراری باید بررسی شود")
            description = str(row.get("description") or row.get("title") or "")
            code = str(row.get("item_code") or row.get("code") or "")
            if not identities and ("میلگرد" in description or "آرماتور" in description
                                   or "rebar" in code.casefold()):
                blockers.append("ردیف میلگرد BOQ شماره "+str(i)+" فاقد هویت فیزیکی قابل تطبیق است")
    return {"policy":POLICY,"status":"preview_only_not_integrated","commit_allowed":False,
            "project_id":data["project_id"],"source_fingerprint_sha256":_fingerprint(data),
            "physical_bar_count":len(paid),"physical_bar_paid_once":paid,
            "reference_only_claims":information,"connections":known_connections,
            "preview_total_kg":_num_string(total),"blockers":blockers,
            "scope_limitation":"فقط ادعاهای صریح ورودی؛ هیچ ادعایی درباره تطبیق تمام دیتایل‌های سازه، نقشه و متره تاریخی وجود ندارد"}
