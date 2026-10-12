from core.platform.concurrency import begin_write,assert_unchanged,guarded_update

def test_unchanged_project_can_be_written():
    current={"qty":10}
    token=begin_write(current)
    assert_unchanged(current,token)
    assert guarded_update(current,token,{"qty":11})["qty"]==11

def test_stale_writer_is_rejected():
    token=begin_write({"qty":10})
    try: assert_unchanged({"qty":11},token)
    except RuntimeError: pass
    else: raise AssertionError("stale writer must fail")

def test_update_does_not_mutate_current():
    current={"qty":10}
    token=begin_write(current)
    out=guarded_update(current,token,{"qty":12})
    assert current["qty"]==10 and out["qty"]==12
