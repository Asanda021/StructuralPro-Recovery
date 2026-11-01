"""Offline DWG conversion boundary with deterministic executable discovery and fail-closed diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os, shutil, subprocess, tempfile, hashlib

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
    source_sha256: str = ""
    output_sha256: str = ""
    dwg_version: str = ""
    exit_code: int = 0


class DWGConversionError(RuntimeError):
    """Actionable DWG conversion failure exposed to the UI boundary."""


class UnsupportedDWGVersionError(DWGConversionError):
    """DWG header is readable but its version is outside the supported boundary."""


class CorruptDWGError(DWGConversionError):
    """The input does not contain a valid DWG signature."""


class OfflineDWGConverter:
    def __init__(self, executable: str | None = None, timeout_seconds: int = 120):
        if isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,int) or not 1<=timeout_seconds<=600:raise ValueError("مهلت تبدیل باید صحیح بین ۱ و ۶۰۰ ثانیه باشد")
        self.timeout_seconds=timeout_seconds
        self.executable = (
            executable
            or os.getenv("STRUCTURALPRO_DWG_CONVERTER")
            or shutil.which("dwg2dxf")
            or shutil.which("ODAFileConverter")
        )

    def _run(self, command, **kwargs):
        # Locale-specific diagnostics must not turn a valid converter run into
        # UnicodeDecodeError, particularly with Persian Windows paths.
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
        try:return subprocess.run(command,timeout=self.timeout_seconds,**kwargs)
        except subprocess.TimeoutExpired as exc:raise DWGConversionError("مهلت تبدیل DWG پایان یافت؛ هیچ خروجی برای متره تأیید نشد") from exc
        except OSError as exc:raise DWGConversionError("اجرای مبدل DWG ممکن نیست") from exc

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
        out = Path(output_dir) if output_dir is not None else Path(tempfile.mkdtemp(prefix="structuralpro_dwg_"))
        owned_targets: list[Path] = []
        try:
            return self._convert(source, out, owned_targets)
        except BaseException:
            # Only our expected result belongs to this operation. Preserve
            # unrelated user files in an explicitly supplied output directory.
            for candidate in owned_targets:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass  # Preserve the original converter/validation failure.
            if output_dir is None:
                for directory in (out / "oda", out):
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
            raise

    def _convert(self, source: str | Path, output_dir: Path, owned_targets: list[Path]) -> ConverterResult:
        src = Path(source)
        if not src.exists():
            raise FileNotFoundError(f"فایل DWG پیدا نشد: {src}")
        if not src.is_file():
            raise DWGConversionError(f"مسیر DWG یک فایل نیست: {src}")
        if src.suffix.lower() != ".dwg":
            raise ValueError("source must be .dwg")
        if src.stat().st_size < 6:
            raise CorruptDWGError("فایل DWG خالی یا ناقص است.")

        def identity(path):
            stat = path.stat()
            return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns
        def digest(path):
            with path.open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").hexdigest()
        source_identity = identity(src)
        source_digest=digest(src)
        header = self.inspect_header(src)
        if not self.executable:
            raise DWGConversionError(
                "DWG Reader/Converter فعال نیست. برای خواندن آفلاین DWG باید "
                "ODAFileConverter یا dwg2dxf نصب و در PATH قرار گیرد، یا "
                "STRUCTURALPRO_DWG_CONVERTER به مسیر اجرایی تنظیم شود."
            )

        out = output_dir
        out.mkdir(parents=True, exist_ok=True)
        target = out / (src.stem + ".dxf")
        name = Path(self.executable).name.lower()

        if "odafileconverter" in name:
            odir = out / "oda"
            odir.mkdir(exist_ok=True)
            # Remove only the expected artifact so a stale DXF cannot masquerade as
            # a successful conversion after the converter exits without writing.
            target = odir / (src.stem + ".dxf")
            owned_targets.append(target)
            target.unlink(missing_ok=True)
            proc = self._run(
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
                    owned_targets.append(target)
        else:
            owned_targets.append(target)
            target.unlink(missing_ok=True)
            # GNU LibreDWG dwg2dxf accepts -o OUTPUT INPUT; the old
            # positional INPUT OUTPUT call treats OUTPUT as a second input
            # and never creates the required DXF.  Use the documented CLI,
            # without weakening DXF parse/integrity checks below.
            if "dwg2dxf" in name:
                command = [self.executable, "-o", str(target), str(src)]
            else:
                command = [self.executable, str(src), str(target)]
            proc = self._run(
                command,
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
        if target.is_symlink():
            raise DWGConversionError("خروجی مبدل نباید پیوند نمادین باشد")

        # A file on disk is not proof of a valid conversion. Parse it with the
        # real DXF reader used by the takeoff pipeline before returning it.
        try:
            import ezdxf
            output_identity = identity(target)
            output_digest = digest(target)
            converted_doc = ezdxf.readfile(str(target))
            list(converted_doc.modelspace())
            if identity(target) != output_identity or digest(target) != output_digest:
                raise DWGConversionError("خروجی DXF هنگام اعتبارسنجی تغییر کرده است")
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise DWGConversionError(
                "مبدل فایل DXF قابل‌خواندن تولید نکرد؛ خروجی نامعتبر است و برای متره پذیرفته نشد."
            ) from exc

        if identity(src) != source_identity or digest(src)!=source_digest:
            target.unlink(missing_ok=True)
            raise DWGConversionError("فایل DWG هنگام تبدیل تغییر کرده است")
        return ConverterResult(src,target,str(self.executable),source_digest,output_digest,header["version"],proc.returncode)
