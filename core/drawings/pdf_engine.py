"""Fail-closed PDF drawing reader used by the Windows graphical takeoff UI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import math


@dataclass(frozen=True)
class PDFPage:
    number: int
    width_pt: float
    height_pt: float
    rotation: int = 0


@dataclass(frozen=True)
class SnapPoint:
    x: float
    y: float
    source: str = "manual"


class PDFDrawingEngine:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        if not self.path.is_file():
            raise ValueError(f"مسیر PDF یک فایل نیست: {self.path}")
        self._doc = None

    def open(self):
        if self._doc is not None:
            return self
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("برای نمایش واقعی PDF، وابستگی PyMuPDF باید نصب باشد.") from exc
        doc = None
        try:
            doc = fitz.open(str(self.path))
            if not getattr(doc, "is_pdf", False):
                raise ValueError("فایل انتخاب‌شده یک PDF معتبر نیست.")
            if getattr(doc, "needs_pass", False):
                raise RuntimeError("این PDF رمزگذاری شده است؛ ابتدا نسخه قابل‌خواندن را با مجوز لازم باز کن.")
            if len(doc) < 1:
                raise ValueError("فایل PDF هیچ صفحه قابل‌نمایشی ندارد.")
            for index, page in enumerate(doc):
                rect = page.rect
                values = (float(rect.width), float(rect.height))
                if not all(math.isfinite(v) and v > 0 for v in values):
                    raise ValueError(f"ابعاد صفحه {index + 1} در PDF معتبر نیست.")
        except Exception:
            if doc is not None:
                doc.close()
            raise
        self._doc = doc
        return self

    @property
    def page_count(self) -> int:
        self.open()
        return len(self._doc)

    def _page(self, page: int):
        self.open()
        try:
            page = int(page)
        except (TypeError, ValueError) as exc:
            raise ValueError("شماره صفحه باید عدد صحیح باشد.") from exc
        if not 1 <= page <= len(self._doc):
            raise IndexError(f"شماره صفحه خارج از محدوده PDF است: {page}")
        return self._doc[page - 1]

    def pages(self) -> list[PDFPage]:
        self.open()
        return [PDFPage(i + 1, float(p.rect.width), float(p.rect.height), int(p.rotation))
                for i, p in enumerate(self._doc)]

    def render(self, page: int, dpi: int = 120) -> bytes:
        if isinstance(dpi, bool) or not isinstance(dpi, int) or not 36 <= dpi <= 600:
            raise ValueError("وضوح نمایش PDF باید عدد صحیح بین ۳۶ و ۶۰۰ باشد.")
        pdf_page = self._page(page)
        pixels = math.ceil(pdf_page.rect.width * dpi / 72) * math.ceil(pdf_page.rect.height * dpi / 72)
        if pixels > 40_000_000:
            raise ValueError("ابعاد نقشه برای نمایش کامل در این وضوح بسیار بزرگ است؛ وضوح پایین‌تر انتخاب کنید")
        pix = pdf_page.get_pixmap(dpi=dpi, alpha=False)
        return pix.tobytes("png")

    def text(self, page: int) -> str:
        return self._page(page).get_text("text") or ""

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
            self._doc = None

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False

    @staticmethod
    def snap(point: tuple[float, float], candidates: Iterable[SnapPoint], tolerance: float = 8.0):
        try:
            x, y = float(point[0]), float(point[1])
            tolerance = float(tolerance)
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError("مختصات و تلورانس Snap باید عددی باشند.") from exc
        if not all(math.isfinite(v) for v in (x, y, tolerance)) or tolerance < 0:
            raise ValueError("مختصات و تلورانس Snap باید متناهی باشند و تلورانس منفی نباشد.")
        pts = list(candidates)
        if not pts:
            return (x, y)
        valid = []
        for candidate in pts:
            cx, cy = float(candidate.x), float(candidate.y)
            if not math.isfinite(cx) or not math.isfinite(cy):
                continue
            valid.append((math.hypot(cx - x, cy - y), cx, cy))
        if not valid:
            return (x, y)
        distance, cx, cy = min(valid)
        return (cx, cy) if distance <= tolerance else (x, y)
