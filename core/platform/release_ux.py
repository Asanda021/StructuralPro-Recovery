"""Installer/update/activation UX contract without network or secrets."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class UpdateInfo:
    current: str
    available: str | None
    channel: str = "stable"

    @property
    def update_available(self) -> bool:
        return bool(self.available and _version_tuple(self.available) > _version_tuple(self.current))

def _version_tuple(v: str) -> tuple[int,int,int]:
    parts=v.strip().split(".")
    if len(parts)!=3 or any(not p.isdigit() for p in parts):
        raise ValueError("version must use MAJOR.MINOR.PATCH")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]

def activation_status(*, licensed: bool, expired: bool=False, revoked: bool=False) -> str:
    if revoked: return "مجوز مسدود شده است"
    if expired: return "مجوز منقضی شده است"
    if licensed: return "مجوز فعال است"
    return "مجوز فعال نشده است"

def update_message(info: UpdateInfo) -> str:
    if info.update_available:
        return f"نسخه جدید {info.available} در کانال {info.channel} موجود است."
    return f"نسخه {info.current} به‌روز است."
