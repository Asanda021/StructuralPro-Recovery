"""E4 original global_search extended: no fabricated ids and normalized Persian."""
from core.search.global_search import search_project, normalize
from core.search.command_center import command_search
import pytest


def fixture():
    return {
        "id":"P","name":"پروژه شمال",
        "floors":[{"id":"F2","name":"طبقه دوم"}],
        "members":[{"id":"M12","floor_id":"F2","kind":"column"}],
        "drawings":[{"id":"D1","name":"پلان طبقه دوم","revision":"R2","source_id":"SRC"}],
        "takeoffs":[{"id":"T1","title":"دیوار آجري",
                     "quantities":[{"id":"I1","title":"سنگ کاری","price_code":"0123"}]}],
        "boq":[{"row_id":"B1","description":"ملات ديوار","price_code":"0099",
                "source_ids":["source:1"],"revision":3}],
        "wbs":[{"id":"W1","title":"اجرای بتن"}],
        "reports":[{"id":"R1","title":"گزارش معماری"}],
    }


def test_normalize_digits_persian_and_zwnj():
    assert normalize("آجر ي")=="آجر ی"
    assert normalize("۰۱۲۳")==normalize("0123")
    assert normalize("کاشی‌کاری")==normalize("کاشيكاري")
    assert normalize("  طبقه   دوم  ")=="طبقه دوم"


@pytest.mark.parametrize("query,kind,entity_id",[
    ("۰۱۲۳","price_code","I1"),("ديوار","takeoff","T1"),
    ("M12","member","M12"),("F2","floor","F2"),
    ("پلان","drawing","D1"),("بتن","wbs","W1"),
    ("معماری","report","R1"),("ملات","boq","B1"),
])
def test_search_reuses_authorized_project_records(query,kind,entity_id):
    p=fixture()
    hits=search_project(p,query)
    assert any(h["kind"]==kind and h["entity_id"]==entity_id and h["project_id"]=="P" for h in hits)


def test_cross_project_absent_and_read_only():
    p=fixture()
    before=repr(p)
    assert not search_project(p,"اطلاعات پروژه محرمانه دیگر")
    assert repr(p)==before
    hit=search_project(p,"0099")[0]
    assert hit["source_id"]==["source:1"] and hit["revision"]==3
    assert hit["route"]=="boq" or hit["route"]=="prices"


def test_search_large_member_collection_bounded():
    p={"id":"P","name":"Large","members":[
        {"id":f"M{i}","kind":"wall","floor_id":"F1"} for i in range(10000)
    ]}
    items=search_project(p,"wall",limit=70)
    assert len(items)==70
    assert all(item["project_id"]=="P" for item in items)
    with pytest.raises(ValueError):search_project(p,"wall",limit=0)


def test_existing_command_center_uses_same_search():
    hits=command_search(fixture(),"ملات")
    assert hits and hits[0]["project_id"]=="P"


def test_equal_price_codes_are_not_unique_boq_identity():
    p={"id":"P","name":"آزمون",
       "boq":[{"description":"اجرای کف","price_code":"0101"},
              {"description":"اجرای کف","price_code":"0101"}]}
    hits=search_project(p,"اجرای کف")
    assert len(hits)==2
    assert all(x["entity_id"] is None and x["link_status"]=="unindexed_record" for x in hits)
    assert hits[0]["data"] is not hits[1]["data"]
