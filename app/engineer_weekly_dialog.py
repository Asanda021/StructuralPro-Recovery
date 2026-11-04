"""Floating Persian independent weekly plans per engineer, even with auto-WBS off."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QLabel,
    QTableWidget,QTableWidgetItem,QHeaderView,QPushButton,QMessageBox,QInputDialog,
)
from core.projects.engineer_weekly_plan import (
    create_engineer_week,add_week_item,check_week_item,set_week_item_status,
    weekly_summary,week_start_of,
)

class EngineerWeeklyDialog(QDialog):
    def __init__(self,get_plans,set_plans,get_activities,source_sha256,parent=None,*,get_team=None,get_wbs=None):
        super().__init__(parent)
        self.setWindowTitle("برنامه هفتگی مستقل مهندسان | روز، تاریخ، کارهای قابل انجام و چک‌لیست")
        self.setObjectName("EngineerWeeklyPlanningDialog")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1160,700)
        self._get=get_plans
        self._set=set_plans
        self._activities=get_activities
        self._sha=source_sha256
        self._team=get_team
        self._wbs=get_wbs
        self._rows=[]
        root=QVBoxLayout(self)
        form=QFormLayout()
        self.engineer_id=QLineEdit()
        self.engineer_id.setObjectName("WeeklyEngineerID")
        self.engineer_id.setPlaceholderText("شناسه یکتای مهندس، مثل supervisor-1")
        self.engineer_name=QLineEdit()
        self.engineer_name.setObjectName("WeeklyEngineerName")
        self.engineer_name.setPlaceholderText("نام مهندس مسئول")
        self.week_date=QLineEdit()
        self.week_date.setObjectName("WeeklyReferenceDate")
        self.week_date.setPlaceholderText("یکی از روزهای هفته، ۱۴۰۵/۰۸/۰۹ تا ۱۴۱۰")
        form.addRow("شناسه مهندس",self.engineer_id)
        form.addRow("نام مهندس",self.engineer_name)
        form.addRow("تاریخ یکی از روزهای هفته",self.week_date)
        root.addLayout(form)
        bar=QHBoxLayout()
        self.show_button=QPushButton("نمایش برنامه این مهندس")
        self.show_button.setObjectName("ShowEngineerWeek")
        self.show_button.clicked.connect(self.refresh)
        self.engineer_id.editingFinished.connect(self.refresh)
        self.week_date.editingFinished.connect(self.refresh)
        self.create_button=QPushButton("تولید / به‌روزرسانی هفته از زمان‌بندی اصلی")
        self.create_button.setObjectName("CreateEngineerWeek")
        self.create_button.clicked.connect(self._create)
        self.add_button=QPushButton("ثبت کار و چک‌لیست برای روز انتخابی")
        self.add_button.setObjectName("AddEngineerDailyWork")
        self.add_button.clicked.connect(self._add_work)
        self.check_button=QPushButton("علامت‌گذاری چک‌لیست")
        self.check_button.setObjectName("ToggleEngineerChecklist")
        self.check_button.clicked.connect(self._check_item)
        self.complete_button=QPushButton("تأیید اتمام فعالیت")
        self.complete_button.setObjectName("CompleteEngineerDailyWork")
        self.complete_button.clicked.connect(self._complete)
        self.revoke_audit=QPushButton("سوابق کنترل‌های نیازمند بازبینی")
        self.revoke_audit.setObjectName("WeeklyRevokedInspectionAudit")
        self.revoke_audit.clicked.connect(self._show_revoked_history)
        for widget in (self.show_button,self.create_button,self.add_button,
                       self.check_button,self.complete_button,self.revoke_audit):
            bar.addWidget(widget)
        root.addLayout(bar)
        self.description=QLabel(
            "هر مهندس برنامه و چک‌لیست مستقل دارد. ثبت تیک، پیشرفت فیزیکی یا تحویل قطعی پروژه را خودکار تأیید نمی‌کند."
        )
        self.description.setWordWrap(True)
        root.addWidget(self.description)
        self.table=QTableWidget(0,7)
        self.table.setObjectName("EngineerWeeklyDaysTable")
        self.table.setHorizontalHeaderLabels(
            ("روز","تاریخ شمسی","کار قابل انجام","اولویت","چک‌لیست","وضعیت","شماره منبع/WBS")
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)
        self.details=QLabel("")
        self.details.setWordWrap(True)
        root.addWidget(self.details)
        self.table.itemSelectionChanged.connect(self._show_details)
        self.refresh()

    def _selected_week(self):
        identity=self.engineer_id.text().strip()
        raw=self.week_date.text().strip()
        first=week_start_of(raw)
        match=next((p for p in self._get()
                    if p.get("engineer_id")==identity and p.get("week_start")==first),None)
        if match is None:raise ValueError("ابتدا برنامه این مهندس و این هفته را ایجاد کنید")
        if match.get("source_sha256")!=self._sha:
            raise ValueError("نسخه نقشه تغییر کرده است؛ برنامه قدیمی قابل ویرایش نیست")
        return match

    def _create(self):
        try:
            if self._team is not None and self._wbs is not None:
                from core.projects.weekly_ownership import derive_weeks
                result=derive_weeks(
                    self._team(),self._wbs(),self.week_date.text(),
                    self._get(),self._sha
                )
                self._set(result["plans"])
            else:
                raise ValueError("برنامه هفتگی باید از زمان‌بندی اصلی استخراج شود")
        except (ValueError,TypeError) as exc:
            QMessageBox.warning(self,"ساخت برنامه مهندس",str(exc))
        self.refresh()

    def _row(self):
        if not self.table.selectedItems():raise ValueError("روز یا فعالیت جدول را انتخاب کنید")
        idx=self.table.currentRow()
        if idx<0 or idx>=len(self._rows):raise ValueError("انتخاب جدول نامعتبر است")
        return self._rows[idx]

    def _add_work(self):
        try:
            week=self._selected_week()
            day,_,_=self._row()
            title,ok=QInputDialog.getText(self,"برنامه کاری روزانه","کار قابل انجام:")
            if not ok:return
            selected=[t.get("id") for t in self._activities() if t.get("id")]
            selected.insert(0,"بدون اتصال به WBS")
            activity,ok=QInputDialog.getItem(
                self,"ارجاع به WBS","فعالیت مرتبط (اختیاری):",selected,0,False
            )
            if not ok:return
            text,ok=QInputDialog.getText(
                self,"چک‌لیست روز","موارد چک‌لیست را با «،» جدا کن:"
            )
            if not ok:return
            items=[v.strip() for v in text.replace(",", "،").split("،") if v.strip()]
            changed=add_week_item(self._get(),week["engineer_id"],week["week_start"],
                day,title,activity_id="" if activity=="بدون اتصال به WBS" else activity,
                checklist=items)
            self._set(changed)
        except (ValueError,TypeError) as exc:
            QMessageBox.warning(self,"کار هفتگی",str(exc))
        self.refresh()

    def _check_item(self):
        try:
            week=self._selected_week()
            day,entry,_=self._row()
            if entry is None:raise ValueError("اول برای این روز فعالیت ثبت کنید")
            checks=entry["checklist"]
            if not checks:raise ValueError("این فعالیت چک‌لیست ندارد")
            lines=[f"{x['id']} | {'✓' if x['done'] else '□'} {x['text']}" for x in checks]
            chosen,ok=QInputDialog.getItem(
                self,"ثبت چک‌لیست","مورد قابل بررسی:",lines,0,False
            )
            if not ok:return
            check=checks[lines.index(chosen)]
            reviewer,ok=QInputDialog.getText(self,"ثبت مسئول بررسی","نام ثبت‌کننده:")
            if not ok:return
            changed=check_week_item(
                self._get(),week["engineer_id"],week["week_start"],day,
                entry["id"],check["id"],done=not check["done"],operator=reviewer
            )
            self._set(changed)
        except (ValueError,TypeError) as exc:
            QMessageBox.warning(self,"چک‌لیست مهندس",str(exc))
        self.refresh()

    def _complete(self):
        try:
            week=self._selected_week()
            day,entry,_=self._row()
            if entry is None:raise ValueError("این روز فعالیتی ثبت نشده است")
            reviewer,ok=QInputDialog.getText(self,"ثبت کار انجام‌شده","نام بازبین مسئول:")
            if not ok:return
            self._set(set_week_item_status(
                self._get(),week["engineer_id"],week["week_start"],
                day,entry["id"],"done",operator=reviewer
            ))
        except (ValueError,TypeError) as exc:
            QMessageBox.warning(self,"ثبت اتمام کار",str(exc))
        self.refresh()

    def _show_revoked_history(self):
        try:
            week=self._selected_week()
        except ValueError as exc:
            QMessageBox.warning(self,"سوابق کنترل‌های تغییرکرده",str(exc))
            return
        history=week.get("invalidated_inspection_history",[])
        if not history:
            QMessageBox.information(self,"سوابق کنترل‌های تغییرکرده",
                                    "این هفته کنترل امضاشده باطل‌شده ندارد.")
            return
        lines=[]
        for item in history[-40:]:
            old=item.get("old_signed_record",{})
            signatures=", ".join(
                str(check.get("checked_by",""))
                for check in old.get("checklist",[])
                if check.get("done") and check.get("checked_by")
            )
            lines.append(
                f"{item.get('date','')} | {old.get('title','')} | "
                f"ثبت‌کنندگان: {signatures or 'نامشخص'} | "
                f"علت: {item.get('reason','')}"
            )
        QMessageBox.information(self,"سوابق کنترل‌های تغییرکرده",
            "\n".join(lines)+"\nاین موارد باید دوباره توسط مسئول بررسی شوند.")

    def _show_details(self):
        try:
            _,task,_=self._row()
        except ValueError:
            self.details.setText("")
            return
        if task is None:
            self.details.setText("برای این روز کار جدید ثبت کنید.")
            return
        self.details.setText(
            "چک‌لیست: "+" | ".join(
                ("✓ " if check["done"] else "□ ")+check["text"]
                for check in task["checklist"]
            )+" | توضیحات: "+str(task.get("notes",""))
        )

    def refresh(self):
        try:
            week=self._selected_week()
        except ValueError:
            self.table.setRowCount(0)
            self._rows=[]
            self.description.setText(
                "برای هر مهندس و هر هفته برنامه مستقل ایجاد کن؛ ابتدا شناسه، نام و تاریخ را ثبت کن."
            )
            return
        self._rows=[]
        for day in week["days"]:
            if not day["work_items"]:
                self._rows.append((day["jalali"],None,day))
            else:
                self._rows.extend((day["jalali"],work,day) for work in day["work_items"])
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self._rows))
            for row,(date,work,day) in enumerate(self._rows):
                checks=work["checklist"] if work else []
                cols=(
                    day["day_name"],date,
                    work["title"] if work else "(بدون کار ثبت‌شده)",
                    work["priority"] if work else "",
                    f"{sum(x['done'] for x in checks)}/{len(checks)}" if work else "0/0",
                    work["status"] if work else "ثبت‌نشده",
                    (work.get("activity_id") or work.get("source_ref") or "") if work else "",
                )
                for col,value in enumerate(cols):
                    item=QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row,col,item)
            summary=weekly_summary(self._get(),week["engineer_id"],week["week_start"])
            self.description.setText(
                f"مهندس {week['engineer_name']} | هفته شروع {week['week_start']} | "
                f"کارها: {summary['item_count']} | انجام‌شده با تأیید: {summary['completed_items']} | "
                f"چک‌لیست: {summary['checked_count']}/{summary['checklist_count']} | "
                f"سوابق نیازمند بازبینی: {len(week.get('invalidated_inspection_history',[]))} | "
                "فعالیت‌های هفتگی از WBS اصلی استخراج شده‌اند؛ تأیید اجرایی مستقل لازم است"
            )
        finally:
            self.table.blockSignals(False)
