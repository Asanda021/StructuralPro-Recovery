from core.platform.product import (
    FEATURES,
    ProductEdition,
    feature_matrix,
    product_profile,
    validate_license_features,
)


def test_all_editions_exist_and_are_monotonic():
    profiles = [product_profile(e) for e in ProductEdition]
    # Four historical profiles remain readable for data migration; only
    # UNIFIED is now the canonical new Windows product, with full capabilities.
    assert len(profiles) == 5
    for left, right in zip(profiles, profiles[1:]):
        assert left.features <= right.features
    assert product_profile(ProductEdition.UNIFIED).features == set(FEATURES)
    assert product_profile(ProductEdition.ENTERPRISE).features == set(FEATURES)


def test_domain_agnostic_takeoff_capabilities_are_packaged():
    for edition in ProductEdition:
        profile = product_profile(edition)
        assert profile.supports("takeoff.boq")
        assert profile.supports("takeoff.drawing")
    assert product_profile(ProductEdition.PRO).supports("takeoff.ai")
    assert product_profile(ProductEdition.ENTERPRISE).supports("enterprise.controls")


def test_invalid_feature_is_rejected():
    try:
        product_profile("unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown edition must fail closed")


def test_license_features_cannot_escape_edition_boundary():
    assert validate_license_features(ProductEdition.PRO, ["takeoff.ai", "estimate.cost"])
    assert not validate_license_features(ProductEdition.STANDARD, ["takeoff.ai"])
    assert not validate_license_features(ProductEdition.LIGHT, ["takeoff.cad"])


def test_feature_matrix_is_stable_and_complete():
    matrix = feature_matrix()
    assert set(matrix) == {e.value for e in ProductEdition}
    assert all(set(features) <= set(FEATURES) for features in matrix.values())
