from core.engineering import EngineeringLibrary, EngineeringMaterial, RebarGrade

def test_default_engineering_library_is_valid():
    result = EngineeringLibrary().validate()
    assert result["ok"] is True
    assert result["counts"] == {"materials": 5, "concretes": 5, "rebars": 4, "standards": 4}

def test_concrete_and_rebar_lookup_is_deterministic():
    library = EngineeringLibrary()
    assert library.concrete("c25").characteristic_strength_mpa == 25
    assert library.rebar("a3").yield_strength_mpa == 400

def test_search_is_cross_library_and_category_filterable():
    library = EngineeringLibrary()
    assert any(row["kind"] == "concrete" for row in library.search("C25"))
    assert all(row["kind"] == "rebar" for row in library.search("A3", category="rebar"))

def test_custom_material_is_validated_and_replaceable():
    library = EngineeringLibrary()
    library.add_material(EngineeringMaterial("WATERPROOF", "عایق", "waterproofing", "m2"))
    assert library.material("waterproof").default_unit == "m2"

def test_invalid_rebar_strength_is_rejected():
    library = EngineeringLibrary()
    try:
        library.add_rebar(RebarGrade("BAD", "نامعتبر", 500, 400))
    except ValueError as exc:
        assert "tensile strength" in str(exc)
    else:
        raise AssertionError("invalid relation was accepted")

def test_snapshot_contains_provenance():
    snapshot = EngineeringLibrary().snapshot()
    assert snapshot["materials"][0]["source_id"] == "builtin-reference"
    assert snapshot["concretes"][0]["source_version"] == "1"
