from core.platform.release_ux import UpdateInfo,activation_status,update_message

def test_update_comparison_is_semver_numeric():
    assert UpdateInfo("0.9.0","0.10.0").update_available
    assert not UpdateInfo("0.10.0","0.9.9").update_available

def test_activation_status_is_fail_closed():
    assert activation_status(licensed=False)=="مجوز فعال نشده است"
    assert activation_status(licensed=True,expired=True)=="مجوز منقضی شده است"
    assert activation_status(licensed=True,revoked=True)=="مجوز مسدود شده است"

def test_update_message_is_deterministic():
    assert "نسخه جدید 0.2.0" in update_message(UpdateInfo("0.1.0","0.2.0"))
