"""Production DWG provider backed by the MIT-licensed ACadSharp bridge.

Flow:
    DWG -> ACadSharp DwgReader -> DXF -> ezdxf -> extraction/takeoff
"""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from core.cad.ezdxf_provider_v1 import DXFDocumentEvidence, read_dxf

class DWGProviderError(ValueError):
    """Raised when a DWG cannot be converted and verified."""

@dataclass(frozen=True)
class DWGConverterConfig:
    executable: str | None = None
    timeout_seconds: int = 120

class ACadSharpDWGProvider:
    ENV_NAME = "STRUCTURALPRO_DWG_BRIDGE"
    DEFAULT_RELATIVE = (
        Path("tools") / "acadsharp-dwg-bridge" / "bin" / "Release" /
        "net8.0" / "win-x64" / "publish" / "StructuralPro.DwgBridge.exe"
    )

    def __init__(self, config: DWGConverterConfig | None = None) -> None:
        config = config or DWGConverterConfig()
        if config.timeout_seconds <= 0:
            raise DWGProviderError("DWG bridge timeout must be positive")
        self.config = config

    @property
    def available(self) -> bool:
        """Whether the authorized bridge can be resolved on this machine."""
        try:
            self._resolve_executable()
        except DWGProviderError:
            return False
        return True

    def _resolve_executable(self) -> str:
        configured = self.config.executable or os.environ.get(self.ENV_NAME)
        if configured:
            resolved = shutil.which(configured)
            if resolved:
                return resolved
            candidate = Path(configured)
            if candidate.is_file():
                return str(candidate)
        repo_default = Path(__file__).resolve().parents[2] / self.DEFAULT_RELATIVE
        if repo_default.is_file():
            return str(repo_default)
        raise DWGProviderError(
            "ACadSharp DWG bridge was not found. Install/build the authorized "
            "StructuralPro.DwgBridge executable and configure STRUCTURALPRO_DWG_BRIDGE."
        )

    def convert(self, source: str | Path) -> Path:
        input_path = Path(source)
        if input_path.suffix.lower() != ".dwg":
            raise DWGProviderError("DWG provider accepts .dwg only")
        if not input_path.is_file():
            raise DWGProviderError("DWG source file does not exist")
        executable = self._resolve_executable()
        fd, output_name = tempfile.mkstemp(prefix="structuralpro-acadsharp-", suffix=".dxf")
        os.close(fd)
        output = Path(output_name)
        try:
            result = subprocess.run(
                [executable, str(input_path.resolve()), str(output)],
                check=False, capture_output=True, text=True,
                timeout=self.config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            output.unlink(missing_ok=True)
            raise DWGProviderError("ACadSharp DWG conversion timed out") from exc
        except OSError as exc:
            output.unlink(missing_ok=True)
            raise DWGProviderError(f"ACadSharp DWG bridge could not be executed: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "no bridge diagnostics").strip()
            output.unlink(missing_ok=True)
            raise DWGProviderError(
                f"ACadSharp DWG conversion failed with exit code {result.returncode}: {detail}"
            )
        if not output.is_file() or output.stat().st_size == 0:
            output.unlink(missing_ok=True)
            raise DWGProviderError("ACadSharp bridge produced no DXF artifact")
        try:
            read_dxf(output)
        except Exception as exc:
            output.unlink(missing_ok=True)
            raise DWGProviderError("ACadSharp bridge produced an invalid DXF artifact") from exc
        return output

    def read(self, source: str | Path) -> DXFDocumentEvidence:
        converted = self.convert(source)
        try:
            return read_dxf(converted)
        finally:
            converted.unlink(missing_ok=True)

ExternalDWGConverterProvider = ACadSharpDWGProvider
