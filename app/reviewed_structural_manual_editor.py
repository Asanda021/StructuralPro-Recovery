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
    QMessageBox, QPushButton, QPlainTextEdit, QTableWidget, QCheckBox, QFileDialog, QScrollArea, QWidget,
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
    outer=QVBoxLayout(dialog);content=QWidget();main=QVBoxLayout(content);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(content);outer.addWidget(scroll)
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
    shape.addItem("نوع هندسه را صریح انتخاب کنید", None)
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
    specialist=QCheckBox('قرارداد تخصصی ستون؛ واحد ابعاد متر و وزن کیلوگرم');main.addWidget(specialist)
    building=QLineEdit();axis=QLineEdit();plan=QLineEdit();drawing_detail=QLineEdit();reason=QLineEdit()
    for w,label in [(building,'شناسه ساختمان'),(axis,'محور ستون'),(plan,'مرجع پلان'),(drawing_detail,'مرجع دیتایل'),(reason,'علت اصلاح نسخه')]:w.setPlaceholderText(label);main.addWidget(w)
    repeat_scope=QComboBox();repeat_scope.addItem('دامنه تعداد ستون را صریح انتخاب کنید',None);repeat_scope.addItem('ستون‌های هم‌تیپ با تکرار صریح','identical_members');main.addWidget(repeat_scope)
    column_scope=QComboBox();column_scope.addItem('دامنه گروه را انتخاب کنید',None);column_scope.addItem('هر ستون','per_member');column_scope.addItem('کل گروه ستون‌ها','total_group');main.addWidget(column_scope)
    ded_scope=QComboBox();ded_scope.addItem('دامنه کسورات را انتخاب کنید',None);ded_scope.addItem('هر ستون','per_member');ded_scope.addItem('کل گروه','total_group');main.addWidget(ded_scope)
    ded_ref=QLineEdit();ded_ref.setPlaceholderText('مرجع کسورات یا نبود تقاطع؛ بدون حدس');main.addWidget(ded_ref)
    advanced=QPushButton('ویرایش ردیفی دیتایل ستون انتخابی');section_button=QPushButton('نواحی مقطع ستون');ded_button=QPushButton('کسورات مستند ستون');review_column=QPushButton('بازبینی نسخه جاری ستون')
    creator=QLineEdit();reviewer=QLineEdit();note=QLineEdit();amend_id=QLineEdit()
    for w,label in [(creator,'سازنده اصلاحیه ستون'),(reviewer,'بازبین مستقل اصلاحیه'),(note,'یادداشت بازبینی'),(amend_id,'شناسه اصلاحیه')]:w.setPlaceholderText(label);main.addWidget(w)
    amend_buttons={k:QPushButton(label) for k,label in [('create','درخواست اصلاح ستون قطعی'),('review','بازبینی مستقل اصلاحیه ستون'),('apply','اعمال اتمیک اصلاحیه ستون')]}
    reports={k:QPushButton('گزارش ستون '+label) for k,label in [('xlsx','Excel'),('pdf','PDF')]}
    for b in [advanced,section_button,ded_button,review_column,*amend_buttons.values(),*reports.values()]:main.addWidget(b)
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
        if selected_shape not in {"rectangular", "circular_column", "reviewed_sections"}:
            raise ValueError("انتخاب صریح نوع هندسه برای عضو الزامی است")
        if selected_shape=="circular_column" and k not in {"column","bored_pile"}:
            raise ValueError("هندسه دایره‌ای فقط برای ستون یا شمع درجا است")
        if selected_shape=="rectangular" and k=="bored_pile":
            raise ValueError("شمع درجا باید قطر و هندسه تأییدشده داشته باشد")
        actual_keys=("count","diameter","height") if selected_shape=="circular_column" else (
            ("count",) if selected_shape=="reviewed_sections" else KINDS[k][3])
        active=specialist.isChecked() and k=='column'
        dimensions=deepcopy(d.get('geometry',{})) if active else {}
        for key in actual_keys:
            raw=numeric[key].text().strip()
            if raw:
                dimensions[key]=(raw if active else int(positive(raw,key,integer=True)) if key=='count' else positive(raw,key))
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
        dimensions["shape"]=selected_shape
        if active:
            d['measurement_policy']='column_specialist_v1';d['building_id']=building.text().strip();d['axis']=axis.text().strip()
            dimensions.update(height=numeric['height'].text().strip(),variable_units={'width':'m','depth':'m','height':'m','count':'عدد'},repeat_scope=repeat_scope.currentData(),intersection_scope=ded_scope.currentData(),intersection_ref=ded_ref.text().strip())
            if 'intersections' not in dimensions:raise ValueError('فهرست کسورات یا فهرست خالی صریح لازم است؛ ویرایش کسورات را باز کنید')
        before=d["geometry"]
        if dimensions!=before:
            state["dirty"]=True
            d["geometry"]=dimensions
        source=source_id.text().strip()
        new_source={"mode":"manual","source_id":source} if source else {}
        if active:
            new_source=deepcopy(d['source']) if d['source'].get('mode') else {'mode':'manual'}
            new_source.update(source_id=source,plan_ref=plan.text().strip(),detail_ref=drawing_detail.text().strip())
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
        active=specialist.isChecked() and d['kind']=='column'
        column_scope.setCurrentIndex(max(0,column_scope.findData(part.get('area_scope') if name=='formwork' else part.get('count_scope'))))
        detail_table.setEnabled(not active)
        keys=_FORM_COLUMNS if name=="formwork" else _REBAR_COLUMNS
        detail_table.setColumnCount(len(keys))
        if active:
            labels={'id':'شناسه','count':'تعداد','nominal_diameter_mm':'قطر میلی‌متر','role':'وجه','gross_area_m2':'سطح ناخالص متر مربع','contact':'تماس واقعی','net_area_m2':'سطح خالص','cut_length_m':'برش متر','unit_weight_kg_m':'وزن واحد','unit_weight_source':'مرجع وزن','source_ref':'دیتایل','approved_by':'بازبین','name':'نام ناحیه','start_m':'شروع متر','end_m':'پایان متر','spacing_m':'گام متر','first_bar_m':'اولین خاموت','last_bar_m':'آخرین خاموت'}
            detail_table.setHorizontalHeaderLabels([labels.get(k,k) for k in keys])
        else:detail_table.setHorizontalHeaderLabels(list(keys))
        _show_table(detail_table, keys, (part.get("surfaces") or []) if name=="formwork"
                    else (part.get("segments") or []))

    def apply_group(name=None):
        d=assure()
        name=name or detail.currentData()
        old=d["formwork"] if name=="formwork" else d["rebars"][name]
        status_name=status.currentData()
        reviewer=group_approver.text().strip()
        ref=group_ref.text().strip()
        active=specialist.isChecked() and d['kind']=='column'
        new={**deepcopy(old),'status':status_name} if active else {'status':status_name}
        if status_name=="confirmed":
            if not reviewer or not ref:
                raise ValueError("گروه تأییدشده به تأییدکننده و مرجع واقعی نیاز دارد")
            keys=_FORM_COLUMNS if name=="formwork" else _REBAR_COLUMNS
            raw=deepcopy(old.get('surfaces' if name=='formwork' else 'segments',[])) if active else _rows(detail_table, keys)
            if not raw:
                raise ValueError("برای گروه تأییدشده جدول دارای حداقل یک ردیف لازم است")
            for line in ([] if active else raw):
                for k in (("net_area_m2",) if name=="formwork" else
                          ("count","cut_length_m","unit_weight_kg_m",
                           "start_m","end_m","spacing_m","first_bar_m","last_bar_m")):
                    if k in line:
                        line[k]=positive(line[k],k,allow_zero=k in
                          {"start_m","first_bar_m"},integer=(k=="count"))
            new.update({"approved_by":reviewer, "source_ref":ref,
                        "surfaces" if name=="formwork" else "segments":raw})
            if active:
                new['area_scope' if name=='formwork' else 'count_scope']=column_scope.currentData();new['area_scope_ref' if name=='formwork' else 'count_scope_ref']=scope_ref.text().strip()
            elif scope.text().strip():
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
            detail.addItem({'longitudinal':'میلگرد طولی','ties':'خاموت','crossties':'سنجاقی','starters':'انتظار و وصله'}.get(name,'آرماتور '+name),name)
        detail.blockSignals(False)
        show_group()

    def reload():
        try:
            state["data"]=None
            d=assure()
            source_id.setText(str(d.get("source",{}).get("source_id") or ""))
            geo=d.get("geometry") or {}
            shape.setCurrentIndex(max(shape.findData(geo.get("shape")),0))
            for key,w in numeric.items():
                value=geo.get(key)
                if value is not None and d.get('measurement_policy')=='column_specialist_v1' and key in ('width','depth','height'):
                    from core.takeoff.formulas import evaluate
                    value=evaluate('value',{'value':value},variable_units={'value':geo.get('variable_units',{}).get(key)},output_unit='m')
                w.setText(str(value) if value is not None else '')
            geometry_ref.setText(str(geo.get("source_ref") or ""))
            geometry_reviewer.setText(str(geo.get("approved_by") or ""))
            section_layout_ref.setText(str(geo.get("section_layout_ref") or ""))
            section_nonoverlap_approver.setText(str(geo.get("nonoverlap_reviewed_by") or ""))
            sections.setPlainText(json.dumps(geo.get("sections",[]),ensure_ascii=False) if geo.get("sections") else "")
            specialist.setChecked(d.get('measurement_policy')=='column_specialist_v1')
            building.setText(d.get('building_id',''));axis.setText(d.get('axis',''));plan.setText(d.get('source',{}).get('plan_ref',''));drawing_detail.setText(d.get('source',{}).get('detail_ref',''));repeat_scope.setCurrentIndex(max(0,repeat_scope.findData(geo.get('repeat_scope'))));ded_scope.setCurrentIndex(max(0,ded_scope.findData(geo.get('intersection_scope'))));ded_ref.setText(geo.get('intersection_ref',''))
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
            entry=service.save_structural_member_draft(pid,d,expected_revision=state["revision"],reason=reason.text().strip() or "ثبت پیش‌نویس")
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

    def edit_column(kind=None):
        try:
            from app.beam_component_editor import BeamComponentEditor
            d=assure()
            if d['kind']!='column' or not specialist.isChecked():raise ValueError('قرارداد تخصصی ستون را انتخاب کنید')
            name=detail.currentData();field='sections' if kind=='sections' else 'intersections' if kind=='intersections' else 'surfaces' if name=='formwork' else 'segments'
            target=d['geometry'] if kind else d['formwork'] if name=='formwork' else d['rebars'][name]
            editor_kind=kind or ('surfaces' if name=='formwork' else 'series')
            extra=[(k,label) for k,label in [('shape_kind','نوع خاموت؛ مستطیلی'),('name','نام ناحیه'),('start_m','شروع متر'),('end_m','پایان متر'),('first_bar_m','اولین خاموت متر'),('last_bar_m','آخرین خاموت متر'),('spacing_m','فاصله واقعی متر')]] if name=='ties' and not kind else []
            child=BeamComponentEditor(editor_kind,target.get(field,[]),dialog,extra_fields=extra);child.setWindowTitle('دیتایل صریح ستون')
            if child.exec()!=QDialog.DialogCode.Accepted:return
            target[field]=child.rows;d.pop('component_review',None);state['dirty']=True
            if not kind:show_group()
        except Exception as exc:error(exc)
    def column_summary(report):
        result=[]
        for row in report['rows']:
            params=row['params']
            if row['unit']=='m3':result.append('بتن ناخالص: '+str(params.get('gross_m3','نامشخص'))+'؛ کسورات: '+str(params.get('deductions_m3','نامشخص'))+'؛ بتن خالص: '+str(row['quantity'])+' متر مکعب')
            elif row['unit']=='m2':result.append('قالب ناخالص: '+str(params.get('gross_area_m2','نامشخص'))+'؛ قالب خالص: '+str(row['quantity'])+' متر مربع')
            else:result.append(row['description']+': '+str(row['quantity'])+' کیلوگرم')
        return '؛ '.join(result)

    def review_current_column():
        try:
            from core.takeoff.manual_formula_amendments import digest
            apply_group();d=physical_geometry();d.pop('component_review',None);r=preview_member(d,service.takeoff)
            if not r['ready']:raise ValueError('؛ '.join(r['blockers']))
            actor=geometry_reviewer.text().strip()
            if not actor:raise ValueError('بازبین لازم است')
            d['component_review']={'digest':digest(d),'base_revision':state['revision'],'reviewer':actor};message.setText('نسخه جاری بازبینی شد؛ '+column_summary(r))
        except Exception as exc:error(exc)
    def amend_column(action):
        try:
            pid,fl,k,mid=context()
            if k!='column':raise ValueError('این گردش فقط ستون است')
            if action=='create':
                apply_group();d=physical_geometry();a=service.create_column_amendment(pid,fl,mid,d,expected_revision=state['revision'],created_by=creator.text(),reason=reason.text());amend_id.setText(a['id']);message.setText('پیشنهاد ثبت شد؛ دلتا: '+str(a['delta']))
            elif action=='review':service.review_beam_amendment(pid,amend_id.text(),expected_revision=1,reviewer=reviewer.text(),note=note.text());message.setText('بازبینی مستقل انجام شد؛ هنوز اعمال نشده')
            else:service.apply_beam_amendment(pid,amend_id.text(),expected_revision=1);reload();message.setText('اصلاحیه اعمال شد؛ اصل ستون ثابت است')
        except Exception as exc:error(exc)
    def export_column(fmt):
        try:
            pid,fl,k,mid=context()
            if k!='column':raise ValueError('گزارش فقط برای ستون')
            path,_=QFileDialog.getSaveFileName(dialog,'گزارش ستون','column.'+fmt,'گزارش (*.'+fmt+')')
            if path:service.export_column_detail_report(pid,fl,mid,path,format=fmt);message.setText('گزارش ستون ذخیره شد')
        except Exception as exc:error(exc)
    advanced.clicked.connect(lambda:edit_column());section_button.clicked.connect(lambda:edit_column('sections'));ded_button.clicked.connect(lambda:edit_column('intersections'));review_column.clicked.connect(review_current_column)
    for action,button in amend_buttons.items():button.clicked.connect(lambda _=False,a=action:amend_column(a))
    for fmt,button in reports.items():button.clicked.connect(lambda _=False,f=fmt:export_column(f))
    dialog.column_controls={'scroll':scroll,'project':project,'floor':floor,'kind':kinds,'id':ident,'load':load,'save':save,'preview':preview,'commit':commit,'numeric':numeric,'specialist':specialist,'building':building,'axis':axis,'plan':plan,'detail_ref':drawing_detail,'repeat_scope':repeat_scope,'scope':column_scope,'ded_scope':ded_scope,'ded_ref':ded_ref,'advanced':advanced,'sections':section_button,'deductions':ded_button,'review':review_column,'group':detail,'status':status,'geometry_reviewer':geometry_reviewer,'reason':reason,'creator':creator,'reviewer':reviewer,'note':note,'amend_id':amend_id,'amend':amend_buttons,'reports':reports,'state':state,'message':message}
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
