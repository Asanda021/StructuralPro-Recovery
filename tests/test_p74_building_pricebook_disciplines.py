from core.estimate.official_pricebook_sources_v1 import building_1404_coverage

def test_building_1404_disciplines_are_explicit():
    c=building_1404_coverage()
    assert c["required"]==["ابنیه","تاسیسات مکانیکی","تاسیسات برقی","مرمت بناهای تاریخی"]
