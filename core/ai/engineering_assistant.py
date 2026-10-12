"""Priority 21 — safe, explainable engineering assistant orchestration."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

INTENTS = ("project_review","takeoff_review","boq_review","report_help","workflow_help","engineering_library","model_review","general")
_KEYWORDS = {
    "project_review": ("بررسی پروژه","project review","وضعیت پروژه","کنترل پروژه"),
    "takeoff_review": ("متره","takeoff","مقدار","دوباره شماری","double count"),
    "boq_review": ("boq","فهرست بها","برآورد","بهای واحد","مبلغ"),
    "report_help": ("گزارش","report","pdf","excel","خروجی"),
    "workflow_help": ("مرحله","next action","اقدام بعدی","workflow","گردش کار"),
    "engineering_library": ("استاندارد","مصالح","بتن","میلگرد","concrete","rebar"),
    "model_review": ("ifc","dwg","dxf","bim","مدل","نسخه مدل"),
}

@dataclass(frozen=True)
class AssistantResponse:
    intent: str
    text: str
    confidence: float
    evidence: tuple[dict[str, Any], ...]
    proposals: tuple[dict[str, Any], ...]
    requires_confirmation: bool
    deterministic: bool = True

class EngineeringAssistant:
    """Safe application-level AI facade; never mutates project data."""

    def classify(self, prompt: str) -> tuple[str, float]:
        text = str(prompt or "").casefold().strip()
        if not text: return "general", 0.2
        best = ("general", 0.2)
        for intent, words in _KEYWORDS.items():
            hits = sum(1 for word in words if word.casefold() in text)
            if hits:
                score = min(0.95, 0.55 + 0.12 * hits)
                if score > best[1]: best = (intent, score)
        return best

    def context(self, project: dict[str, Any] | None) -> dict[str, Any]:
        p = project if isinstance(project, dict) else {}
        return {
            "project_id": str(p.get("id", "")), "project_name": str(p.get("name", "")),
            "takeoff_count": len(p.get("takeoffs", []) or []), "boq_count": len(p.get("boq", []) or []),
            "model_source_count": len(p.get("model_sources", []) or []),
            "model_object_count": len(p.get("model_objects", []) or []),
            "finance_document_count": len(p.get("financial_documents", []) or []),
            "management_task_count": len(p.get("project_schedule_tasks", []) or []),
        }

    def respond(self, prompt: str, *, project: dict[str, Any] | None = None,
                validator: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> AssistantResponse:
        intent, confidence = self.classify(prompt)
        ctx = self.context(project)
        evidence: list[dict[str, Any]] = [{"type": "project_context", "data": ctx}]
        if validator and project is not None:
            result = validator(project)
            evidence.append({"type":"validation","errors":len(result.get("errors",[]) or []),
                             "warnings":len(result.get("warnings",[]) or []),"score":result.get("score")})
        if intent == "project_review":
            validation = next((x for x in evidence if x.get("type") == "validation"), None)
            text = (f"بازبینی پروژه انجام شد: {validation['errors']} خطای داده و {validation.get('warnings',0)} هشدار شناسایی شده است."
                    if validation and validation.get("errors",0)
                    else f"بازبینی اولیه پروژه «{ctx['project_name']}» انجام شد؛ {ctx['takeoff_count']} متره و {ctx['boq_count']} ردیف BOQ در زمینه پاسخ قرار گرفت.")
        elif intent == "takeoff_review":
            text = f"در این پروژه {ctx['takeoff_count']} مورد متره ثبت شده است. کنترل صحت و منبع هر مورد باید قبل از اثرگذاری بر BOQ تأیید شود."
        elif intent == "boq_review":
            text = f"BOQ فعلی {ctx['boq_count']} ردیف دارد. دستیار فقط وضعیت و منشأ داده را توضیح می‌دهد و تغییر قیمت یا مقدار را خودکار اعمال نمی‌کند."
        elif intent == "report_help":
            text = "می‌توانم ساختار گزارش، منشأ ردیف‌ها و تفاوت خروجی‌ها را توضیح دهم؛ تولید گزارش از داده‌های قطعی برنامه انجام می‌شود."
        elif intent == "workflow_help":
            text = "گردش کار باید از داده واقعی پروژه پیروی کند؛ پیشنهاد بعدی قابل نمایش است اما اجرای عملیات اثرگذار نیازمند تأیید کاربر است."
        elif intent == "engineering_library":
            text = "کتابخانه مهندسی برای جست‌وجوی مصالح و مراجع است. پاسخ دستیار جایگزین محاسبات قطعی یا تفسیر رسمی آیین‌نامه نیست."
        elif intent == "model_review":
            text = f"مدل پروژه {ctx['model_source_count']} منبع و {ctx['model_object_count']} شیء ثبت‌شده دارد. نگاشت مدل به متره باید قابل ردیابی و قابل تأیید باشد."
        else:
            text = "دستیار مهندسی آماده است. می‌توانم پروژه، متره، BOQ، گزارش، گردش کار و مدل‌های BIM/CAD را بررسی و توضیح دهم."
        proposals: list[dict[str, Any]] = []
        if any(token in str(prompt).casefold() for token in ("اجرا","ثبت کن","حذف","apply","execute","delete")):
            proposals.append({"action":"user_confirmation_required","reason":"عملیات اثرگذار باید پس از تأیید صریح کاربر اجرا شود."})
        return AssistantResponse(intent, text, confidence, tuple(evidence), tuple(proposals), bool(proposals))
