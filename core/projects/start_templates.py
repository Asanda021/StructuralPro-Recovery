"""E3: declarative project-start previews over the existing ProjectStore.

No quantities, default geometry, members, WBS dates, crew data or prices. The
four templates are structural suggestions only. Persistence is through the
canonical service and an atomic create-only SQLite transaction.
"""
from __future__ import annotations
from copy import deepcopy
from core.projects.project_model import ProjectModel, _identity
from core.project.domains import DISCIPLINES

TEMPLATE_VERSION = 1
TEMPLATES = {
    "residential": {
        "title": "مسکونی",
        "disciplines": ("architecture", "concrete", "mechanical", "electrical"),
        "checklist": ("مدارک مالکیت و نقشه", "ساختار طبقات", "مسیر متره سازه",
                      "تأسیسات", "بازبینی مصالح و گزارش"),
    },
    "commercial": {
        "title": "تجاری",
        "disciplines": ("architecture", "structural", "mechanical", "electrical"),
        "checklist": ("اسناد کاربری", "تفکیک طبقات و فضاها", "بارگذاری و سازه",
                      "تأسیسات ساختمان", "گزارش مهندسی"),
    },
    "industrial": {
        "title": "صنعتی",
        "disciplines": ("civil", "steel", "mechanical", "electrical"),
        "checklist": ("مدارک و نقشه‌های مصوب", "محوطه و فونداسیون",
                      "سازه صنعتی", "تجهیزات و مسیرها", "هماهنگی رشته‌ها"),
    },
    "renovation": {
        "title": "بازسازی",
        "disciplines": ("architecture", "structural", "mechanical", "electrical"),
        "checklist": ("برداشت وضع موجود", "بازبینی مدارک تاریخی",
                      "بررسی مهندسی وضع موجود", "محدوده تخریب و بازسازی",
                      "تأیید تغییرات توسط مهندس"),
    },
}


def preview_project_start(template_code: str, *, project_id: str, name: str,
                          floor_count: int, floor_names=None, disciplines=None) -> dict:
    if template_code not in TEMPLATES:
        raise ValueError("الگوی شروع پروژه ناشناخته است.")
    if not isinstance(project_id, str) or project_id != project_id.strip() or not _identity(project_id):
        raise ValueError("شناسه پروژه باید صریح و معتبر باشد.")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("نام پروژه باید صریح و معتبر باشد.")
    if isinstance(floor_count, bool) or not isinstance(floor_count, int) or not 1 <= floor_count <= 1000:
        raise ValueError("تعداد طبقات باید عدد صحیح صریح از ۱ تا ۱۰۰۰ باشد.")
    if floor_names is None:
        names=[f"طبقه {i}" for i in range(1, floor_count+1)]
    else:
        if not isinstance(floor_names, (tuple, list)) or len(floor_names)!=floor_count:
            raise ValueError("فهرست اسامی طبقات با تعداد طبقات مطابقت ندارد.")
        names=list(floor_names)
    if any(not isinstance(x,str) or not x.strip() for x in names):
        raise ValueError("نام همه طبقات باید مشخص باشد.")
    if len({_identity(x) for x in names})!=floor_count:
        raise ValueError("نام طبقه تکراری است.")
    preset=TEMPLATES[template_code]
    selected=tuple(preset["disciplines"] if disciplines is None else disciplines)
    if not selected or len(set(selected))!=len(selected) or any(
            not isinstance(x,str) or x not in DISCIPLINES for x in selected):
        raise ValueError("رشته‌ها باید از فهرست مجاز و بدون تکرار انتخاب شوند.")
    model=ProjectModel(project_id=project_id,name=name.strip())
    for i,label in enumerate(names,1):
        model.add_floor(label.strip(), level=f"F{i}")
    errors=model.validate()
    if errors:
        raise ValueError("؛ ".join(errors))
    return {
        "project_id": project_id, "name": name.strip(), "template": template_code,
        "template_title": preset["title"], "template_version": TEMPLATE_VERSION,
        "floors": deepcopy(model.floors), "disciplines": list(selected),
        "checklist": list(preset["checklist"]), "preview_only": True,
        "quantity": None, "price": None, "needs_user_approval": True,
    }


def project_payload(preview: dict) -> dict:
    if not isinstance(preview,dict) or not preview.get("preview_only"):
        raise ValueError("پیش‌نمایش معتبر پروژه لازم است.")
    # Validate the entire preview again; never trust a caller-mutated label.
    verified=preview_project_start(
        preview["template"],project_id=preview["project_id"],name=preview["name"],
        floor_count=len(preview["floors"]),
        floor_names=[f["name"] for f in preview["floors"]],
        disciplines=preview["disciplines"])
    for key in ("floors","disciplines","checklist","template_version","template_title"):
        if preview.get(key)!=verified[key]:
            raise ValueError("پیش‌نمایش از نسخه معتبر الگو فاصله گرفته است.")
    return {
        "id": verified["project_id"], "name": verified["name"], "floors":verified["floors"],
        "members":[], "takeoffs":[], "boq":[], "metadata":{"offline":True},
        "template_start":{
            "code": verified["template"], "version": TEMPLATE_VERSION,
            "disciplines":verified["disciplines"],"checklist":verified["checklist"],
            "checklist_status":"پیشنهادی، فاقد تأیید اجرایی",
        },
    }
