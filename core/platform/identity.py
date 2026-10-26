"""Trusted local operating-system identity for offline authorization.

This module deliberately does not use environment variables or UI text as an
authentication source.  On Windows the SID comes from the live access token;
on POSIX the subject is the effective kernel UID.  This proves the local OS
session identity, not an identity independent of a local administrator.
"""
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class OperatingSystemIdentity:
    subject_id: str
    display_name: str
    authority: str
    platform: str
    authenticated: bool

    def __post_init__(self) -> None:
        if not self.authenticated or not self.subject_id.strip() or not self.authority.strip():
            raise RuntimeError("operating-system identity is not authenticated")


class SystemIdentityProvider:
    """Resolve the identity attached to the current process/thread token."""

    trusted_for_legacy_claim = True

    def current(self) -> OperatingSystemIdentity:
        if os.name == "nt":
            return self._windows_identity()
        return self._posix_identity()

    def owns_path(self, identity: OperatingSystemIdentity, path) -> bool:
        """Return whether the authenticated subject owns an existing file."""
        if os.name != "nt":
            try:
                return identity.subject_id == f"uid:{os.stat(path).st_uid}"
            except OSError:
                return False
        return self._windows_file_owner_sid(path) == identity.subject_id

    @staticmethod
    def _posix_identity() -> OperatingSystemIdentity:
        import pwd

        uid = os.geteuid()
        account = pwd.getpwuid(uid).pw_name
        return OperatingSystemIdentity(
            subject_id=f"uid:{uid}",
            display_name=account,
            authority="posix-euid",
            platform="posix",
            authenticated=True,
        )

    @staticmethod
    def _windows_identity() -> OperatingSystemIdentity:
        import ctypes
        from ctypes import wintypes

        token_query = 0x0008
        token_user = 1
        error_insufficient_buffer = 122
        error_no_token = 1008
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.GetCurrentThread.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.LocalFree.argtypes = [wintypes.HLOCAL]
        kernel.LocalFree.restype = wintypes.HLOCAL
        advapi.OpenThreadToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.POINTER(wintypes.HANDLE)]
        advapi.OpenThreadToken.restype = wintypes.BOOL
        advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        advapi.OpenProcessToken.restype = wintypes.BOOL
        advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        advapi.GetTokenInformation.restype = wintypes.BOOL
        advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
        advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
        advapi.LookupAccountSidW.argtypes = [
            wintypes.LPCWSTR, ctypes.c_void_p, wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
        ]
        advapi.LookupAccountSidW.restype = wintypes.BOOL

        class SidAndAttributes(ctypes.Structure):
            _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

        class TokenUser(ctypes.Structure):
            _fields_ = [("User", SidAndAttributes)]

        handle = wintypes.HANDLE()
        if not advapi.OpenThreadToken(kernel.GetCurrentThread(), token_query, True, ctypes.byref(handle)):
            error = ctypes.get_last_error()
            if error != error_no_token or not advapi.OpenProcessToken(
                kernel.GetCurrentProcess(), token_query, ctypes.byref(handle)
            ):
                raise OSError(ctypes.get_last_error(), "cannot query the live Windows access token")
        try:
            size = wintypes.DWORD()
            advapi.GetTokenInformation(handle, token_user, None, 0, ctypes.byref(size))
            if ctypes.get_last_error() != error_insufficient_buffer or not size.value:
                raise OSError(ctypes.get_last_error(), "cannot size Windows TokenUser")
            buffer = ctypes.create_string_buffer(size.value)
            if not advapi.GetTokenInformation(handle, token_user, buffer, size, ctypes.byref(size)):
                raise OSError(ctypes.get_last_error(), "cannot read Windows TokenUser")
            sid = ctypes.cast(buffer, ctypes.POINTER(TokenUser)).contents.User.Sid
            sid_text = wintypes.LPWSTR()
            if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)):
                raise OSError(ctypes.get_last_error(), "cannot convert Windows SID")
            try:
                subject = sid_text.value
            finally:
                kernel.LocalFree(sid_text)

            name_size = wintypes.DWORD(0)
            domain_size = wintypes.DWORD(0)
            sid_type = wintypes.DWORD()
            advapi.LookupAccountSidW(
                None, sid, None, ctypes.byref(name_size), None,
                ctypes.byref(domain_size), ctypes.byref(sid_type),
            )
            name = ctypes.create_unicode_buffer(name_size.value or 1)
            domain = ctypes.create_unicode_buffer(domain_size.value or 1)
            display = subject
            if advapi.LookupAccountSidW(
                None, sid, name, ctypes.byref(name_size), domain,
                ctypes.byref(domain_size), ctypes.byref(sid_type),
            ):
                display = f"{domain.value}\\{name.value}" if domain.value else name.value
            return OperatingSystemIdentity(
                subject_id=subject,
                display_name=display,
                authority="windows-access-token",
                platform="windows",
                authenticated=True,
            )
        finally:
            kernel.CloseHandle(handle)

    @staticmethod
    def _windows_file_owner_sid(path) -> str:
        import ctypes
        from ctypes import wintypes

        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi.GetNamedSecurityInfoW.argtypes = [
            wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        ]
        advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
        advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
        advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
        kernel.LocalFree.argtypes = [wintypes.HLOCAL]
        kernel.LocalFree.restype = wintypes.HLOCAL
        owner = ctypes.c_void_p()
        descriptor = ctypes.c_void_p()
        status = advapi.GetNamedSecurityInfoW(
            str(path), 1, 1, ctypes.byref(owner), None, None, None,
            ctypes.byref(descriptor),
        )
        if status:
            raise OSError(status, "cannot read Windows database file owner")
        try:
            sid_text = wintypes.LPWSTR()
            if not advapi.ConvertSidToStringSidW(owner, ctypes.byref(sid_text)):
                raise OSError(ctypes.get_last_error(), "cannot convert Windows file-owner SID")
            try:
                return sid_text.value
            finally:
                kernel.LocalFree(sid_text)
        finally:
            kernel.LocalFree(descriptor)

