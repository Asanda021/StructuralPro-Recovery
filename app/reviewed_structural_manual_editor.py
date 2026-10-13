"""Functional RTL manual concrete-member review: columns, ties and seven footing/pile forms.

No computed defaults; the SQLite domain review determines whether a member is
ready for BOQ. Geometric sections and reinforcement schedules remain physical
source-backed evidence, never AI estimates.
"""
from __future__ import annotations
from copy import deepcopy
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QPlainTextEdit, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)
from core.takeoff.reviewed_structural import KINDS, preview_member
from core.takeoff.reviewed_components import positive

_REBAR_COLUMNS = (
    "count", "cut_length_m", "unit_weight_kg_m",
    "unit_weight_source", "source_ref", "approved_by",
    "name", "start_m", "end_m", "spacing_m", "first_bar_m", "last_bar_m",
)
_FORM_COLUMNS = ("id", "net_area_m2", "source_ref")


def _rows(grid, keys):
    collected = []
    for row in range(grid.rowCount()):
        values = {}
        for col, key in enumerate(keys):
            cell = grid.item(row, col)
            if cell and cell.text().strip():
                values[key] = cell.text().strip()
        if values:
            collected.append(values)
    return collected


def _show_table(grid, keys, rows):
    grid.setRowCount(0)
    for item in rows:
        grid.insertRow(grid.rowCount())
        for col, key in enumerate(keys):
            if key in item:
                grid.setItem(grid.rowCount()-1, col, QTableWidgetItem(str(item[key])))


