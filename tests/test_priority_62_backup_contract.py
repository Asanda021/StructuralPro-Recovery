from core.platform.backup import create_backup, restore_backup, validate_backup

def test_backup_is_deterministic_and_restores_copy():
    payload={"name":"P1","items":[{"qty":10}]}
    backup=create_backup("P1",2,payload)
    assert validate_backup(backup)==[]
    restored=restore_backup(backup,expected_project_id="P1")
    restored["items"][0]["qty"]=99
    assert payload["items"][0]["qty"]==10

def test_tamper_is_rejected():
    backup=create_backup("P1",1,{"qty":10})
    backup["payload"]["qty"]=11
    assert "backup integrity mismatch" in validate_backup(backup)
    try: restore_backup(backup)
    except ValueError as exc: assert "backup integrity mismatch" in str(exc)
    else: raise AssertionError("tampered backup must fail")

def test_project_mismatch_is_rejected():
    backup=create_backup("P1",1,{})
    try: restore_backup(backup,expected_project_id="P2")
    except ValueError as exc: assert "project_id mismatch" in str(exc)
    else: raise AssertionError("mismatched project must fail")

def test_invalid_schema_fails_closed():
    backup=create_backup("P1",1,{})
    backup["schema_version"]="v2"
    assert validate_backup(backup)
