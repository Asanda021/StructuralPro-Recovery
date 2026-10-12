from core.project.domains import DISCIPLINES, normalize_discipline
from core.project.product_map import MASTER_PRODUCT_MAP, find_product_node, flatten_product_map


def test_master_product_map_preserves_existing_core_disciplines():
    for discipline in (
        "architecture", "structural", "concrete", "steel", "masonry",
        "mechanical", "electrical", "civil", "other",
    ):
        assert discipline in DISCIPLINES
        assert normalize_discipline(discipline) == discipline


def test_master_product_map_has_required_structural_branches():
    structural = find_product_node("structural")
    assert structural is not None
    keys = {child.key for child in structural.children}
    assert {
        "concrete", "steel", "masonry", "timber", "composite",
        "precast", "special_structures", "foundations",
    } <= keys


def test_master_product_map_contains_shared_whole_building_services():
    required = {
        "architecture", "analysis_design", "geotechnical", "mechanical",
        "electrical", "civil", "cad", "bim", "takeoff", "boq",
        "estimating", "cost_database", "contracts", "tender",
        "progress_payment", "procurement", "schedule", "cost_control",
        "revision", "audit", "standards", "reports", "document_management",
    }
    root_keys = {child.key for child in MASTER_PRODUCT_MAP.children}
    assert required <= root_keys


def test_master_product_map_is_non_empty_and_keys_are_unique():
    nodes = flatten_product_map()
    assert len(nodes) > 100
    keys = [node.key for node in nodes]
    assert len(keys) == len(set(keys))


def test_existing_revision_and_audit_nodes_are_explicitly_mapped():
    assert find_product_node("revision") is not None
    assert find_product_node("audit") is not None
    assert find_product_node("traceability") is None
    assert find_product_node("steel_connections") is not None
