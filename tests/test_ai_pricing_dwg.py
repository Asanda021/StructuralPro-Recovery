from core.ai.local_engine import LocalAIEngine
from core.ai.takeoff_assistant import LocalTakeoffAssistant
from core.pricing.annual_update import AnnualPriceImporter
from core.pricing.catalog import PriceCatalog, PriceItem
from core.drawings.dwg_takeoff import DWGDocument, DWGEntity, infer_takeoff_from_layers
from core.drawings.dwg_converter import OfflineDWGConverter


def test_local_ai_rule_engine_is_offline_and_flags_missing_project_data():
    ai = LocalAIEngine()
    assert ai.is_local is True
    assert ai.has_llm_model is False
    result = ai.inspect_project({})
    assert "نام پروژه" in result.text
    assert "حداقل یک متره" in result.text
    assert result.source == "local-rule-engine"


def test_local_ai_takeoff_mapping_and_qa():
    ai = LocalTakeoffAssistant()
    catalog = [
        {"code": "A-1", "description": "Concrete wall", "group": "Building", "chapter": "Concrete"},
        {"code": "B-1", "description": "Steel rebar", "group": "Building", "chapter": "Rebar"},
    ]
    mapped = ai.suggest_mapping(
        [{"layer": "WALL", "entity_type": "LINE", "text": "concrete wall"}],
        catalog,
    )
    assert mapped[0]["suggestions"][0]["code"] == "A-1"
    issues = ai.qa([
        {"quantity": -2, "unit": "m3", "price_code": "A-1"},
        {"quantity": 1, "unit": "", "price_code": ""},
    ])
    assert any(x["code"] == "negative_quantity" for x in issues)
    assert any(x["code"] == "missing_unit" for x in issues)
    assert any(x["code"] == "missing_price_code" for x in issues)


def test_annual_price_importer_validates_and_converts():
    rows = [{
        "year": "1405", "group": "ابنیه", "chapter": "بتن",
        "code": "A-1", "description": "بتن آماده", "unit": "m3", "unit_price": "1200000"
    }]
    importer = AnnualPriceImporter()
    assert importer.validate(rows) == []
    converted = importer.convert(rows)
    assert converted[0].code == "A-1"
    assert converted[0].unit_price == 1200000


def test_annual_price_importer_rejects_bad_rows():
    importer = AnnualPriceImporter()
    errors = importer.validate([{
        "year": "1200", "group": "ابنیه", "chapter": "بتن",
        "code": "", "description": "bad", "unit": "m3", "unit_price": "-1"
    }])
    assert len(errors) >= 2


def test_price_catalog_import_replace_year():
    c = PriceCatalog([PriceItem(1405, "ابنیه", "بتن", "OLD", "قدیمی", "m3", 1)])
    csv_text = "year,group,chapter,code,description,unit,unit_price,analysis,notes\n1405,ابنیه,بتن,NEW,جدید,m3,10,,"
    assert c.import_csv(csv_text, replace_year=True) == 1
    assert c.get("OLD", 1405) is None
    assert c.get("NEW", 1405).unit_price == 10


def test_dwg_layer_takeoff_and_document_summary():
    doc = DWGDocument(
        [
            DWGEntity("LINE", "WALL", "1", {"length": 4}),
            DWGEntity("LINE", "WALL", "2", {"length": 6}),
            DWGEntity("INSERT", "DOOR", "3", {"block": "D1"}),
        ],
        ["WALL", "DOOR"],
        block_counts={"D1": 1},
        text_labels=["Door"],
        units="m",
    )
    rows = infer_takeoff_from_layers(doc, {
        "WALL": {"description": "wall", "unit": "m", "metric": "length", "price_code": "W1"},
        "DOOR": {"description": "door", "unit": "count", "price_code": "D1"},
    })
    assert rows[0]["quantity"] == 10
    assert rows[1]["quantity"] == 1
    assert len(doc.layers) == 2


def test_dwg_converter_missing_source_and_no_converter_are_explicit():
    converter = OfflineDWGConverter(executable=None)
    missing = __import__("pathlib").Path("/tmp/structuralpro_missing_file.dwg")
    try:
        converter.convert(missing)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing DWG must raise FileNotFoundError")
