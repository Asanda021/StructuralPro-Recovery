"""Smoke test of synthetic specialist adapter dispatch, not engineering signoff."""
from decimal import Decimal
from pathlib import Path
import pytest

EXACT = "12345678901234567890.123456789012345678901"

class SyntheticService:
    def __init__(self, ready=True):
        self.ready = ready
    def _preview(self):
        return {"ready": self.ready, "committed": True, "rows": [
            {"description": "مقدار مصنوعی", "quantity": Decimal(EXACT),
             "unit": "m3", "formula": "length*width*depth",
             "source_id": "SRC-0001", "params": {"source_ref": "REF-0001"}}]}
    def _record(self):
        return {"revision": 2, "data": {"source": {
            "source_id": "SRC-0001", "plan_ref": "PLAN-0001",
            "detail_ref": "DETAIL-0001"}}}
    def preview_beam_detail(self, *args):
        return self._preview()
    def preview_structural_member(self, *args):
        return self._preview()
    def get_beam_detail(self, *args):
        return self._record()
    def get_structural_member(self, *args):
        return self._record()
    def open_project(self, *args):
        return {"beam_amendments": {}}

@pytest.mark.parametrize("kind", ["beam", "column", "tie_beam",
                                  "isolated_footing", "strip_footing",
                                  "mat_footing", "pile_cap"])
@pytest.mark.parametrize("fmt", ["csv", "docx"])
def test_adapter_routes_preserve_exact_quantity_and_source(monkeypatch, tmp_path, kind, fmt):
    from core.reports import beam_detail_report, column_detail_report
    module = beam_detail_report if kind == "beam" else column_detail_report
    out = tmp_path / ("report." + fmt)
    captured = []
    def spy(rows, path, **kwargs):
        captured.append((rows, path, kwargs))
        return Path(path)
    monkeypatch.setattr(module, "export_" + fmt, spy)
    service = SyntheticService()
    if kind == "beam":
        result = module.export(service, "P1", "L1", "B1", out, format=fmt)
    else:
        result = module.export(service, "P1", "L1", "C1", out, format=fmt, kind=kind)
    assert result == out
    assert len(captured) == 1
    rows, path, kwargs = captured[0]
    combined = " ".join(str(v) for row in rows for v in row.values())
    assert EXACT in combined
    assert "SRC-0001" in combined
    assert kwargs["title"] and kwargs["columns"]

@pytest.mark.parametrize("kind", ["beam", "column", "tie_beam"])
def test_unreviewed_report_fails_closed(monkeypatch, tmp_path, kind):
    from core.reports import beam_detail_report, column_detail_report
    module = beam_detail_report if kind == "beam" else column_detail_report
    def forbidden(*args, **kwargs):
        raise AssertionError("Unreviewed exporter was called")
    monkeypatch.setattr(module, "export_csv", forbidden)
    service = SyntheticService(ready=False)
    with pytest.raises(ValueError):
        if kind == "beam":
            module.export(service, "P1", "L1", "B1", tmp_path / "bad.csv", format="csv")
        else:
            module.export(service, "P1", "L1", "C1", tmp_path / "bad.csv", format="csv", kind=kind)
