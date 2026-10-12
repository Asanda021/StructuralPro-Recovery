"""Reusable UX polish primitives shared by StructuralPro desktop surfaces."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class UXAction:
    key: str
    label: str
    shortcut: str
    tooltip: str

DEFAULT_ACTIONS=(
    UXAction("new_project","پروژه جدید","Ctrl+N","ساخت پروژه جدید"),
    UXAction("open_project","بازکردن پروژه","Ctrl+O","بازکردن پروژه موجود"),
    UXAction("save","ذخیره","Ctrl+S","ذخیره تغییرات پروژه"),
    UXAction("help","راهنما","F1","نمایش راهنمای سریع"),
    UXAction("search","جستجو","Ctrl+K","جستجوی سریع در ابزارها"),
)

def navigation_groups() -> tuple[tuple[str, tuple[str,...]], ...]:
    return (
        ("شروع",("داشبورد","پروژه‌ها")),
        ("متره و برآورد",("متره سریع","متره از نقشه","فهرست‌بها","برآورد و BOQ")),
        ("مدیریت پروژه",("صورت‌وضعیت","گزارشات","اسناد پروژه")),
        ("کنترل و ابزار",("ابزارهای حرفه‌ای","کنترل کیفیت","هوش مصنوعی آفلاین")),
        ("سیستم",("تنظیمات","راهنما")),
    )

def quick_status(*, project_name: str="", dirty: bool=False, offline: bool=True) -> str:
    project = project_name.strip() or "بدون پروژه"
    state = "● تغییر ذخیره‌نشده" if dirty else "● ذخیره‌شده"
    mode = "آفلاین" if offline else "آنلاین"
    return f"{project}  |  {state}  |  حالت {mode}"
