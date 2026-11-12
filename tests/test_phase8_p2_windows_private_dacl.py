"""Native Windows NTFS DACL tests; all source data and receipts synthetic."""
import os
from pathlib import Path
import subprocess
import pytest
from core.platform.windows_private_acl import current_user_sid, verify_private_dacl

def _icacls(path,*args):
    r=subprocess.run(["icacls",str(path),*args],capture_output=True,text=True,timeout=25)
    assert r.returncode==0, "Unable to configure disposable Windows ACL"

def _restrict(path,*,directory):
    sid=current_user_sid()
    # Elevated Windows runners can create new files owned by the local
    # Administrators group. Require an explicit owner change, do not relax
    # the production owner's identity invariant to accommodate the runner.
    _icacls(path,"/setowner",f"*{sid}")
    _icacls(path,"/inheritance:r")
    rights="(OI)(CI)F" if directory else "F"
    _icacls(path,"/grant:r",f"*{sid}:{rights}",f"*S-1-5-18:{rights}")
    assert verify_private_dacl(path,directory=directory)

def test_non_windows_must_fail_closed():
    if os.name=="nt":
        assert current_user_sid().startswith("S-1-")
    else:
        with pytest.raises(ValueError,match="WINDOWS_PRIVATE_DACL_NOT_VERIFIED"):
            verify_private_dacl(Path(__file__),directory=False)

@pytest.mark.skipif(os.name!="nt",reason="Requires native Windows NTFS DACL")
def test_protected_private_folder_and_config(tmp_path):
    folder=tmp_path/"private"
    folder.mkdir()
    _restrict(folder,directory=True)
    config=folder/"config.json"
    config.write_text('{"synthetic":true}',encoding="utf-8")
    with pytest.raises(ValueError,match="WINDOWS_PRIVATE_DACL_NOT_VERIFIED"):
        verify_private_dacl(config,directory=False)  # inherited ACL is insufficient
    _restrict(config,directory=False)
    assert verify_private_dacl(config,directory=False)

@pytest.mark.skipif(os.name!="nt",reason="Requires native Windows NTFS DACL")
def test_inherited_default_folder_is_denied(tmp_path):
    folder=tmp_path/"default_acl"
    folder.mkdir()
    with pytest.raises(ValueError,match="WINDOWS_PRIVATE_DACL_NOT_VERIFIED"):
        verify_private_dacl(folder,directory=True)
    _restrict(folder,directory=True)

@pytest.mark.skipif(os.name!="nt",reason="Requires native Windows NTFS DACL")
def test_everyone_grant_is_denied(tmp_path):
    folder=tmp_path/"private"
    folder.mkdir()
    _restrict(folder,directory=True)
    _icacls(folder,"/grant","*S-1-1-0:(OI)(CI)R")
    with pytest.raises(ValueError,match="WINDOWS_PRIVATE_DACL_NOT_VERIFIED"):
        verify_private_dacl(folder,directory=True)
    _icacls(folder,"/remove:g","*S-1-1-0")
    assert verify_private_dacl(folder,directory=True)

@pytest.mark.skipif(os.name!="nt",reason="Requires native Windows NTFS DACL")
def test_chmod_0600_is_not_windows_privacy(tmp_path):
    config=tmp_path/"config.json"
    config.write_text('{"synthetic":true}',encoding="utf-8")
    config.chmod(0o600)
    with pytest.raises(ValueError,match="WINDOWS_PRIVATE_DACL_NOT_VERIFIED"):
        verify_private_dacl(config,directory=False)
    _restrict(config,directory=False)

@pytest.mark.skipif(os.name!="nt",reason="Requires native Windows NTFS DACL")
def test_missing_file_and_wrong_type_denied(tmp_path):
    folder=tmp_path/"private"
    folder.mkdir()
    _restrict(folder,directory=True)
    for candidate,is_dir in [(folder,False),(folder/"missing.json",False)]:
        with pytest.raises(ValueError,match="WINDOWS_PRIVATE_DACL_NOT_VERIFIED"):
            verify_private_dacl(candidate,directory=is_dir)
