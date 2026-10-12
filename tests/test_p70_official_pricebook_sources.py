from core.estimate.official_pricebook_sources_v1 import *

def test_registry():
    assert validate_sources() and len(registry_fingerprint())==64

def test_recent_year_coverage():
    assert coverage()["years"] == [1399,1400,1401,1402,1403,1404]

def test_direct_official_pages():
    assert any(x.year==1401 and "mdid=5681" in x.official_url for x in SOURCES)
    assert any(x.year==1403 and "mdid=5852" in x.official_url for x in SOURCES)
    assert any(x.year==1404 and "mdid=5957" in x.official_url for x in SOURCES)


def test_archive_index_row_parser_keeps_year_discipline_context():
    from scripts.sync_pricebooks_24 import ArchiveRowParser

    parser = ArchiveRowParser()
    parser.feed(
        '<table><tr><td>دانلود اکسل فهرست بهای تاسیسات مکانیکی سال 1399</td>'
        '<td><a href="/fehrest_baha_years/mechanic_1399.html">صفحه دانلود</a></td></tr></table>'
    )
    assert len(parser.rows) == 1
    label, links = parser.rows[0]
    assert "1399" in label
    assert "تاسیسات مکانیکی" in label
    assert links == [("صفحه دانلود", "/fehrest_baha_years/mechanic_1399.html")]
