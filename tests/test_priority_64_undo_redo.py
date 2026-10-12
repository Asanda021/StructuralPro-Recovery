from core.platform.history import History

def test_undo_redo_round_trip():
    h=History({"qty":1})
    h.apply({"qty":2})
    h.apply({"qty":3})
    assert h.undo()["qty"]==2
    assert h.undo()["qty"]==1
    assert h.redo()["qty"]==2
    assert h.redo()["qty"]==3

def test_new_change_invalidates_redo():
    h=History({"v":0})
    h.apply({"v":1})
    h.undo()
    assert h.can_redo
    h.apply({"v":2})
    assert not h.can_redo

def test_history_is_copy_safe_and_bounded():
    source={"items":[1]}
    h=History(source,limit=2)
    h.apply({"items":[2]})
    source["items"].append(9)
    assert h.current()["items"]==[2]
    h.apply({"items":[3]})
    assert h.can_undo
    assert h.undo()["items"]==[2]
    assert not h.can_undo

def test_empty_operations_fail_closed():
    h=History({})
    for op in (h.undo,h.redo):
        try: op()
        except IndexError: pass
        else: raise AssertionError("empty operation must fail")
