from core.platform.product import ProductEdition, packaged_edition, product_profile, validate_packaged_edition_features

def test_packaged_edition_marker_is_read(tmp_path):
    (tmp_path / "EDITION").write_text("pro\n", encoding="utf-8")
    assert packaged_edition(tmp_path, fail_closed=True) is ProductEdition.PRO

def test_invalid_or_missing_packaged_edition_fails_closed(tmp_path):
    for marker in [None, "not-an-edition\n"]:
        path = tmp_path / "EDITION"
        if marker is None:
            if path.exists(): path.unlink()
        else:
            path.write_text(marker, encoding="utf-8")
        try:
            packaged_edition(tmp_path, fail_closed=True)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid or missing edition marker must fail closed")

def test_packaged_edition_respects_feature_boundary(tmp_path):
    (tmp_path / "EDITION").write_text("standard\n", encoding="utf-8")
    assert validate_packaged_edition_features(tmp_path, ["takeoff.cad", "estimate.cost"])
    assert not validate_packaged_edition_features(tmp_path, ["takeoff.ai"])

def test_profiles_remain_monotonic():
    editions = list(ProductEdition)
    for left, right in zip(editions, editions[1:]):
        assert product_profile(left).features <= product_profile(right).features
