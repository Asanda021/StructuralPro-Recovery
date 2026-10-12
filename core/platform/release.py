"""Release metadata and offline license primitives for StructuralPro."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "VERSION"


def load_version() -> str:
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError("VERSION must use MAJOR.MINOR.PATCH")
    return value


@dataclass(frozen=True)
class ReleaseInfo:
    name: str
    version: str
    channel: str = "stable"

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version, "channel": self.channel}


@dataclass(frozen=True)
class LicenseRecord:
    product: str
    license_id: str
    customer: str
    expires_on: str = ""
    features: tuple[str, ...] = ()
    issuer: str = ""

    def payload(self) -> dict:
        return {
            "product": self.product,
            "license_id": self.license_id,
            "customer": self.customer,
            "expires_on": self.expires_on,
            "features": list(self.features),
            "issuer": self.issuer,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def fingerprint(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()

    def is_expired(self, on: date | None = None) -> bool:
        if not self.expires_on:
            return False
        try:
            expiry = date.fromisoformat(self.expires_on)
        except ValueError:
            return True
        return (on or date.today()) > expiry

    def has_feature(self, feature: str) -> bool:
        return bool(feature) and feature in self.features


class LicenseVerifier:
    """Fail-closed verifier boundary; private signing material never belongs here."""

    def __init__(
        self,
        verify_signature: Callable[[bytes, str], bool],
        expected_product: str = "StructuralPro",
        revoked_license_ids: Iterable[str] = (),
        today: Callable[[], date] = date.today,
    ):
        self._verify_signature = verify_signature
        self._expected_product = expected_product
        self._revoked_license_ids = frozenset(revoked_license_ids)
        self._today = today

    def _valid_record(self, record: LicenseRecord) -> bool:
        if record.product != self._expected_product:
            return False
        if not record.license_id.strip() or not record.customer.strip():
            return False
        if not record.issuer.strip():
            return False
        if record.license_id in self._revoked_license_ids:
            return False
        if len(set(record.features)) != len(record.features):
            return False
        if record.expires_on:
            try:
                date.fromisoformat(record.expires_on)
            except ValueError:
                return False
            if record.is_expired(self._today()):
                return False
        return True

    def verify(self, record: LicenseRecord, signature: str) -> bool:
        if not signature or not self._valid_record(record):
            return False
        try:
            return bool(self._verify_signature(record.canonical_bytes(), signature))
        except Exception:
            return False
