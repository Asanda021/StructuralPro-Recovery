"""Windows private evidence DACL verifier. Does not infer ACL from chmod.

Only the current process token user, LOCAL SYSTEM and BUILTIN Administrators
may have allow ACEs. Protected non-null DACL and explicit current-user
read/write are required. No shell or sensitive command-line values are used.
This is a native Windows check; other platforms always fail closed.
"""
from __future__ import annotations
import os
from pathlib import Path

def _blocked():
    raise ValueError("WINDOWS_PRIVATE_DACL_NOT_VERIFIED")

def _apis():
    if os.name != "nt":
        _blocked()
    import ctypes
    from ctypes import wintypes as wt
    return ctypes, wt, ctypes.WinDLL("advapi32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)

def _sid_string(adv, kernel, sid, c, wt):
    if not sid:
        _blocked()
    result=wt.LPWSTR()
    f=adv.ConvertSidToStringSidW
    f.argtypes=(wt.LPVOID,c.POINTER(wt.LPWSTR))
    f.restype=wt.BOOL
    if not f(sid,c.byref(result)):
        _blocked()
    try:
        return result.value
    finally:
        kernel.LocalFree.argtypes=(wt.HLOCAL,)
        kernel.LocalFree.restype=wt.HLOCAL
        kernel.LocalFree(c.cast(result,wt.HLOCAL))

def current_user_sid():
    """Read SID from kernel process token, never an environment variable."""
    c,wt,adv,kernel=_apis()
    kernel.GetCurrentProcess.restype=wt.HANDLE
    f=adv.OpenProcessToken
    f.argtypes=(wt.HANDLE,wt.DWORD,c.POINTER(wt.HANDLE))
    f.restype=wt.BOOL
    token=wt.HANDLE()
    if not f(kernel.GetCurrentProcess(),0x0008,c.byref(token)):
        _blocked()
    try:
        get=adv.GetTokenInformation
        get.argtypes=(wt.HANDLE,c.c_int,wt.LPVOID,wt.DWORD,c.POINTER(wt.DWORD))
        get.restype=wt.BOOL
        size=wt.DWORD()
        get(token,1,None,0,c.byref(size))
        if not 1<=size.value<=65536:
            _blocked()
        buf=c.create_string_buffer(size.value)
        if not get(token,1,buf,size.value,c.byref(size)):
            _blocked()
        class TokenUser(c.Structure):
            _fields_=(("Sid",wt.LPVOID),("Attributes",wt.DWORD))
        sid=c.cast(buf,c.POINTER(TokenUser)).contents.Sid
        return _sid_string(adv,kernel,sid,c,wt)
    finally:
        kernel.CloseHandle.argtypes=(wt.HANDLE,)
        kernel.CloseHandle.restype=wt.BOOL
        kernel.CloseHandle(token)

def verify_private_dacl(path: str | Path, *, directory: bool) -> bool:
    """Require owner-owned, non-inherited, private NTFS DACL or veto."""
    c,wt,adv,kernel=_apis()
    p=Path(path)
    if not p.is_absolute() or not p.exists() or p.is_dir()!=directory or p.is_symlink():
        _blocked()
    if (hasattr(p,"is_junction") and p.is_junction()) or (p.stat().st_file_attributes & 0x400):
        _blocked()
    for parent in p.parents:
        if parent.is_symlink() or (hasattr(parent,"is_junction") and parent.is_junction()):
            _blocked()
    owner=wt.LPVOID()
    dacl=wt.LPVOID()
    sd=wt.LPVOID()
    g=adv.GetNamedSecurityInfoW
    g.argtypes=(wt.LPWSTR,wt.DWORD,wt.DWORD,c.POINTER(wt.LPVOID),
                c.POINTER(wt.LPVOID),c.POINTER(wt.LPVOID),
                c.POINTER(wt.LPVOID),c.POINTER(wt.LPVOID))
    g.restype=wt.DWORD
    if g(str(p),1,0x5,c.byref(owner),None,c.byref(dacl),None,c.byref(sd))!=0 or not sd:
        _blocked()
    try:
        control=wt.WORD()
        revision=wt.DWORD()
        get_control=adv.GetSecurityDescriptorControl
        get_control.argtypes=(wt.LPVOID,c.POINTER(wt.WORD),c.POINTER(wt.DWORD))
        get_control.restype=wt.BOOL
        if not get_control(sd,c.byref(control),c.byref(revision)):
            _blocked()
        if (control.value & 0x1004)!=0x1004 or not dacl or not owner:
            _blocked()  # No NULL DACL, or unprotected inherited ACL.
        user=current_user_sid()
        if _sid_string(adv,kernel,owner,c,wt)!=user:
            _blocked()
        class AclSize(c.Structure):
            _fields_=(("count",wt.DWORD),("inuse",wt.DWORD),("free",wt.DWORD))
        info=AclSize()
        getinfo=adv.GetAclInformation
        getinfo.argtypes=(wt.LPVOID,wt.LPVOID,wt.DWORD,c.c_int)
        getinfo.restype=wt.BOOL
        if not getinfo(dacl,c.byref(info),c.sizeof(info),2) or not 1<=info.count<=24:
            _blocked()
        getace=adv.GetAce
        getace.argtypes=(wt.LPVOID,wt.DWORD,c.POINTER(wt.LPVOID))
        getace.restype=wt.BOOL
        allowed={user,"S-1-5-18","S-1-5-32-544"}
        owner_mask=0
        for index in range(info.count):
            ace=wt.LPVOID()
            if not getace(dacl,index,c.byref(ace)):
                _blocked()
            address=c.cast(ace,c.c_void_p).value
            kind=c.c_ubyte.from_address(address).value
            flags=c.c_ubyte.from_address(address+1).value
            length=c.c_ushort.from_address(address+2).value
            if kind not in (0,1) or flags & 0x10 or length<16:
                _blocked()  # no unknown/object ACE or inherited grants
            mask=c.c_uint32.from_address(address+4).value
            sid=_sid_string(adv,kernel,wt.LPVOID(address+8),c,wt)
            if kind==0:
                if sid not in allowed:
                    _blocked()
                if sid==user and not flags & 0x08:
                    owner_mask|=mask
            elif sid==user:
                _blocked()
        if (owner_mask & 0x3)!=0x3 and not (owner_mask & 0x10000000):
            _blocked()
        return True
    finally:
        kernel.LocalFree.argtypes=(wt.HLOCAL,)
        kernel.LocalFree.restype=wt.HLOCAL
        kernel.LocalFree(sd)
