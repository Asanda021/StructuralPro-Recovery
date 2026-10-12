from core.estimate.official_pricebook_sources_v1 import all_building_sources, BUILDING_1404_DISCIPLINES

def test_all_building_sources_cover_1404():
    years={s.discipline for s in all_building_sources() if s.year==1404}
    assert set(BUILDING_1404_DISCIPLINES).issubset(years)
