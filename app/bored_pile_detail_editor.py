"""Persian RTL bored-pile evidence editor; draft-only, no financial actions."""
from __future__ import annotations

import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)
from app.bored_pile_draft_controller import PileDraftController
from app.shear_wall_detail_editor import ExactCellDelegate


def open_bored_pile_editor(service, *, parent=None, project_id='', floor_id='', group_id=''):
    """Open a fully wired *draft* workflow. No BOQ/review/commit button exists."""
    controller = PileDraftController(service, project_id)
    dialog = QDialog(parent)
    dialog.setObjectName('BoredPileDraftEditor')
    dialog.setWindowTitle('متره تخصصی شمع بتنی درجا — پیش‌نویس مستند')
    dialog.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    dialog.resize(1160, 790)
    root = QVBoxLayout(dialog)
    tabs = QTabWidget(dialog)
    root.addWidget(tabs, 1)
    message = QLabel('ثبت مالی شمع تا تطبیق مالکیت مشترک مسدود است.')
    message.setObjectName('pile_message')
    message.setWordWrap(True)
    root.addWidget(message)
    controls = {'dialog': dialog, 'tabs': tabs, 'message': message, 'controller': controller}

    def page(title):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        view = QWidget()
        layout = QVBoxLayout(view)
        scroll.setWidget(view)
        tabs.addTab(scroll, title)
        return layout

    def field(form, name, label, value='', *, readonly=False):
        w = QLineEdit(str(value))
        w.setObjectName('pile_' + name)
        if readonly:
            w.setReadOnly(True)
        form.addRow(label, w)
        controls[name] = w
        return w

    identity = page('هویت و مدارک')
    form = QFormLayout()
    identity.addLayout(form)
    field(form, 'project', 'شناسه پروژه', project_id, readonly=True)
    field(form, 'floor', 'طبقه', floor_id)
    field(form, 'group', 'گروه شمع', group_id)
    mode = QComboBox()
    for title, code in [('نوع منبع را انتخاب کنید', None),
                        ('متره دستی مستند', 'manual'),
                        ('برداشت مستند از نقشه', 'drawing')]:
        mode.addItem(title, code)
    form.addRow('نوع منبع', mode)
    controls['source_mode'] = mode
    for name, label in [('source_id','شناسه منبع'), ('approved_by','تأییدکننده منبع'),
                        ('measurement_ref','مرجع برداشت')]:
        field(form, name, label)
    extra = QPlainTextEdit()
    extra.setMaximumHeight(80)
    extra.setPlaceholderText('برای نقشه: JSON واقعی شامل sha256، page، drawing_path و selected_region')
    form.addRow('مشخصات نقشه', extra)
    controls['source_extra'] = extra
    for name, label in [('input_path','مسیر دیتایل'), ('input_sha256','SHA-256 دیتایل'),
                        ('ownership_path','مسیر مالکیت'), ('ownership_sha256','SHA-256 مالکیت'),
                        ('joint_path','مسیر سند مشترک'), ('joint_sha256','SHA-256 سند مشترک')]:
        field(form, name, label, readonly=True)
    for name, label in [('joint_reference','مرجع اتصال مشترک'),
                        ('ownership_reference','مرجع مالکیت'),
                        ('reviewer','بازبین مقدماتی مستقل'),
                        ('ownership_claim','مرجع کنترل مقدماتی مالکیت')]:
        field(form, name, label)
    field(form, 'amendment_reason', 'علت مستند اصلاحیه پیش‌نویس')
    amendment_note = QLabel('اصلاحیه فقط برای نسخه ذخیره‌شده با همان شمع‌های فیزیکی است؛ تمام مدارک مالکیت و اتصال مشترک قبلی باطل خواهند شد.')
    amendment_note.setWordWrap(True)
    identity.addWidget(amendment_note)

    geometry = page('هندسه و آرماتور')
    note = QLabel('هیچ قطر، تراز، تعداد، طول یا وزن واحدی تخمین زده نمی‌شود؛ مقادیر از فایل مستند خوانده می‌شوند.')
    note.setWordWrap(True)
    geometry.addWidget(note)
    piles = QTableWidget(0, 5)
    piles.setHorizontalHeaderLabels(['شناسه شمع','هویت فیزیکی','قطر (متر)','تراز بالا','تراز پایین'])
    piles.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    piles.setItemDelegate(ExactCellDelegate(('id','physical_part_id','diameter_m','top_elevation_m','bottom_elevation_m'), piles))
    geometry.addWidget(piles)
    rebars = QTableWidget(0, 5)
    rebars.setHorizontalHeaderLabels(['گروه','سری','هویت فیزیکی','تعداد','طول برش'])
    rebars.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    rebars.setItemDelegate(ExactCellDelegate(('kind','id','physical_bar_set_id','count','cut_length_m'), rebars))
    geometry.addWidget(rebars)
    controls['piles'], controls['rebars'] = piles, rebars

    audit_tab = page('پیش‌نمایش و تاریخچه')
    report = QPlainTextEdit()
    report.setObjectName('pile_audit_report')
    report.setReadOnly(True)
    audit_tab.addWidget(report)
    history = QTableWidget(0, 3)
    history.setHorizontalHeaderLabels(['نسخه','علت','زمان'])
    history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    audit_tab.addWidget(history)
    controls['report'], controls['history'] = report, history

    def run(fn):
        try:
            fn()
        except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
            message.setText('خطا: ' + str(exc))
            QMessageBox.warning(dialog, 'کنترل دیتایل شمع', str(exc))

    def button(key, title, fn):
        w = QPushButton(title)
        w.setObjectName('pile_' + key)
        w.clicked.connect(lambda _checked=False: run(fn))
        controls[key] = w
        return w

    def show_rows(table, rows):
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                table.setItem(i, j, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()

    def fill():
        d = controller.data or {}
        dt = d.get('pile_detail', {})
        data = dt.get('input', {})
        controls['floor'].setText(d.get('floor_id',''))
        controls['group'].setText(d.get('member_id',''))
        source = d.get('source', {})
        index = mode.findData(source.get('mode'))
        mode.setCurrentIndex(index if index >= 0 else 0)
        for key in ('source_id','approved_by','measurement_ref'):
            controls[key].setText(source.get(key,''))
        extra_fields = {k:v for k,v in source.items()
                        if k not in ('mode','source_id','approved_by','measurement_ref')}
        extra.setPlainText(json.dumps(extra_fields,ensure_ascii=False) if extra_fields else '')
        for prefix in ('input','ownership','joint'):
            document = dt.get(prefix + '_document', {})
            for key in ('path','sha256'):
                controls[prefix + '_' + key].setText(document.get(key,''))
        controls['ownership_reference'].setText(dt.get('ownership_document',{}).get('reference',''))
        controls['joint_reference'].setText(dt.get('joint_document',{}).get('reference',''))
        controls['reviewer'].setText(dt.get('preflight',{}).get('reviewer',''))
        controls['ownership_claim'].setText(dt.get('preflight',{}).get('ownership_reference_claim',''))
        members = data.get('piles', [])
        show_rows(piles, [(p.get('id',''),p.get('physical_id',''),p.get('diameter_m',''),
                           p.get('top_elevation_m',''),p.get('bottom_elevation_m',''))
                          for p in members])
        bar_rows = []
        for p in members:
            for kind, group in p.get('rebars',{}).items():
                for series in group.get('series',[]):
                    bar_rows.append(({'longitudinal':'میلگرد طولی','spiral_ties':'مارپیچ یا خاموت','crossties':'سنجاقی','starters':'میلگرد انتظار'}.get(kind,kind),series.get('id',''),series.get('physical_id',''),
                                     series.get('count',''),series.get('cut_length_m','')))
        show_rows(rebars, bar_rows)
        message.setText('نسخه پیش‌نویس: ' + str(controller.revision) + '؛ ثبت مالی مسدود است.')

    def create():
        controller.new(controls['floor'].text(),controls['group'].text())
        fill()
        report.clear()

    def load():
        controller.load(controls['floor'].text(),controls['group'].text())
        fill()
        report.clear()

    def source():
        kind = mode.currentData()
        if kind is None:
            raise ValueError('نوع منبع را صریحاً انتخاب کنید')
        src = {k:controls[k].text() for k in ('source_id','approved_by','measurement_ref')}
        src['mode'] = kind
        raw = extra.toPlainText().strip()
        if kind == 'drawing':
            if not raw:
                raise ValueError('نقشه به مشخصات منبع مستند نیاز دارد')
            extra_fields = json.loads(raw)
            if not isinstance(extra_fields,dict) or any(k in src for k in extra_fields):
                raise ValueError('ساختار و هویت منبع نقشه نامعتبر است')
            src.update(extra_fields)
        elif raw:
            raise ValueError('در حالت دستی فیلد نقشه نباید وارد شود')
        return src

    def check_context(*, include_source=True):
        data = controller.data
        if data is None:
            raise ValueError('ابتدا گروه شمع را ایجاد یا بازگشایی کنید')
        if (controls['floor'].text(), controls['group'].text()) != (data['floor_id'], data['member_id']):
            raise ValueError('هویت نمایشی با گروه بارگذاری‌شده برابر نیست؛ گروه را بازگشایی یا گروه جدید ایجاد کنید')
        if include_source and source() != data.get('source', {}):
            raise ValueError('منبع نمایشی تغییر کرده است؛ دیتایل مستند را دوباره بارگذاری کنید')

    def attach_input():
        path, _ = QFileDialog.getOpenFileName(dialog,'دیتایل واقعی گروه شمع','','JSON (*.json)')
        if not path:
            return
        check_context(include_source=False)
        controller.attach_input(path,source=source())
        fill()
        message.setText('دیتایل مستند بارگذاری شد؛ مالکیت قبلی باطل شد. هنوز ذخیره نشده است.')

    def set_reviewer():
        controller.set_preflight(reviewer=controls['reviewer'].text(),
                                 ownership_reference=controls['ownership_claim'].text())

    def attach_owner():
        path, _ = QFileDialog.getOpenFileName(dialog,'سند مستقل مالکیت','','JSON (*.json)')
        if not path:
            return
        check_context()
        # Unlike a blind fill(), preserve any entered review information.
        if controls['reviewer'].text().strip() or controls['ownership_claim'].text().strip():
            set_reviewer()
        assessment = controller.attach_ownership(path,reference=controls['ownership_reference'].text())
        fill()
        report.setPlainText(json.dumps({'status':assessment['status'],
            'blockers':assessment['blockers'],
            'excluded_operations':assessment['excluded_operations']},
            ensure_ascii=False,indent=2))
        message.setText('ممیزی مقدماتی ثبت شد؛ مالکیت مشترک و ثبت مالی هنوز مسدودند.')


    def attach_joint():
        path, _ = QFileDialog.getOpenFileName(dialog,'سند اتصال شمع، کلاهک و ستون','','JSON (*.json)')
        if not path:
            return
        check_context()
        if controls['reviewer'].text().strip() or controls['ownership_claim'].text().strip():
            set_reviewer()
        result = controller.attach_joint(path,reference=controls['joint_reference'].text())
        fill()
        report.setPlainText(json.dumps({'status':result['status'],
            'matched_interfaces':result['matched_interfaces'],
            'matched_starter_pieces':result['matched_starter_pieces'],
            'blockers':result['blockers']},ensure_ascii=False,indent=2))
        message.setText('اتصال مشترک پیش‌ممیزی شد؛ هیچ مجوز پرداخت صادر نشده است.')

    def audit_spatial():
        # A cancelled or rejected attempt must not leave a previous favourable
        # preview visible as though it belonged to the current evidence.
        report.clear()
        check_context()
        data = controller.data
        if data is None or (controls['reviewer'].text() != data['pile_detail']['preflight'].get('reviewer','')
                            or controls['ownership_claim'].text() != data['pile_detail']['preflight'].get('ownership_reference_claim','')):
            raise ValueError('بازبین نمایش‌داده‌شده با نسخه ذخیره‌شده برابر نیست')
        path, _ = QFileDialog.getOpenFileName(
            dialog, 'سند مستقل سه‌بعدی شمع و عضو مرتبط', '', 'JSON (*.json)')
        if not path:
            return
        result = controller.audit_spatial(path)
        report.setPlainText(json.dumps({
            'status':result['status'],
            'counterpart_geometry_record_bound':result.get('counterpart_geometry_record_bound',False),
            'unbound_counterpart_count':result.get('unbound_counterpart_count'),
            'matched_interfaces':result['matched_interfaces'],
            'commit_allowed':result['commit_allowed'],
            'ready_for_boq':result['ready_for_boq'],
            'blockers':result['blockers'],
        }, ensure_ascii=False, indent=2))
        message.setText('ممیزی سه‌بعدی فقط‌خواندنی انجام شد؛ نتیجه ذخیره نشده و ثبت مالی مسدود است.')
        tabs.setCurrentIndex(2)

    def amend_input():
        check_context()
        current = controller.data['pile_detail']['preflight']
        if (controls['reviewer'].text() != current.get('reviewer','') or
                controls['ownership_claim'].text() != current.get('ownership_reference_claim','')):
            raise ValueError('تغییرات بازبین را پیش از اصلاحیه ذخیره کنید')
        reason = controls['amendment_reason'].text()
        # The controller also rechecks reason, old/new evidence digests and
        # saved revision. No record is mutated if the file picker is cancelled.
        path, _ = QFileDialog.getOpenFileName(
            dialog,'نسخه جدید دیتایل مستند شمع','','JSON (*.json)')
        if not path:
            return
        controller.amend_input(path, reason=reason)
        fill()
        controls['amendment_reason'].clear()
        message.setText('اصلاحیه پیش‌نویس در SQLite و تاریخچه ذخیره شد؛ مالکیت و اتصال مشترک قبلی باطل هستند. ثبت مالی مسدود است.')
        tabs.setCurrentIndex(2)

    def save():
        check_context()
        set_reviewer()
        controller.save()
        fill()
        message.setText('پیش‌نویس در SQLite ذخیره شد؛ نسخه ' + str(controller.revision))

    def preview():
        check_context()
        set_reviewer()
        result = controller.preview()
        names = ('engineering_ready','ready','commit_allowed','totals_exact',
                 'ownership_audit','joint_audit','blockers')
        report.setPlainText(json.dumps({k:result.get(k) for k in names},ensure_ascii=False,indent=2))
        message.setText('پیش‌نمایش انجام شد؛ گیت مالی همچنان بسته است.' if result.get('engineering_ready') else 'پیش‌نمایش نامعتبر: ' + '؛ '.join(result.get('blockers', [])))
        tabs.setCurrentIndex(2)

    def refresh_history():
        check_context(include_source=False)
        from core.takeoff.reviewed_structural import _key
        data = controller.data
        if data is None:
            raise ValueError('ابتدا گروه شمع را بازگشایی کنید')
        key = _key('bored_pile',data['floor_id'],data['member_id'])
        project = service.open_project(controller.project_id)
        rows = [(record.get('revision',''),record.get('reason',''),record.get('at',''))
                for record in project.get('structural_member_history',[])
                if record.get('member_key') == key]
        show_rows(history, rows)
        message.setText('تاریخچه ذخیره‌شده بازخوانی شد.')
        tabs.setCurrentIndex(2)

    for entries in (
        (('new','گروه جدید',create),('load','بازگشایی از SQLite',load),
         ('input','خواندن دیتایل',attach_input),('owner','خواندن مالکیت',attach_owner),
         ('joint','خواندن اتصال مشترک',attach_joint),
          ('spatial','پیش‌ممیزی سه‌بعدی',audit_spatial)),
        (('save','ذخیره نسخه‌دار',save),('amend','اصلاحیه مستند پیش‌نویس',amend_input),('preview','پیش‌نمایش',preview),
         ('history_refresh','بازخوانی تاریخچه',refresh_history)),
    ):
        bar = QHBoxLayout()
        root.addLayout(bar)
        for key,title,fn in entries:
            bar.addWidget(button(key,title,fn))
    close = QPushButton('بستن')
    close.clicked.connect(dialog.reject)
    root.addWidget(close)
    controls['close'] = close
    dialog.pile_controls = controls
    if group_id.strip() and floor_id.strip():
        try:
            load()
        except ValueError as exc:
            message.setText('بازگشایی مسدود: ' + str(exc))
    return dialog.exec()