def open_manual_structural_editor(service, *, parent=None, project_id="", floor_id=""):
    dialog=QDialog(parent)
    dialog.setWindowTitle("متره دستی تأییدشده سازه بتنی و پی")
    dialog.setObjectName("ReviewedStructuralManualEditor")
    dialog.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    dialog.resize(1200,820)
    main=QVBoxLayout(dialog)
    basic=QFormLayout()
    project=QLineEdit(str(project_id))
    floor=QLineEdit(str(floor_id))
    kinds=QComboBox()
    for code, meta in KINDS.items():
        kinds.addItem(meta[0],code)
    ident=QLineEdit()
    source_id=QLineEdit()
    source_id.setPlaceholderText("شناسه برداشت مستقل از یک دیتایل واقعی")
    for key,widget in (("پروژه",project),("طبقه",floor),("نوع عضو",kinds),
                       ("شناسه عضو",ident),("منبع واقعی",source_id)):
        basic.addRow(key,widget)
    main.addLayout(basic)
    form=QFormLayout()
    shape=QComboBox()
    for title,key in (("مستطیلی / منشوری","rectangular"),
                      ("ستون یا شمع دایره‌ای","circular_column"),
                      ("مقطع‌بندی واقعی تأییدشده","reviewed_sections")):
        shape.addItem(title,key)
    form.addRow("هندسه",shape)
    numeric={}
    names={
        "length":"طول (متر)","width":"عرض (متر)","depth":"عمق مقطع (متر)",
        "height":"ارتفاع واقعی (متر)","thickness":"ضخامت (متر)",
        "diameter":"قطر واقعی (متر)","count":"تعداد فیزیکی عضو",
    }
    for key, label in names.items():
        text=QLineEdit()
        text.setPlaceholderText("عدد صریح؛ مقدار پیش‌فرض ندارد")
        numeric[key]=text
        form.addRow(label,text)
    geometry_ref=QLineEdit()
    geometry_reviewer=QLineEdit()
    form.addRow("مرجع دیتایل هندسه",geometry_ref)
    form.addRow("تأییدکننده هندسه",geometry_reviewer)
    section_layout_ref=QLineEdit()
    section_nonoverlap_approver=QLineEdit()
    form.addRow("مرجع جانمایی ناحیه‌های غیرهم‌پوشان", section_layout_ref)
    form.addRow("تأییدکننده عدم هم‌پوشانی", section_nonoverlap_approver)
    sections=QPlainTextEdit()
    sections.setPlaceholderText(
        "در حالت مقطع‌بندی: فهرست JSON از ناحیه‌های دارای شناسه، ابعاد، "
        "source_ref و approved_by. برای ستون، start_m/end_m لازم است.")
    sections.setMaximumHeight(80)
    form.addRow("جدول ناحیه‌های واقعی",sections)
    main.addLayout(form)
    status=QComboBox()
    status.addItem("نیازمند بازبینی","unreviewed")
    status.addItem("تأییدشده","confirmed")
    status.addItem("عدم کاربرد مستند","not_applicable")
    detail=QComboBox()
    detail.addItem("قالب‌بندی", "formwork")
    review_form=QFormLayout()
    review_form.addRow("گروه دیتایل",detail)
    review_form.addRow("وضعیت گروه",status)
    group_approver=QLineEdit()
    group_ref=QLineEdit()
    group_reason=QLineEdit()
    scope=QLineEdit()
    scope_ref=QLineEdit()
    review_form.addRow("تأییدکننده",group_approver)
    review_form.addRow("مرجع گروه",group_ref)
    review_form.addRow("دلیل عدم کاربرد",group_reason)
    review_form.addRow("دامنه شمارش اعضای تکراری",scope)
    review_form.addRow("مرجع دامنه شمارش",scope_ref)
    main.addLayout(review_form)
    detail_table=QTableWidget(0, len(_REBAR_COLUMNS))
    detail_table.setHorizontalHeaderLabels(list(_REBAR_COLUMNS))
    detail_table.setAlternatingRowColors(True)
    main.addWidget(detail_table,1)
    buttons=QHBoxLayout()
    add=QPushButton("افزودن جزء")
    remove=QPushButton("حذف جزء انتخابی")
    apply=QPushButton("اعمال دیتایل")
    load=QPushButton("بارگذاری")
    save=QPushButton("ذخیره در SQLite")
    preview=QPushButton("بازبینی کل عضو")
    commit=QPushButton("ثبت قطعی BOQ")
    for b in (add,remove,apply,load,save,preview,commit): buttons.addWidget(b)
    main.addLayout(buttons)
    message=QLabel("گروه بررسی‌نشده هرگز به معنی میلگرد صفر یا نبود قالب نیست.")
    message.setWordWrap(True)
    main.addWidget(message)
    state={"data":None,"project_id":None,"revision":0,"current":None,"dirty":False}

    def error(exc):
        QMessageBox.warning(dialog,"کنترل دیتایل سازه",str(exc))

    def context():
        pid, fl, k, mid=project.text().strip(),floor.text().strip(),kinds.currentData(),ident.text().strip()
        if not (pid and fl and mid):
            raise ValueError("پروژه، طبقه و شناسه عضو الزامی‌اند")
        if service.open_project(pid) is None:
            raise ValueError("پروژه موجود نیست")
        return pid,fl,k,mid

    def assure():
        pid,fl,k,mid=context()
        if state["data"] is None or state["project_id"]!=pid or (
            state["data"]["kind"],state["data"]["floor_id"],state["data"]["member_id"]
        )!=(k,fl,mid):
            old=service.get_structural_member(pid,k,fl,mid)
            if old:
                state["data"]=deepcopy(old["data"])
                state["revision"]=old["revision"]
            else:
                state["data"]=service.new_structural_member(k,fl,mid)
                state["revision"]=0
            state["current"]=None
            state["project_id"]=pid
            state["dirty"]=False
        return state["data"]

    def physical_geometry():
        d=assure()
        k=d["kind"]
        selected_shape=shape.currentData()
        if selected_shape=="circular_column" and k not in {"column","bored_pile"}:
            raise ValueError("هندسه دایره‌ای فقط برای ستون یا شمع درجا است")
        if selected_shape=="rectangular" and k=="bored_pile":
            raise ValueError("شمع درجا باید قطر و هندسه تأییدشده داشته باشد")
        actual_keys=("count","diameter","height") if selected_shape=="circular_column" else (
            ("count",) if selected_shape=="reviewed_sections" else KINDS[k][3])
        dimensions={}
        for key in actual_keys:
            raw=numeric[key].text().strip()
            if raw:
                dimensions[key]=int(positive(raw,key,integer=True)) if key=="count" else positive(raw,key)
        if selected_shape=="reviewed_sections":
            if sections.toPlainText().strip():
                positions=json.loads(sections.toPlainText())
                if not isinstance(positions,list):
                    raise ValueError("جدول ناحیه‌ها باید فهرست واقعی باشد")
                dimensions["sections"]=positions
            if section_layout_ref.text().strip():
                dimensions["section_layout_ref"]=section_layout_ref.text().strip()
            if section_nonoverlap_approver.text().strip():
                dimensions["nonoverlap_reviewed_by"]=section_nonoverlap_approver.text().strip()
        ref=geometry_ref.text().strip()
        approver=geometry_reviewer.text().strip()
        if ref: dimensions["source_ref"]=ref
        if approver: dimensions["approved_by"]=approver
        if selected_shape!="rectangular":
            dimensions["shape"]=selected_shape
        before=d["geometry"]
        if dimensions!=before:
            state["dirty"]=True
            d["geometry"]=dimensions
        source=source_id.text().strip()
        new_source={"mode":"manual","source_id":source} if source else {}
        if d["source"]!=new_source:
            state["dirty"]=True
            d["source"]=new_source
        return d

    def show_group():
        d=assure()
        name=detail.currentData()
        part=d["formwork"] if name=="formwork" else d["rebars"][name]
        state["current"]=name
        state_status=part.get("status","unreviewed")
        status.setCurrentIndex(max(status.findData(state_status),0))
        group_approver.setText(str(part.get("approved_by") or ""))
        group_ref.setText(str(part.get("source_ref") or ""))
        group_reason.setText(str(part.get("reason") or ""))
        scope.setText(str(part.get("count_scope") or part.get("area_scope") or ""))
        scope_ref.setText(str(part.get("count_scope_ref") or part.get("area_scope_ref") or ""))
        keys=_FORM_COLUMNS if name=="formwork" else _REBAR_COLUMNS
        detail_table.setColumnCount(len(keys))
        detail_table.setHorizontalHeaderLabels(list(keys))
        _show_table(detail_table, keys, (part.get("surfaces") or []) if name=="formwork"
                    else (part.get("segments") or []))

    def apply_group(name=None):
        d=assure()
        name=name or detail.currentData()
        old=d["formwork"] if name=="formwork" else d["rebars"][name]
        status_name=status.currentData()
        reviewer=group_approver.text().strip()
        ref=group_ref.text().strip()
        new={"status":status_name}
        if status_name=="confirmed":
            if not reviewer or not ref:
                raise ValueError("گروه تأییدشده به تأییدکننده و مرجع واقعی نیاز دارد")
            keys=_FORM_COLUMNS if name=="formwork" else _REBAR_COLUMNS
            raw=_rows(detail_table, keys)
            if not raw:
                raise ValueError("برای گروه تأییدشده جدول دارای حداقل یک ردیف لازم است")
            for line in raw:
                for k in (("net_area_m2",) if name=="formwork" else
                          ("count","cut_length_m","unit_weight_kg_m",
                           "start_m","end_m","spacing_m","first_bar_m","last_bar_m")):
                    if k in line:
                        line[k]=positive(line[k],k,allow_zero=k in
                          {"start_m","first_bar_m"},integer=(k=="count"))
            new.update({"approved_by":reviewer, "source_ref":ref,
                        "surfaces" if name=="formwork" else "segments":raw})
            if scope.text().strip():
                if scope.text().strip() != "total_group":
                    raise ValueError("برای چند عضو، دامنه باید صریحاً total_group باشد")
                new["area_scope" if name=="formwork" else "count_scope"]="total_group"
                new["area_scope_ref" if name=="formwork" else "count_scope_ref"]=scope_ref.text().strip()
        elif status_name=="not_applicable":
            if not (reviewer and ref and group_reason.text().strip()):
                raise ValueError("عدم کاربرد به دلیل، مرجع و تأییدکننده نیاز دارد")
            new.update({"approved_by":reviewer,"source_ref":ref,"reason":group_reason.text().strip()})
        if new!=old:
            state["dirty"]=True
            if name=="formwork":d["formwork"]=new
            else:d["rebars"][name]=new
        state["current"]=name
        message.setText("گروه در پیش‌نویس اعمال شد؛ برای ثبت قطعی باید نسخه ذخیره شود.")

    def refresh_groups():
        d=assure()
        detail.blockSignals(True)
        detail.clear()
        detail.addItem("قالب‌بندی","formwork")
        for name in KINDS[d["kind"]][4]:
            detail.addItem("آرماتور "+name,name)
        detail.blockSignals(False)
        show_group()

    def reload():
        try:
            state["data"]=None
            d=assure()
            source_id.setText(str(d.get("source",{}).get("source_id") or ""))
            geo=d.get("geometry") or {}
            shape.setCurrentIndex(max(shape.findData(geo.get("shape","rectangular")),0))
            for key,w in numeric.items():
                w.setText(str(geo[key]) if key in geo else "")
            geometry_ref.setText(str(geo.get("source_ref") or ""))
            geometry_reviewer.setText(str(geo.get("approved_by") or ""))
            section_layout_ref.setText(str(geo.get("section_layout_ref") or ""))
            section_nonoverlap_approver.setText(str(geo.get("nonoverlap_reviewed_by") or ""))
            sections.setPlainText(json.dumps(geo.get("sections",[]),ensure_ascii=False) if geo.get("sections") else "")
            refresh_groups()
            message.setText("پیش‌نویس بازیابی شد. تکمیل همه گروه‌ها برای ثبت قطعی الزامی است.")
        except Exception as exc:error(exc)

    def change_group(_index):
        try:
            former=state["current"]
            if former and former!=detail.currentData():
                try:apply_group(former)
                except Exception:
                    detail.blockSignals(True)
                    detail.setCurrentIndex(detail.findData(former))
                    detail.blockSignals(False)
                    raise
            show_group()
        except Exception as exc:error(exc)

    def persist():
        try:
            apply_group()
            d=physical_geometry()
            pid,_,_,_=context()
            entry=service.save_structural_member_draft(pid,d,expected_revision=state["revision"])
            state["revision"]=entry["revision"]
            state["dirty"]=False
            message.setText(f"نسخه {entry['revision']} در SQLite ذخیره شد.")
        except Exception as exc:error(exc)

    def inspect():
        try:
            apply_group()
            d=physical_geometry()
            report=preview_member(d,service.takeoff)
            message.setText(("آماده ریزمتره؛ تعداد ردیف: "+str(len(report["rows"])))
                         if report["ready"] else "\n".join(report["blockers"][:12]))
        except Exception as exc:error(exc)

    def finalize():
        try:
            apply_group()
            physical_geometry()
            if state["dirty"]:
                raise ValueError("تغییرات پیش از ثبت قطعی باید در SQLite ذخیره شوند")
            pid,fl,k,mid=context()
            if state["revision"]<=0:
                raise ValueError("پیش‌نویس هنوز ذخیره نشده است")
            report=service.commit_structural_member(pid,k,fl,mid,expected_revision=state["revision"])
            message.setText(f"ثبت قطعی: {report['takeoff_rows']} ردیف در BOQ.")
        except Exception as exc:error(exc)

    add.clicked.connect(lambda: detail_table.insertRow(detail_table.rowCount()))
    def remove_selected():
        selected=sorted({x.row() for x in detail_table.selectedIndexes()},reverse=True)
        for n in selected:detail_table.removeRow(n)
    remove.clicked.connect(remove_selected)
    def apply_clicked():
        try:apply_group()
        except Exception as exc:error(exc)
    apply.clicked.connect(apply_clicked)
    load.clicked.connect(reload)
    save.clicked.connect(persist)
    preview.clicked.connect(inspect)
    commit.clicked.connect(finalize)
    detail.currentIndexChanged.connect(change_group)
    if project.text().strip() and floor.text().strip() and ident.text().strip():
        reload()
    else:
        message.setText("پروژه، طبقه، نوع و شناسه عضو را وارد کنید، سپس «بارگذاری» را بزنید.")
    return dialog.exec()
