"""Cancellable, off-UI-thread opening of a source-verified IFC 3D document.

Cancellation is cooperative at validated checkpoints; an active IfcOpenShell
parse cannot be interrupted inside the third-party native parser. Cancelled
results are discarded and never presented as an approved or partial model.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal

from core.bim.ifc import DeepIFCAdapter
from core.drawings.source_mesh3d import VerifiedScene3D


def digest_file(path: Path, cancel: Event | None = None) -> str:
    """Bounded-memory SHA-256 calculation of the *actual* IFC source."""
    checksum = sha256()
    with path.open("rb") as stream:
        while True:
            if cancel is not None and cancel.is_set():
                raise InterruptedError("بارگذاری مدل سه‌بعدی لغو شد.")
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            checksum.update(chunk)
    return checksum.hexdigest()


class IFC3DLoadSignals(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int)
    stage = Signal(int, str)


class IFC3DLoadJob(QRunnable):
    """One immutable request, tied to a token and a user-selectable cancellation."""

    def __init__(self, *, token: int, path: str, revision: str, expected_sha: str):
        super().__init__()
        self.token = token
        self.path = str(path)
        self.revision = str(revision)
        self.expected_sha = str(expected_sha)
        self.cancellation = Event()
        self.signals = IFC3DLoadSignals()

    def cancel(self):
        self.cancellation.set()

    def _checkpoint(self):
        if self.cancellation.is_set():
            raise InterruptedError("بارگذاری مدل سه‌بعدی لغو شد.")

    def run(self):
        try:
            self._checkpoint()
            source = Path(self.path)
            self.signals.stage.emit(self.token, "بررسی هش منبع IFC…")
            if digest_file(source, self.cancellation) != self.expected_sha:
                raise ValueError("هش IFC تغییر کرده است؛ بارگذاری سه‌بعدی مسدود شد.")
            self._checkpoint()
            self.signals.stage.emit(self.token, "خواندن هندسه واقعی IFC در پس‌زمینه…")
            contract = DeepIFCAdapter().read_display_contract(
                source, revision=self.revision, max_triangles=40_000)
            self._checkpoint()
            if contract["source_sha256"] != self.expected_sha:
                raise ValueError("هویت IFC در مدل سه‌بعدی و سند فعال یکسان نیست.")
            self.signals.stage.emit(self.token, "اعتبارسنجی عضو و هندسه مدل…")
            scene = VerifiedScene3D(contract)
            self._checkpoint()
            if digest_file(source, self.cancellation) != self.expected_sha:
                raise ValueError("منبع IFC حین بارگذاری تغییر کرده است.")
            self._checkpoint()
            self.signals.finished.emit(self.token, scene)
        except InterruptedError:
            self.signals.cancelled.emit(self.token)
        except Exception as exc:
            if self.cancellation.is_set():
                self.signals.cancelled.emit(self.token)
            else:
                self.signals.failed.emit(self.token, str(exc))
