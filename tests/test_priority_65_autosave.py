from core.platform.autosave import create_autosave,validate_autosave,recover_autosave

def test_autosave_round_trip_and_copy_safety():
    p={"qty":10,"items":[1]}
    s=create_autosave("P1",3,p)
    assert validate_autosave(s)==[]
    out=recover_autosave(s,expected_project_id="P1")
    out["items"].append(2)
    assert p["items"]==[1]

def test_tampered_autosave_fails():
    s=create_autosave("P1",1,{"x":1})
    s["payload"]["x"]=2
    assert validate_autosave(s)
    try: recover_autosave(s,expected_project_id="P1")
    except ValueError: pass
    else: raise AssertionError("tampered autosave must fail")

def test_wrong_project_fails():
    s=create_autosave("P1",1,{})
    try: recover_autosave(s,expected_project_id="P2")
    except ValueError: pass
    else: raise AssertionError("wrong project must fail")
