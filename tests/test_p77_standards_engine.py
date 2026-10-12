from core.standards import StandardsEngine, default_iran_registry
from core.standards.catalog import IRAN_CORE_SOURCES

def test_engine_resolves_rule_to_source_and_clause():
    engine=StandardsEngine(default_iran_registry())
    d=engine.require(domain="concrete",rule_code="N09-CONCRETE-SOURCE")
    assert d.source_code == "IR-NBR-09" and d.edition == "1399"
    assert d.clause == "دامنه کاربرد" and d.domain == "concrete"
    assert engine.provenance(d)["source_code"] == "IR-NBR-09"

def test_engine_rejects_missing_rule():
    engine=StandardsEngine(default_iran_registry())
    try: engine.require(domain="concrete",rule_code="NO-SUCH-RULE")
    except LookupError: pass
    else: raise AssertionError("missing rule must fail explicitly")

def test_catalog_covers_all_iran_national_building_regulation_numbers():
    codes={s.code for s in IRAN_CORE_SOURCES}
    assert {f"IR-NBR-{i:02d}" for i in range(1,24)} <= codes

def test_registry_sources_have_no_duplicate_codes():
    reg=default_iran_registry()
    codes=[s.code for s in reg.sources()]
    assert len(codes)==len(set(codes))
