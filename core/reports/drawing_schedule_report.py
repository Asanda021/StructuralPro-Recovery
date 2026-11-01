"""Source-bound Persian draft WBS exports through the existing report engine.

No baseline, quantity, calendar, crew rate or critical path is approved here.
Stage the entire bundle privately and reject a changed source/plan before
publishing it. The drawing and project databases are never modified.
"""
from __future__ import annotations

from copy import deepcopy
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import shutil
import tempfile

from core.reports.project_report import build_report


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _source_state(path):
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            digest = file_digest(stream, "sha256").hexdigest()
            after = os.fstat(stream.fileno())
        current = path.stat()
    except OSError as exc:
        raise ValueError("پرونده منبع زمان‌بندی در دسترس نیست") from exc
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if identity(before) != identity(after) or identity(after) != identity(current):
        raise ValueError("هویت منبع هنگام کنترل خروجی تغییر کرده است")
    return digest, identity(current)


def _checked_plan(plan):
    from core.drawings.workflow_planning import recompute_schedule, apply_resource_limits
    if (not isinstance(plan, dict) or plan.get("schema") != "structuralpro.drawing-workflow-v1"
            or plan.get("status") != "DRAFT_UNAPPROVED"):
        raise ValueError("خروجی تنها از برنامه پیش‌نویس معتبر ساخته می‌شود")
    if not plan.get("calendar", {}).get("start_date"):
        raise ValueError("ابتدا تاریخ شروع و تقویم برنامه را مشخص کنید")
    if not isinstance(plan.get("tasks"), list) or not 0 < len(plan["tasks"]) <= 10000:
        raise ValueError("فهرست فعالیت‌های زمان‌بندی معتبر نیست")
    checked = deepcopy(plan)
    if plan.get("resource_leveling_status") == "PROPOSED_UNAPPROVED":
        checked = apply_resource_limits(checked, checked.get("resource_limits"), level=True)
    else:
        recompute_schedule(checked)
    for actual, expected in zip(plan["tasks"], checked["tasks"]):
        for key in ("start_workday_offset", "end_workday_offset", "start_jalali", "finish_jalali"):
            if actual.get(key) != expected.get(key):
                raise ValueError("جدول و تاریخ‌های برنامه با محاسبه شبکه تطبیق ندارند؛ برنامه را تازه‌سازی کنید")
    return checked


def _quantities(task):
    totals = defaultdict(Decimal)
    for record in task.get("measured", {}).values():
        try:
            value = Decimal(str(record["quantity"]))
        except (KeyError, InvalidOperation, ValueError) as exc:
            raise ValueError("مقدار متره زمان‌بندی معتبر نیست") from exc
        if not value.is_finite() or value < 0:
            raise ValueError("مقدار متره زمان‌بندی باید متناهی و غیرمنفی باشد")
        totals[str(record.get('unit', 'واحد نامشخص'))] += value
    rows = [f"{value} {unit}" for unit, value in sorted(totals.items())[:3]]
    if len(totals) > 3:
        rows.append(f"{len(totals)} نوع واحد؛ جزئیات کامل در CSV")
    if task.get("scheduled_quantity") is not None:
        rows.append("مقدار پس از ضریب مستند: " + str(task["scheduled_quantity"]))
    return "؛ ".join(rows) if rows else "متره ثبت نشده"


