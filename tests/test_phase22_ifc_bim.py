import io
from dataclasses import replace
import pytest

ifc = pytest.importorskip("ifcopenshell")

from core.bim.phase22 import IFCError, extract_ifc, fingerprint, validate_model, element_to_takeoff


def sample_ifc():
    model = ifc.file(schema="IFC4")
    project = model.create_entity("IfcProject", GlobalId="3fJ8$abc1234567890123", Name="Demo")
    unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE")
    model.create_entity("IfcUnitAssignment", Units=[unit])
    project.UnitsInContext = next(iter(model.by_type("IfcUnitAssignment")), None)
    wall = model.create_entity("IfcWall", GlobalId="3fJ8$wall123456789012", Name="Wall-01")
    prop = model.create_entity("IfcPropertySingleValue", Name="Material", NominalValue=model.create_entity("IfcLabel", "Concrete"))
    pset = model.create_entity("IfcPropertySet", GlobalId="3fJ8$pset123456789012", Name="Pset_WallCommon", HasProperties=[prop])
    rel = model.create_entity("IfcRelDefinesByProperties", GlobalId="3fJ8$rel123456789012", RelatedObjects=[wall], RelatingPropertyDefinition=pset)
    q = model.create_entity("IfcQuantityVolume", Name="NetVolume", VolumeValue=12.5)
    qset = model.create_entity("IfcElementQuantity", GlobalId="3fJ8$qset123456789012", Name="BaseQuantities", Quantities=[q])
    model.create_entity("IfcRelDefinesByProperties", GlobalId="3fJ8$qrel123456789012", RelatedObjects=[wall], RelatingPropertyDefinition=qset)
    stream = io.BytesIO()
    stream.write(model.to_string().encode("utf-8"))
    return stream.getvalue()


def test_ifc_extracts_elements_properties_quantities():
    result = extract_ifc(sample_ifc())
    assert result.schema == "IFC4"
    assert result.element_count == 1
    assert result.elements[0].ifc_type == "IfcWall"
    assert dict(result.elements[0].quantities)["NetVolume"] == 12.5
    assert dict(result.elements[0].quantity_kinds)["NetVolume"] == "VOLUME"
    assert result.units == "LENGTHUNIT:MILLIMETRE"


def test_quantity_bridge_and_fingerprint():
    raw = sample_ifc()
    result = extract_ifc(raw)
    validate_model(result)
    takeoff = element_to_takeoff(result)
    assert takeoff[0]["element_id"]
    assert takeoff[0]["quantities"]["NetVolume"] == 12.5
    assert takeoff[0]["quantity_kinds"]["NetVolume"] == "VOLUME"
    assert takeoff[0]["unit_basis"] == "LENGTHUNIT:MILLIMETRE"
    assert result.export_payload()["source_fingerprint"] == fingerprint(raw)


@pytest.mark.parametrize("payload", [b"not-ifc", b"ISO-10303-21;", b"\xff\xfe"])
def test_invalid_ifc_fails_closed(payload):
    with pytest.raises(IFCError, match="decoding"):
        extract_ifc(payload)


def test_missing_identity_is_not_silently_dropped():
    model = ifc.file.from_string(sample_ifc().decode())
    model.by_type("IfcWall")[0].GlobalId = None
    with pytest.raises(IFCError, match="GlobalId"):
        extract_ifc(model.to_string().encode())


def test_negative_quantity_is_rejected_during_extraction():
    model = ifc.file.from_string(sample_ifc().decode())
    model.by_type("IfcQuantityVolume")[0].VolumeValue = -12.5
    with pytest.raises(IFCError, match="quantity"):
        extract_ifc(model.to_string().encode())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -1])
def test_quantity_bridge_rejects_nonfinite_or_negative_values(value):
    model = extract_ifc(sample_ifc())
    element = replace(model.elements[0], quantities=(("NetVolume", value),))
    with pytest.raises(IFCError, match="quantity"):
        element_to_takeoff(replace(model, elements=(element,)))


def test_quantity_bridge_rejects_duplicate_quantity_names():
    model = extract_ifc(sample_ifc())
    element = replace(model.elements[0], quantities=(("NetVolume", 1.0), ("NetVolume", 2.0)))
    with pytest.raises(IFCError, match="Duplicate IFC quantity"):
        element_to_takeoff(replace(model, elements=(element,)))


def test_quantity_totals_reject_same_name_with_conflicting_kinds():
    model = extract_ifc(sample_ifc())
    volume = model.elements[0]
    length = replace(
        volume,
        global_id="3fJ8$beam123456789012",
        quantities=(("NetVolume", 12.5),),
        quantity_kinds=(("NetVolume", "LENGTH"),),
    )
    ambiguous = replace(model, elements=(volume, length))

    with pytest.raises(IFCError, match="Conflicting IFC quantity kinds"):
        ambiguous.quantity_totals()


def test_export_payload_validates_quantities_before_aggregation():
    model = extract_ifc(sample_ifc())
    invalid = replace(model.elements[0], quantities=(("NetVolume", float("nan")),))

    with pytest.raises(IFCError, match="finite and non-negative"):
        replace(model, elements=(invalid,)).export_payload()


def test_ambiguous_duplicate_unit_types_fail_closed():
    model = ifc.file.from_string(sample_ifc().decode())
    project = model.by_type("IfcProject")[0]
    second = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    project.UnitsInContext.Units = tuple(project.UnitsInContext.Units) + (second,)
    with pytest.raises(IFCError, match="Duplicate IFC unit type"):
        extract_ifc(model.to_string().encode())

