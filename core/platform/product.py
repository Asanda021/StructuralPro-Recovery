"""Commercial product packaging contract for StructuralPro.

The matrix is intentionally domain-agnostic: StructuralPro is a comprehensive
construction takeoff/BOQ/estimating product, not a concrete-only application.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import os


class ProductEdition(str, Enum):
    LIGHT = "light"
    STANDARD = "standard"
    PRO = "pro"
    ENTERPRISE = "enterprise"


FEATURES = (
    "takeoff.boq",
    "takeoff.drawing",
    "takeoff.pdf",
    "takeoff.cad",
    "takeoff.bim",
    "takeoff.ai",
    "revision.compare",
    "estimate.cost",
    "reports.export",
    "collaboration",
    "offline.core",
    "local.ai",
    "api.integration",
    "enterprise.controls",
)


@dataclass(frozen=True)
class ProductProfile:
    edition: ProductEdition
    features: frozenset[str]

    def supports(self, feature: str) -> bool:
        return bool(feature) and feature in self.features


def _profile(edition: ProductEdition, *features: str) -> ProductProfile:
    unknown = set(features) - set(FEATURES)
    if unknown:
        raise ValueError(f"Unknown product features: {sorted(unknown)}")
    return ProductProfile(edition, frozenset(features))


_PRODUCT_PROFILES = {
    ProductEdition.LIGHT: _profile(
        ProductEdition.LIGHT,
        "takeoff.boq",
        "takeoff.drawing",
        "takeoff.pdf",
        "reports.export",
        "offline.core",
    ),
    ProductEdition.STANDARD: _profile(
        ProductEdition.STANDARD,
        "takeoff.boq",
        "takeoff.drawing",
        "takeoff.pdf",
        "takeoff.cad",
        "takeoff.bim",
        "revision.compare",
        "estimate.cost",
        "reports.export",
        "offline.core",
        "local.ai",
    ),
    ProductEdition.PRO: _profile(
        ProductEdition.PRO,
        "takeoff.boq",
        "takeoff.drawing",
        "takeoff.pdf",
        "takeoff.cad",
        "takeoff.bim",
        "takeoff.ai",
        "revision.compare",
        "estimate.cost",
        "reports.export",
        "collaboration",
        "offline.core",
        "local.ai",
        "api.integration",
    ),
    ProductEdition.ENTERPRISE: _profile(
        ProductEdition.ENTERPRISE,
        *FEATURES,
    ),
}


def product_profile(edition: ProductEdition | str) -> ProductProfile:
    try:
        edition = ProductEdition(edition)
    except ValueError as exc:
        raise ValueError(f"Unsupported product edition: {edition!r}") from exc
    return _PRODUCT_PROFILES[edition]


def feature_matrix() -> dict[str, tuple[str, ...]]:
    return {
        edition.value: tuple(
            feature for feature in FEATURES if profile.supports(feature)
        )
        for edition, profile in _PRODUCT_PROFILES.items()
    }


def validate_license_features(
    edition: ProductEdition | str,
    licensed_features: tuple[str, ...] | list[str] | set[str],
) -> bool:
    """Return true only when every licensed feature belongs to the edition."""
    profile = product_profile(edition)
    requested = set(licensed_features)
    return requested <= profile.features


def packaged_edition(
    bundle_dir: str | Path | None = None,
    *,
    fail_closed: bool = False,
) -> ProductEdition | None:
    """Read the edition marker shipped beside the Windows payload.

    CI/release builds always ship EDITION. Development checkouts may omit it;
    in that case None is returned unless fail_closed=True.
    """
    raw = os.getenv("STRUCTURALPRO_EDITION", "").strip().lower()
    if not raw:
        base = Path(bundle_dir) if bundle_dir is not None else Path(__file__).resolve().parents[2]
        marker = base / "EDITION"
        if marker.exists():
            raw = marker.read_text(encoding="utf-8").strip().lower()
    if not raw:
        if fail_closed:
            raise ValueError("StructuralPro edition marker is missing")
        return None
    try:
        return ProductEdition(raw)
    except ValueError as exc:
        if fail_closed:
            raise ValueError(f"Invalid StructuralPro edition marker: {raw!r}") from exc
        return None


def validate_packaged_edition_features(
    bundle_dir: str | Path,
    licensed_features: tuple[str, ...] | list[str] | set[str],
) -> bool:
    edition = packaged_edition(bundle_dir, fail_closed=True)
    return validate_license_features(edition, licensed_features)