def _gantt(plan, directory, checkpoint):
    from core.projects.jalali_dates import jalali_to_gregorian
    from core.reports.project_control_figures import canvas
    tasks = plan["tasks"]
    first = jalali_to_gregorian(plan["calendar"]["start_date"])
    last = max(jalali_to_gregorian(t["finish_jalali"]) for t in tasks) + timedelta(days=1)
    span = max(1, (last-first).days)
    def x(day):
        return 510 + int((day-first).days/span*720)
    figures = []
    for begin in range(0, len(tasks), 22):
        checkpoint("ترسیم گانت " + str(begin//22+1))
        group = tasks[begin:begin+22]
        image, draw, label = canvas("گانت پیشنهادی؛ مبنا و مسیر بحرانی تصویب نشده", 135+len(group)*48)
        label((510, 48), plan["calendar"]["start_date"])
        label((1020, 48), max(t["finish_jalali"] for t in tasks))
        draw.line((510, 72, 1230, 72), fill="#bac8d8")
        for row, task in enumerate(group):
            y = 87 + row*48
            label((12,y), str(begin+row+1))
            label((55,y), str(task["title"])[:38])
            start = jalali_to_gregorian(task["start_jalali"])
            end = jalali_to_gregorian(task["finish_jalali"]) + timedelta(days=1)
            left = x(start)
            if task["duration_days"] == 0:
                draw.polygon([(left,y),(left+5,y+8),(left,y+16),(left-5,y+8)],fill="#ac7b27")
            else:
                draw.rectangle((left,y,max(left+3,x(end)),y+17),fill="#347eaf")
            label((left,y+20), str(task["duration_days"]) + " روز کاری", "#526577")
        path = directory/f"gantt-{begin//22+1}.png"
        image.save(path)
        figures.append({"path":str(path),"caption":"گانت تاریخ‌دارِ پیش‌نویس؛ بخش " + str(begin//22+1)})
    return figures


class ScheduleExportCancelled(RuntimeError):
    pass


@dataclass
class PreparedScheduleBundle:
    stage: Path
    destination: Path
    source: Path
    source_state: tuple
    plan_sha256: str
    manifest: dict

    def discard(self):
        if self.stage.exists():
            shutil.rmtree(self.stage)


def publish_prepared_schedule_bundle(prepared, current_plan):
    """GUI-thread handoff checks the current plan, never a stale worker copy."""
    try:
        if _source_state(prepared.source) != prepared.source_state:
            raise ValueError("منبع هنگام ساخت خروجی تغییر کرده؛ کل بسته کنار گذاشته شد")
        if sha256(_json(current_plan).encode()).hexdigest() != prepared.plan_sha256:
            raise ValueError("نسخه برنامه هنگام ساخت خروجی تغییر کرده؛ کل بسته کنار گذاشته شد")
        if prepared.destination.exists():
            raise FileExistsError("پوشه خروجی هم‌زمان ایجاد شده است")
        prepared.stage.rename(prepared.destination)
        return {"destination":str(prepared.destination), "manifest":prepared.manifest}
    finally:
        prepared.discard()


def prepare_drawing_schedule_bundle(plan, destination, *, cancel_event=None, progress=None):
    def checkpoint(message):
        if cancel_event is not None and cancel_event.is_set():
            raise ScheduleExportCancelled("ساخت خروجی لغو شد؛ هیچ بسته‌ای ثبت نشد")
        if progress is not None:
            progress(message)
    checkpoint("کنترل نسخه و منبع برنامه")
    original_plan_digest = sha256(_json(plan).encode()).hexdigest()
    snapshot = _checked_plan(plan)
    source = Path(str(snapshot.get("drawing_source", "")))
    if not source.is_file():
        raise ValueError("پرونده منبع زمان‌بندی موجود نیست")
    before = _source_state(source)
    if before[0] != snapshot.get("source_sha256"):
        raise ValueError("هش منبع با نسخه برنامه مطابقت ندارد")
    target = Path(destination)
    if target.exists():
        raise FileExistsError("پوشه خروجی از قبل وجود دارد؛ پوشه تازه‌ای انتخاب کنید")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".structuralpro-schedule-", dir=target.parent))
    prepared = None
    try:
        rows=[]
        details=[]
        for number, task in enumerate(snapshot["tasks"], 1):
            refs = list(map(str, task.get("linked_item_ids",[])))
            reference_summary = "، ".join(ref[:48] + ("…" if len(ref)>48 else "") for ref in refs[:3])
            if len(refs)>3:
                reference_summary += f"؛ {len(refs)} ردیف، جزئیات کامل در CSV"
            rows.append({"item_no":number,"item_code":task["id"],"description":task["title"],
                "مدت روز کاری":task["duration_days"],"شروع شمسی":task["start_jalali"],
                "پایان شمسی":task["finish_jalali"],"اکیپ":task.get("crew","تعیین نشده"),
                "مقدار و واحد":_quantities(task),
                "ردیف منبع":reference_summary,
                "وضعیت":"پیش‌نویس؛ نیازمند بازبینی مقدار، نرخ و تقویم"})
            for item_id in sorted(set(refs) | set(task.get("measured", {}))):
                record=task.get("measured",{}).get(item_id,{})
                details.append({"item_no":len(details)+1,"item_code":task["id"],
                    "description":task["title"],"source_id":item_id,
                    "quantity":record.get("quantity"),"unit":record.get("unit"),
                    "notes":record.get("source_ref", "منبع متره ثبت نشده"),
                    "status":"DRAFT_UNAPPROVED"})
        metadata={"منبع":source.name,"SHA-256 منبع":before[0],
                  "وضعیت":"پیش‌نویس؛ تاریخ تحویل و مسیر بحرانی مصوب نیست",
                  "مدت صفر":"رویداد یا مقدار/نرخ نامشخص؛ نشانه تکمیل کار نیست",
                  "تعطیلات آینده":"نیازمند بازبینی سال‌نامه و شرایط پروژه",
                  "_custom_header":"زمان‌بندی پیشنهادی؛ فاقد تصویب مبنا",
                  "جزئیات متره":"تمام شناسه‌ها و مقادیر در measurement-details.csv و draft-schedule.json",
                  "_figures":_gantt(snapshot,stage,checkpoint)}
        report=build_report("StructuralPro | برنامه زمان‌بندی پیش‌نویس",rows,metadata=metadata)
        report.selected_columns=[("item_no","ردیف"),("item_code","شناسه فعالیت"),
            ("description","شرح فعالیت"),("مدت روز کاری","مدت روز کاری"),
            ("شروع شمسی","شروع شمسی"),("پایان شمسی","پایان شمسی"),
            ("اکیپ","اکیپ"),("مقدار و واحد","مقدار و واحد"),
            ("ردیف منبع","ردیف منبع"),("وضعیت","وضعیت")]
        for fmt in ("xlsx","pdf"):
            checkpoint("ساخت خروجی " + fmt.upper())
            report.export(stage/f"schedule.{fmt}",fmt)
        detail=build_report("جزئیات ریزمتره زمان‌بندی پیش‌نویس",details,
            metadata={"SHA-256 منبع":before[0],"وضعیت":"فاقد تأیید مقدار و مبنا"})
        detail.export(stage/"measurement-details.csv","csv")
        (stage/"draft-schedule.json").write_text(_json(snapshot),encoding="utf-8")
        manifest={"schema":"structuralpro.draft-drawing-schedule-bundle-v1",
            "status":"DRAFT_UNAPPROVED","source_name":source.name,"source_sha256":before[0],
            "plan_sha256":original_plan_digest,"critical_path_approved":False,
            "snapshot_sha256":sha256(_json(snapshot).encode()).hexdigest(),
            "quantities_approved":False,"baseline_approved":False,
            "calendar_approved":bool(snapshot.get("calendar_approved")),
            "files":[{"name":p.name,"sha256":_source_state(p)[0],"bytes":p.stat().st_size}
                     for p in sorted(stage.iterdir()) if p.is_file()]}
        (stage/"manifest.json").write_text(_json(manifest),encoding="utf-8")
        checkpoint("کنترل نهایی نسخه و منبع")
        if _source_state(source)!=before:
            raise ValueError("منبع هنگام ساخت خروجی تغییر کرده؛ کل بسته کنار گذاشته شد")
        if sha256(_json(plan).encode()).hexdigest()!=original_plan_digest:
            raise ValueError("نسخه برنامه هنگام ساخت خروجی تغییر کرده؛ کل بسته کنار گذاشته شد")
        prepared=PreparedScheduleBundle(stage,target,source,before,original_plan_digest,manifest)
        return prepared
    finally:
        if prepared is None and stage.exists():
            shutil.rmtree(stage)


def export_drawing_schedule_bundle(plan, destination):
    """Synchronous API for services/CLI; Qt uses prepare/publish on a worker."""
    return publish_prepared_schedule_bundle(prepare_drawing_schedule_bundle(plan,destination),plan)
