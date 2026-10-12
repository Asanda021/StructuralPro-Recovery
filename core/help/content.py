"""In-app help content kept deterministic and offline."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class HelpTopic:
    key: str
    title: str
    summary: str
    steps: tuple[str,...]

TOPICS=(
 HelpTopic("start","شروع کار","از ساخت پروژه تا گزارش خروجی",
   ("پروژه جدید بسازید.","متره را ثبت یا از نقشه استخراج کنید.","BOQ و برآورد را بازبینی کنید.","گزارش موردنیاز را خروجی بگیرید.")),
 HelpTopic("takeoff","متره","ثبت و کنترل مقادیر پروژه",
   ("پروژه را انتخاب کنید.","مقادیر را ثبت کنید یا نقشه را بررسی کنید.","منبع و واحد هر مقدار را کنترل کنید.","قبل از انتقال به BOQ بازبینی کنید.")),
 HelpTopic("reports","گزارش‌ها","خروجی حرفه‌ای پروژه",
   ("پروژه و دوره را انتخاب کنید.","فرمت XLSX/PDF/DOCX/CSV را انتخاب کنید.","گزارش را بسازید.","فایل خروجی و جمع مبالغ را کنترل کنید.")),
 HelpTopic("recovery","پشتیبان و بازیابی","حفاظت از داده‌های پروژه",
   ("قبل از تغییرات مهم Backup بگیرید.","Integrity را کنترل کنید.","در صورت نیاز Backup را Validate کنید.","قبل از جایگزینی پروژه، نسخه قبلی را نگه دارید.")),
 HelpTopic("ai","هوش مصنوعی","دستیار توضیحی و کنترل‌محور",
   ("AI را برای بررسی و توضیح استفاده کنید.","شواهد و Context را بخوانید.","برای تغییرات اثرگذار تأیید صریح لازم است.","محاسبات قطعی را با موتور اصلی کنترل کنید.")),
 HelpTopic("about","درباره برنامه","شناسنامه رسمی StructuralPro",
   ("محصول: StructuralPro","پدیدآورنده و مالک: مهندس محمد سلطانی","وب‌سایت رسمی: ERVIRA.ir","تاریخ تولید: ۱۴۰۵/۰۷/۱۴")),
)

def topics() -> tuple[HelpTopic,...]:
    return TOPICS

def topic(key: str) -> HelpTopic:
    for item in TOPICS:
        if item.key == key: return item
    raise KeyError(key)

def search(query: str) -> list[HelpTopic]:
    q=query.strip().lower()
    if not q: return list(TOPICS)
    return [x for x in TOPICS if q in x.title.lower() or q in x.summary.lower() or q in " ".join(x.steps).lower()]
