from core.takeoff.automated_building_takeoff_v1 import TakeoffRecord, UniversalBuildingTakeoff
import pytest

def r(i,d,c,q,u="m2",src=("S1",),rev="A"):
    return TakeoffRecord(i,d,c,src,q,u,"explicit_quantity",rev)

def test_aggregates_all_building_disciplines():
    rows=[r("1","structural","concrete",10,"m3"),r("2","architectural","wall",20),r("3","mechanical","pipe",30,"m"),r("4","electrical","cable",40,"m"),r("5","site","paving",50)]
    out=UniversalBuildingTakeoff().aggregate(rows)
    assert {x["discipline"] for x in out}=={"structural","architectural","mechanical","electrical","site"}

def test_units_are_not_mixed():
    out=UniversalBuildingTakeoff().aggregate([r("1","architectural","wall",10,"m2"),r("2","architectural","wall",2,"m")])
    assert len(out)==2

def test_missing_source_fails_closed():
    with pytest.raises(ValueError): r("1","structural","beam",1,src=()).validate()

def test_nonaccepted_record_is_blocked():
    with pytest.raises(ValueError): TakeoffRecord("1","structural","beam",("S",),1,"m3","f","A","review").validate()

def test_fingerprint_order_independent():
    w=UniversalBuildingTakeoff(); a=r("a","structural","x",1); b=r("b","architectural","y",2)
    assert w.fingerprint((a,b))==w.fingerprint((b,a))

def test_revision_delta_is_explicit():
    w=UniversalBuildingTakeoff(); a=r("a","structural","x",1); b=r("a","structural","x",2)
    assert w.revision_delta((a,),(b,))==(("a","changed"),)
