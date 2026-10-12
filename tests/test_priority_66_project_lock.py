from datetime import datetime,timezone,timedelta
from core.platform.locks import ProjectLock,acquire_lock,is_lock_active,release_lock

def test_owner_can_refresh_and_release():
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    lock=acquire_lock("P1","A",now=now,ttl_seconds=60)
    assert is_lock_active(lock,now=now)
    refreshed=acquire_lock("P1","A",now=now+timedelta(seconds=10),existing=lock)
    assert refreshed.owner_id=="A"
    release_lock(refreshed,owner_id="A")

def test_other_owner_is_blocked_until_expiry():
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    lock=acquire_lock("P1","A",now=now,ttl_seconds=60)
    try: acquire_lock("P1","B",now=now+timedelta(seconds=10),existing=lock)
    except RuntimeError: pass
    else: raise AssertionError("active lock must block another owner")
    acquired=acquire_lock("P1","B",now=now+timedelta(seconds=61),existing=lock)
    assert acquired.owner_id=="B"

def test_wrong_owner_cannot_release():
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    lock=acquire_lock("P1","A",now=now)
    try: release_lock(lock,owner_id="B")
    except PermissionError: pass
    else: raise AssertionError("wrong owner must not release")

def test_naive_clock_is_rejected():
    try: acquire_lock("P1","A",now=datetime(2026,1,1))
    except ValueError: pass
    else: raise AssertionError("naive datetime must fail")
