"""P8/P2: Actual public source DWGs must open for preview even if payable decoder fails.

No private customer drawing leaves local analysis. This test uses the two
immutable public upstream sample DWGs already pinned by other CI scenarios.
"""
from hashlib import sha256
from pathlib import Path
from functools import lru_cache
from time import sleep
from urllib.error import HTTPError

import pytest

from core.drawings.dwg_takeoff import DWGTakeoffEngine, cad_entity_geometry
from core.drawings.native_dwg_preview import native_readonly_dwg_preview
from core.drawings.viewer_model import DrawingViewerModel
from core.cad.optional_strict_python_dwg_provider import StrictPythonDWGError
from scripts.phase8_p2_ac1018_paired_geometry_probe import _download as paired_public_download
from scripts.phase8_p2_real_dwg_source_probe import (
    RestrictedRedirect, approved_url, STUDIO_SOURCE, SOURCES,
)
from urllib.request import Request, build_opener


def public_ac1018(tmp_path):
    b = paired_public_download("line_2004.dwg")
    p = tmp_path / "public-source-ac1018.dwg"
    p.write_bytes(b)
    assert b[:6] == b"AC1018"
    return p


@lru_cache(maxsize=1)
def _verified_public_studio_bytes():
    """One immutable public sample per test process. Never accept changed bytes.

    Some public hosts intermittently return HTTP 502/503/504. Retry these
    transport errors only, with a fixed, bounded budget; do not retry bad
    host redirects or an incorrect SHA and never substitute synthetic CAD.
    """
    for attempt in range(3):
        try:
            with build_opener(RestrictedRedirect()).open(
                Request(STUDIO_SOURCE, headers={"User-Agent": "P8P2-native-preview-CI/1.0"}),
                timeout=35,
            ) as response:
                if not approved_url(response.geturl()):
                    raise ValueError("Unapproved public DWG redirect")
                b = response.read(500_000)
        except HTTPError as exc:
            if exc.code not in (502, 503, 504) or attempt == 2:
                raise
            sleep(2 * (attempt + 1))
            continue
        if sha256(b).hexdigest() != SOURCES["studio_cc0"]["expected_sha256"]:
            raise ValueError("Pinned public DWG SHA changed")
        return b
    raise RuntimeError("Pinned public DWG was not acquired")


def public_unitless_ac1015(tmp_path):
    b = _verified_public_studio_bytes()
    p = tmp_path / "public-cc0-unitless.dwg"
    p.write_bytes(b)
    return p


def _assert_non_payable_preview(doc, expected_sha):
    assert doc.format == "DWG_NATIVE_READONLY_PREVIEW"
    assert doc.source_sha256 == expected_sha
    assert doc.conversion["preview_only"] is True
    assert doc.conversion["geometry_approved"] is False
    assert doc.conversion["cad_derived_legacy_metre_rows_approved"] == 0
    assert len(doc.entities) > 0
    assert all(e.data["preview_only"] and e.data["unsupported_measurement"] for e in doc.entities)
    with pytest.raises(ValueError, match="فقط"):
        cad_entity_geometry(doc, doc.entities[0].handle, "length")
    with pytest.raises(ValueError, match="فقط"):
        DWGTakeoffEngine().layer_takeoff(doc, {doc.entities[0].layer: {"metric":"count"}})


def test_real_paired_ac1018_has_preview_without_payable_conversion(tmp_path):
    path = public_ac1018(tmp_path)
    preview = native_readonly_dwg_preview(path)
    _assert_non_payable_preview(preview, sha256(path.read_bytes()).hexdigest())
    assert preview.units == "mm"
    assert preview.dxf_version == "AC1018"
    assert "LINE" in {e.entity_type for e in preview.entities}


def test_actual_public_unitless_dwg_is_viewable_without_guessing_units(tmp_path):
    path = public_unitless_ac1015(tmp_path)
    preview = native_readonly_dwg_preview(path)
    _assert_non_payable_preview(preview, sha256(path.read_bytes()).hexdigest())
    assert preview.units == "unitless"
    assert any("unit" in text.lower() for text in preview.warnings)


def test_windows_viewer_falls_back_to_readonly_native_on_authorized_strict_failure(tmp_path,monkeypatch):
    path = public_unitless_ac1015(tmp_path)
    def fail_payable_import(self,path):
        raise StrictPythonDWGError("Original DWG unitless, do not infer metres")
    monkeypatch.setattr(DWGTakeoffEngine,"import_file",fail_payable_import)
    viewer = DrawingViewerModel().open(path)
    assert viewer.kind == "cad"
    assert viewer.page_count == 1
    assert viewer.cad_document.format == "DWG_NATIVE_READONLY_PREVIEW"
    summary = viewer.summary
    assert summary["entities"] > 0
    assert summary["conversion"]["preview_only"]


def test_corrupt_dwg_fails_closed_even_in_preview(tmp_path):
    src = tmp_path/"broken.dwg"
    src.write_bytes(b"AC1018"+b"broken-sample-dwg-not-a-real-cad-file")
    with pytest.raises((RuntimeError,ValueError,Exception)):
        native_readonly_dwg_preview(src)
