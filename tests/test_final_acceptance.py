from core.projects.store import ProjectStore
from core.sync.conflicts import merge_dict, resolve_conflicts
from core.platform.clients import ProductClient
from core.pricing.catalog import PriceCatalog, PriceItem
from core.pricing.datasets import export_dataset, load_dataset

def test_offline_project_store_and_revisions(tmp_path):
    s = ProjectStore(tmp_path / "p.db")
    first = s.save("p1", {"name": "A", "takeoffs": [{"q": 2}]})
    second = s.save("p1", {"name": "A2", "takeoffs": [{"q": 3}]})
    assert first["version"] == 1
    assert second["version"] == 2
    assert s.get("p1")["name"] == "A2"
    assert len(s.revisions("p1")) == 2
    s.close()

def test_three_way_sync_conflict_is_lossless():
    merged, conflicts = merge_dict({"a": 1, "b": 2}, {"a": 2, "b": 2}, {"a": 3, "b": 4})
    assert conflicts == ["a"]
    assert merged["a"]["_conflict"]["local"] == 2
    assert resolve_conflicts(merged, {"a": "remote"})["a"] == 3

def test_all_platforms_share_contract():
    for platform in ("windows", "android", "telegram"):
        client = ProductClient(platform)
        assert client.open_project("x")["id"] == "x"
        assert client.state()["project_id"] == "x"

def test_verified_dataset_roundtrip(tmp_path):
    catalog = PriceCatalog([PriceItem(1405, "ابنیه", "بتن", "A-1", "بتن", "m3", 100)])
    path = tmp_path / "dataset.json"
    export_dataset(catalog, path, year=1405, group="ابنیه", source="verified-test")
    loaded, meta = load_dataset(path, expected_year=1405, expected_group="ابنیه")
    assert meta["verified"] is True
    assert loaded.get("A-1", 1405).unit_price == 100
