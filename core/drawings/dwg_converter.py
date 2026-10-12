"""Offline DWG conversion boundary with deterministic executable discovery and fail-closed diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os, shutil, subprocess, tempfile

_DWG_VERSIONS = {
    "AC1009": "R12",
    "AC1012": "R13",
    "AC1014": "R14",
    "AC1015": "2000",
    "AC1018": "2004",
    "AC1021": "2007",
    "AC1024": "2010",
    "AC1027": "2013",
    "AC1032": "2018",
    "AC1036": "2021",
    "AC1037": "2024",
}


@dataclass(frozen=True)
class ConverterResult:
    source: Path
    output: Path
    converter: str


class DWGConversionError(RuntimeError):
    """Actionable DWG conversion failure exposed to the UI boundary."""


class UnsupportedDWGVersionError(DWGConversionError):
    """DWG header is readable but its version is outside the supported boundary."""


class CorruptDWGError(DWGConversionError):
    """The input does not contain a valid DWG signature."""


class OfflineDWGConverter:
    def __init__(self, executable: str | None = None):
        self.executable = (
            executable
            or os.getenv("STRUCTURALPRO_DWG_CONVERTER")
            or shutil.which("dwg2dxf")
            or shutil.which("ODAFileConverter")
        )

    @property
    def available(self) -> bool:
        return bool(self.executable)

    @staticmethod
    def inspect_header(source: str | Path) -> dict[str, str]:
        src = Path(source)
        try:
            with src.open("rb") as fh:
                header = fh.read(6)
        except OSError as exc:
            raise DWGConversionError(f"امکان خواندن فایل DWG وجود ندارد: {exc}") from exc

        signature = header.decode("ascii", errors="replace")
        if not signature.startswith("AC10"):
            raise CorruptDWGError(
                "فایل انتخاب‌شده امضای معتبر DWG ندارد یا خراب است."
            )
        version = _DWG_VERSIONS.get(signature)
        if version is None:
            raise UnsupportedDWGVersionError(
                f"نسخه DWG با کد {signature} در مسیر فعلی پشتیبانی نمی‌شود."
            )
        return {"code": signature, "version": version}

    def convert(self, source: str | Path, output_dir: str | Path | None = None) -> ConverterResult:
        src = Path(source)
        if not src.exists():
            raise FileNotFoundError(f"فایل DWG پیدا نشد: {src}")
        if not src.is_file():
            raise DWGConversionError(f"مسیر DWG یک فایل نیست: {src}")
        if src.suffix.lower() != ".dwg":
            raise ValueError("source must be .dwg")
        if src.stat().st_size < 6:
            raise CorruptDWGError("فایل DWG خالی یا ناقص است.")

        header = self.inspect_header(src)
        if not self.executable:
            raise DWGConversionError(
                "DWG Reader/Converter فعال نیست. برای خواندن آفلاین DWG باید "
                "ODAFileConverter یا dwg2dxf نصب و در PATH قرار گیرد، یا "
                "STRUCTURALPRO_DWG_CONVERTER به مسیر اجرایی تنظیم شود."
            )

        out = Path(output_dir or tempfile.mkdtemp(prefix="structuralpro_dwg_"))
        out.mkdir(parents=True, exist_ok=True)
        target = out / (src.stem + ".dxf")
        name = Path(self.executable).name.lower()

        if "odafileconverter" in name:
            odir = out / "oda"
            odir.mkdir(exist_ok=True)
            # Remove only the expected artifact so a stale DXF cannot masquerade as
            # a successful conversion after the converter exits without writing.
            target = odir / (src.stem + ".dxf")
            target.unlink(missing_ok=True)
            proc = subprocess.run(
                [self.executable, str(src.parent), str(odir), "ACAD2018", "DXF", "0", "1", src.name],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode:
                detail = (proc.stderr or proc.stdout or "").strip()
                raise DWGConversionError(
                    f"تبدیل DWG با ODAFileConverter شکست خورد "
                    f"(نسخه {header['version']}): {detail or 'خطای نامشخص مبدل'}"
                )
            if not target.is_file():
                matches = [p for p in odir.glob("*.dxf") if p.stem.casefold() == src.stem.casefold()]
                if len(matches) == 1:
                    target = matches[0]
        else:
            target.unlink(missing_ok=True)
            proc = subprocess.run(
                [self.executable, str(src), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode:
                detail = (proc.stderr or proc.stdout or "").strip()
                raise DWGConversionError(
                    f"تبدیل DWG شکست خورد (نسخه {header['version']}): "
                    f"{detail or 'خطای نامشخص مبدل'}"
                )

        if not target.is_file() or target.stat().st_size == 0:
            raise DWGConversionError(
                "مبدل اجرا شد اما فایل DXF خروجی تولید نشد؛ فایل DWG یا تنظیمات مبدل را بررسی کنید."
            )

        # A file on disk is not proof of a valid conversion. Parse it with the
        # real DXF reader used by the takeoff pipeline before returning it.
        try:
            import ezdxf
            converted_doc = ezdxf.readfile(str(target))
            list(converted_doc.modelspace())
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise DWGConversionError(
                "مبدل فایل DXF قابل‌خواندن تولید نکرد؛ خروجی نامعتبر است و برای متره پذیرفته نشد."
            ) from exc

        return ConverterResult(src, target, str(self.executable))
