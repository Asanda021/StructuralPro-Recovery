"""Opt-in, fail-closed in-process DWG reader for Windows-first CAD workflows.

Uses a *prebuilt, separately installed* ezdwg 0.17.0 wheel, with strict=True
conversion. No compiler, EXE build or license-bypassing DXF synthesis.
Do not treat a decoder output as a complete project/member/BOQ oracle.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib import metadata, util
from pathlib import Path
import tempfile

from core.drawings.dwg_converter import OfflineDWGConverter

PINNED_VERSION = "0.17.0"
MAX_DWG_BYTES = 50 * 1024 * 1024
ALLOWED_DWG_HEADERS = frozenset({"AC1015", "AC1018", "AC1021", "AC1024", "AC1027", "AC1032"})


class StrictPythonDWGError(RuntimeError):
    pass


@dataclass(frozen=True)
class StrictPythonDWGReceipt:
    output: Path
    source_sha256: str
    output_sha256: str
    decoder_version: str
    signature: str
    total_entities: int
    written_entities: int
    skipped_entities: int


class StrictPythonDWGProvider:
    @property
    def available(self) -> bool:
        if util.find_spec("ezdwg") is None:
            return False
        try:
            return metadata.version("ezdwg") == PINNED_VERSION
        except metadata.PackageNotFoundError:
            return False

    @staticmethod
    def _sha(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    def convert(self, source: str | Path) -> StrictPythonDWGReceipt:
        import ezdxf
        path = Path(source)
        if not path.is_file() or path.suffix.lower() != ".dwg":
            raise StrictPythonDWGError("Expected a real local DWG source file")
        if not 6 < path.stat().st_size <= MAX_DWG_BYTES:
            raise StrictPythonDWGError("DWG is empty or outside the approved size limit")
        header = OfflineDWGConverter.inspect_header(path)["code"]
        if header not in ALLOWED_DWG_HEADERS:
            raise StrictPythonDWGError("DWG version is not approved for strict Python decoding")
        if not self.available:
            raise StrictPythonDWGError("Pinned ezdwg[dxf]==0.17.0 prebuilt wheel is unavailable")
        original_sha = self._sha(path)
        import ezdwg
        import os
        fd, name = tempfile.mkstemp(prefix="structuralpro-ezdwg-strict-", suffix=".dxf")
        os.close(fd)
        out = Path(name)
        try:
            # Windows cannot overwrite a still-open named temporary output.\n            # Caller uses a dedicated temp file; it must not be reused as a stale artifact.
            out.unlink(missing_ok=True)
            result = ezdwg.to_dxf(str(path), str(out), strict=True)
            total = int(result.total_entities)
            written = int(result.written_entities)
            skipped = int(result.skipped_entities)
            if total <= 0 or skipped != 0 or written != total:
                raise StrictPythonDWGError("Strict DWG conversion did not preserve entity coverage")
            if not out.is_file() or out.stat().st_size <= 100:
                raise StrictPythonDWGError("Strict DWG reader produced no usable DXF")
            # Confirm exported DXF loads; actual engineering checks follow in the
            # canonical DWGTakeoffEngine._read_dxf and human-review gate.
            ezdxf.readfile(out)
            output_sha = self._sha(out)
            if self._sha(path) != original_sha:
                raise StrictPythonDWGError("Source DWG changed during strict conversion")
            return StrictPythonDWGReceipt(
                output=out, source_sha256=original_sha, output_sha256=output_sha,
                decoder_version=PINNED_VERSION, signature=header,
                total_entities=total, written_entities=written,
                skipped_entities=skipped,
            )
        except Exception:
            out.unlink(missing_ok=True)
            raise
