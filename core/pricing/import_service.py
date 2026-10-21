"""Fail-closed price-list import with provenance and user-import support.

Supports CSV and real Excel workbooks (XLSX/XLSM). Excel data is normalized to
StructuralPro's canonical price-item schema before it reaches the catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import csv
import math
import re
from core.commercial.exact_values import number,wire
from io import StringIO, BytesIO

from core.pricing.catalog import PriceCatalog, PriceItem
from core.pricing.source_registry import PriceSource, PriceSourceRegistry


@dataclass(frozen=True)
class ImportReceipt:
    source_id: str
    year: int
    discipline: str
    filename: str
    sha256: str
    rows: int
    verified_source: bool
    imported_at: str
    format: str = "csv"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class PricebookImportService:
    """Import official/user datasets without inventing source provenance."""

    _ALIASES = {
        "year": {"year", "سال", "سال فهرست بها", "سال فهرست‌بها"},
        "group": {"group", "رشته", "دسته", "گروه", "دیسپلین", "رشته کاری"},
        "chapter": {"chapter", "فصل", "فصل کاری", "فصل فهرست بها", "فصل فهرست‌بها"},
        "code": {"code", "کد", "شماره ردیف", "شماره ردیف فهرست بها", "شماره فهرست بها", "شماره فهرست‌بها", "ردیف"},
        "description": {"description", "شرح", "شرح ردیف", "شرح عملیات"},
        "unit": {"unit", "واحد", "واحد اندازه گیری", "واحد اندازه‌گیری"},
        "unit_price": {"unit_price", "unit price", "بهای واحد", "بهای واحد (ریال)", "قیمت واحد", "قیمت", "بها"},
        "analysis": {"analysis", "تجزیه", "تجزیه بها", "آنالیز"},
        "notes": {"notes", "یادداشت", "توضیحات", "توضیح"},
    }

    def __init__(self, catalog: PriceCatalog | None = None, registry: PriceSourceRegistry | None = None):
        self.catalog = catalog or PriceCatalog()
        self.registry = registry or PriceSourceRegistry()

    @staticmethod
    def _norm(value: Any) -> str:
        return " ".join(str(value or "").strip().replace("‌", " ").split()).casefold()

    @classmethod
    def _map_headers(cls, headers: list[Any]) -> dict[str, int]:
        normalized = [cls._norm(x) for x in headers]
        mapping: dict[str, int] = {}
        for field, aliases in cls._ALIASES.items():
            aliases_norm = {cls._norm(x) for x in aliases}
            for idx, header in enumerate(normalized):
                if header in aliases_norm:
                    mapping[field] = idx
                    break
        return mapping

    @staticmethod
    def _number(value: Any):
        if isinstance(value,bool) or value is None:raise ValueError("بهای واحد یا سال معتبر لازم است")
        raw=str(value).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
        raw=raw.replace('٫','.')
        if any(c in raw for c in (',','٬',' ')):
            if not re.fullmatch(r"[+]?[0-9]{1,3}(?:([,٬ ])[0-9]{3})+(?:\.[0-9]+)?",raw):
                raise ValueError("جداکننده عدد فهرست‌بها مبهم یا نامعتبر است")
            separators={c for c in raw if c in ',٬ '}
            if len(separators)!=1:raise ValueError("جداکننده‌های ناسازگار عدد")
            raw=raw.replace(next(iter(separators)),'')
        return wire(number(raw,'عدد فهرست‌بها'))

    @classmethod
    def _year(cls,value: Any)->int:
        n=number(cls._number(value),'سال')
        if n!=n.to_integral_value() or n<=0:raise ValueError("سال فهرست‌بها باید عدد صحیح مثبت باشد")
        return int(n)

    @classmethod
    def _rows_from_excel(cls, path: Path, *, fallback_year: int, raw_bytes: bytes | None = None) -> list[PriceItem]:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("برای ورود Excel باید openpyxl نصب باشد.") from exc
        wb = load_workbook(BytesIO(raw_bytes) if raw_bytes is not None else path, read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                rows = ws.iter_rows(values_only=True)
                headers = next(rows, None)
                if not headers:
                    continue
                mapping = cls._map_headers(list(headers))
                required = {"code", "description", "unit", "unit_price"}
                if not required.issubset(mapping):
                    continue
                out: list[PriceItem] = []
                for raw in rows:
                    values = list(raw)
                    def val(field: str, default: Any = ""):
                        idx = mapping.get(field)
                        return values[idx] if idx is not None and idx < len(values) else default
                    code = str(val("code")).strip()
                    desc = str(val("description")).strip()
                    unit = str(val("unit")).strip()
                    if not code or not desc or not unit:
                        continue
                    year_value = val("year", fallback_year)
                    group = str(val("group", "")).strip()
                    chapter = str(val("chapter", "")).strip()
                    raw_price=val("unit_price")
                    if isinstance(raw_price,(int,float)) and not isinstance(raw_price,bool) and len(number(raw_price,'قیمت Excel').as_tuple().digits)>15:
                        raise ValueError("قیمت بلند Excel باید سلول متنی باشد؛ رقم‌های قبلاً ازدست‌رفته حدس زده نمی‌شوند")
                    price = cls._number(raw_price)
                    out.append(PriceItem(
                        year=cls._year(year_value),
                        group=group, chapter=chapter, code=code,
                        description=desc, unit=unit, unit_price=price,
                        analysis=str(val("analysis", "") or ""),
                        notes=str(val("notes", "") or ""),
                    ))
                if out:
                    return out
            raise ValueError(
                "ساختار فایل Excel قابل تشخیص نیست. ستون‌های ضروری: کد/شماره ردیف، شرح، واحد و بهای واحد."
            )
        finally:
            wb.close()

    @classmethod
    def _rows_from_pdf(cls, path: Path, *, fallback_year: int, raw_bytes: bytes | None = None) -> list[PriceItem]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("برای ورود PDF باید PyMuPDF نصب باشد.") from exc
        text_parts=[]
        document = fitz.open(stream=raw_bytes, filetype="pdf") if raw_bytes is not None else fitz.open(path)
        with document as doc:
            for page in doc:
                text_parts.append(page.get_text("text") or "")
        text="\n".join(text_parts)
        if not text.strip():
            raise ValueError("PDF اسکن‌شده یا تصویری است و برای جلوگیری از حدس‌زدن رد شد.")
        out=[]
        for line in text.splitlines():
            cols=[x.strip() for x in line.split("|") if x.strip()]
            if len(cols)<4: continue
            if {"code","description","unit","unit_price"}.issubset(cls._map_headers(cols)):continue
            code,desc,unit,raw_price=cols[0],cols[1],cols[2],cols[3]
            try: price=cls._number(raw_price)
            except ValueError as e:raise ValueError("قیمت ردیف PDF نامعتبر است") from e
            if code and desc and unit and number(price,"قیمت")>=0:
                out.append(PriceItem(year=fallback_year,group="",chapter="",code=code,description=desc,unit=unit,unit_price=price))
        if not out:
            raise ValueError("PDF قابل تشخیص نیست؛ PDF باید متن واقعی با ستون‌های کد، شرح، واحد و بهای واحد داشته باشد.")
        return out

    @classmethod
    def _rows_from_csv(cls, path: Path, *, fallback_year: int, raw_bytes: bytes | None = None) -> list[PriceItem]:
        text = raw_bytes.decode("utf-8-sig") if raw_bytes is not None else path.read_text(encoding="utf-8-sig")
        reader = csv.reader(StringIO(text))
        headers = next(reader, None)
        if not headers:
            return []
        mapping = cls._map_headers(headers)
        required = {"code", "description", "unit", "unit_price"}
        if not required.issubset(mapping):
            raise ValueError("ساختار CSV قابل تشخیص نیست. ستون‌های ضروری: کد، شرح، واحد و بهای واحد.")
        out: list[PriceItem] = []
        for raw in reader:
            values = list(raw)
            def val(field: str, default: Any = ""):
                idx = mapping.get(field)
                return values[idx] if idx is not None and idx < len(values) else default
            out.append(PriceItem(
                year=cls._year(val("year", fallback_year)),
                group=str(val("group", "") or ""),
                chapter=str(val("chapter", "") or ""),
                code=str(val("code", "") or "").strip(),
                description=str(val("description", "") or "").strip(),
                unit=str(val("unit", "") or "").strip(),
                unit_price=cls._number(val("unit_price")),
                analysis=str(val("analysis", "") or ""),
                notes=str(val("notes", "") or ""),
            ))
        return out

    def _load_items(self, path: Path, *, fallback_year: int, raw_bytes: bytes | None = None) -> tuple[list[PriceItem], str]:
        suffix = path.suffix.casefold()
        if suffix in {".xlsx", ".xlsm"}:
            return self._rows_from_excel(path, fallback_year=fallback_year, raw_bytes=raw_bytes), "excel"
        if suffix == ".csv":
            return self._rows_from_csv(path, fallback_year=fallback_year, raw_bytes=raw_bytes), "csv"
        if suffix == ".pdf":
            return self._rows_from_pdf(path, fallback_year=fallback_year, raw_bytes=raw_bytes), "pdf"
        raise ValueError("فرمت پشتیبانی‌شده برای فهرست‌بها: XLSX، XLSM، CSV یا PDF متنی")

    def inspect(self, path: str | Path, *, year: int, discipline: str = "building",
                source_id: str = "user-import") -> dict[str, Any]:
        info, _ = self._inspect_items(path, year=year, discipline=discipline, source_id=source_id)
        return info

    def _inspect_items(self, path: str | Path, *, year: int, discipline: str,
                       source_id: str) -> tuple[dict[str, Any], list[PriceItem]]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        year = self._year(year)
        raw_bytes = p.read_bytes()
        items, file_format = self._load_items(p, fallback_year=year, raw_bytes=raw_bytes)
        errors: list[str] = []
        codes: set[str] = set()
        for item in items:
            if item.year != year:
                errors.append(f"{item.code}: سال ردیف با سال درخواستی منطبق نیست")
            if item.code in codes:
                errors.append(f"{item.code}: کد فهرست‌بها تکراری است")
            codes.add(item.code)
            try:
                self.catalog._validate_item(item)
            except (ValueError, TypeError) as exc:
                errors.append(f"{item.code or '?'}: {exc}")
        if not items:
            errors.append("هیچ ردیف قابل استفاده‌ای در فایل پیدا نشد.")
        source = self.registry.get(year, discipline, source_id)
        info = {
            "path": str(p), "filename": p.name, "year": year,
            "discipline": discipline, "source_id": source_id,
            "sha256": sha256(raw_bytes).hexdigest(), "rows": len(items),
            "valid": not errors, "errors": errors[:20],
            "verified_source": bool(source and source.verified and
                                    self.registry.verify_record(source, sha256(raw_bytes).hexdigest())),
            "format": file_format,
        }
        return info, items

    def import_file(self, path: str | Path, *, year: int, discipline: str = "building",
                    source_id: str = "user-import", require_verified_source: bool = False,
                    replace_year: bool = True) -> ImportReceipt:
        p = Path(path)
        info, items = self._inspect_items(p, year=year, discipline=discipline, source_id=source_id)
        if not info["valid"]:
            raise ValueError("اعتبارسنجی فهرست‌بها ناموفق بود: " + "; ".join(info["errors"][:5]))
        if require_verified_source and not info["verified_source"]:
            raise PermissionError(
                "ورود رسمی/تأییدشده نیازمند منبع ثبت‌شده و SHA-256 منطبق است؛ حالت ورود فایل کاربر آزاد است."
            )
        file_format = info["format"]
        normalized = [
            PriceItem(
                year=item.year or int(year), group=item.group, chapter=item.chapter,
                code=item.code, description=item.description, unit=item.unit,
                unit_price=item.unit_price, analysis=item.analysis, notes=item.notes,
            ) for item in items
        ]
        if replace_year:
            years = {x.year for x in normalized}
            self.catalog._items = {
                k: v for k, v in self.catalog._items.items() if k[0] not in years
            }
        for item in normalized:
            self.catalog.add(item)
        return ImportReceipt(
            source_id=source_id, year=year, discipline=discipline, filename=p.name,
            sha256=info["sha256"], rows=len(normalized),
            verified_source=info["verified_source"],
            imported_at=datetime.now(timezone.utc).isoformat(), format=file_format,
        )


def verify_reviewed_rates(path: Path, review: dict) -> bool:
    """Verify structured source rates without rewriting old, rounded snapshots.

    Opaque historical evidence remains an explicit human review, rather than
    being represented as a parsed exact import. New imports require parsing.
    """
    raw=path.read_bytes();suffix=path.suffix.lower();version=review.get('numeric_encoding_version',0)
    if sha256(raw).hexdigest()!=str(review.get('sha256','')).lower():raise ValueError('منبع قیمت هنگام کنترل تغییر کرده است')
    if suffix=='.json':
        import json
        source=json.loads(raw)
        if not isinstance(source,dict) or not all(isinstance(x,dict) and 'unit_price' in x and 'unit' in x for x in source.values()):
            if version==2:raise ValueError('منبع قیمت دقیق قابل تشخیص نیست')
            return False
    elif suffix=='.csv':
        headers=next(csv.reader(StringIO(raw.decode('utf-8-sig'))),[])
        if not {'code','description','unit','unit_price'}.issubset(PricebookImportService._map_headers(headers)):
            if version==2:raise ValueError('ستون‌های منبع قیمت دقیق موجود نیستند')
            return False
        items=PricebookImportService._rows_from_csv(path,fallback_year=(review.get('receipt') or {}).get('year',0),raw_bytes=raw)
        if len({x.code for x in items})!=len(items):raise ValueError('منبع قیمت تکراری است')
        source={x.code:{'unit':x.unit,'unit_price':x.unit_price} for x in items}
    elif suffix in {'.xlsx','.xlsm','.pdf'}:
        year=(review.get('receipt') or {}).get('year')
        if year is None:
            if version==2:raise ValueError('سال منبع قیمت دقیق نامعلوم است')
            return False
        items,_=PricebookImportService()._load_items(path,fallback_year=year,raw_bytes=raw)
        if len({x.code for x in items})!=len(items):raise ValueError('منبع قیمت تکراری است')
        source={x.code:{'unit':x.unit,'unit_price':x.unit_price} for x in items}
    else:
        if version==2:raise ValueError('قالب منبع قیمت دقیق نامعلوم است')
        return False
    for code,row in review['rows_by_code'].items():
        actual=source.get(code)
        if not actual or not PriceCatalog._units_compatible(actual['unit'],row['unit']) or number(actual['unit_price'],'قیمت منبع')!=number(row['unit_price'],'قیمت ذخیره‌شده'):
            raise ValueError('قیمت ذخیره‌شده با رقم‌های منبع واقعی منطبق نیست؛ ورود و بازبینی مجدد لازم است')
    return True
