"""Persian RTL manual AEC reviewed editor (all registered system families).

Every click performs a real project operation. Values, dimensions, approval,
material specifications and sources are NEVER invented by UI defaults.
Draft/preview/commit use StructuralProApp and its single SQLite/BOQ gate.
"""
from __future__ import annotations

from copy import deepcopy

from core.takeoff.reviewed_aec import (
    MECHANICAL_SYSTEMS, ELECTRICAL_SYSTEMS, CIVIL_SYSTEMS,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

_COLUMNS = (
    ("line_id", "شناسه ردیف"),
    ("item_code", "کد عملیات"),
    ("description", "شرح"),
    ("quantity", "مقدار مستند"),
    ("unit", "واحد"),
    ("source_ref", "مرجع دیتایل"),
    ("measurement_ref", "مرجع اندازه‌گیری"),
    ("formula", "مبنای محاسبه"),
    ("spec_ref", "مشخصات فنی"),
)


def open_reviewed_aec_editor(service, *, parent=None, project_id="", floor_id=""):
    """Open a modal real editor for manual reviewed AEC component records."""
    dialog = QDialog(parent)
    dialog.setObjectName("ReviewedAECManualEditor")
    dialog.setWindowTitle("متره دستی حرفه‌ای — کلیه سیستم‌های ابنیه")
    dialog.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    dialog.resize(1200, 760)
    outer = QVBoxLayout(dialog)
    form = QFormLayout()
    project = QLineEdit(str(project_id))
    floor = QLineEdit(str(floor_id))
    kind = QComboBox()
    for code, spec in service.aec_system_types().items():
        kind.addItem(spec["title"], code)
    system = QLineEdit()
    identity = QLineEdit()
    identity.setPlaceholderText("شناسه یکتای واقعی منبع برداشت؛ بدون عدد پیش‌فرض")
    form.addRow("شناسه پروژه", project)
    form.addRow("طبقه / ناحیه", floor)
    form.addRow("نوع عملیات", kind)
    form.addRow("شناسه عضو / سیستم", system)
    form.addRow("شناسه منبع مستقل", identity)
    outer.addLayout(form)
    group_box = QGroupBox("دیتایل‌های یک گروه؛ سایر گروه‌ها تا بررسی مسدود هستند")
    group_layout = QVBoxLayout(group_box)
    group_selector = QComboBox()
    group_layout.addWidget(group_selector)
    choice = QComboBox()
    choice.addItem("نیازمند بررسی", "unreviewed")
    choice.addItem("اندازه‌گیری‌شده و تأییدشده", "confirmed")
    choice.addItem("عدم کاربرد با دلیل و سند", "not_applicable")
    group_layout.addWidget(choice)
    controls = QFormLayout()
    approver = QLineEdit()
    approver.setPlaceholderText("نام تأییدکننده واقعی")
    exclusion_reason = QLineEdit()
    exclusion_ref = QLineEdit()
    controls.addRow("تأییدکننده", approver)
    controls.addRow("دلیل عدم کاربرد (در صورت انتخاب)", exclusion_reason)
    controls.addRow("مرجع بررسی عدم کاربرد", exclusion_ref)
    group_layout.addLayout(controls)
    grid = QTableWidget(0, len(_COLUMNS))
    grid.setHorizontalHeaderLabels([label for _, label in _COLUMNS])
    grid.setObjectName("AECReviewedComponentRows")
    grid.setAlternatingRowColors(True)
    group_layout.addWidget(grid)
    row_buttons = QHBoxLayout()
    add_row = QPushButton("افزودن ریزقلم")
    remove_row = QPushButton("حذف ریزقلم انتخاب‌شده")
    store_group = QPushButton("اعمال گروه در پیش‌نویس")
    row_buttons.addWidget(add_row)
    row_buttons.addWidget(remove_row)
    row_buttons.addWidget(store_group)
    group_layout.addLayout(row_buttons)
    outer.addWidget(group_box, 1)
    report = QLabel("همه اجزای ضروری باید با دیتایل تأیید شوند؛ مقدار نامعلوم صفر نیست.")
    report.setWordWrap(True)
    outer.addWidget(report)
    actions = QHBoxLayout()
    load_button = QPushButton("بارگذاری پیش‌نویس")
    save_button = QPushButton("ذخیره نسخه در SQLite")
    preview_button = QPushButton("اعتبارسنجی ریزمتره")
    commit_button = QPushButton("ثبت قطعی در BOQ")
    for button in (load_button, save_button, preview_button, commit_button):
        actions.addWidget(button)
    outer.addLayout(actions)
    roof_button=QPushButton('فرم تخصصی دال، تیرچه، وافل، هالوکور، یوبوت و کوبیاکس')
    outer.addWidget(roof_button)
    def open_specialist_roof():
        from core.takeoff.roof_detail import KINDS
        if kind.currentData() not in KINDS:
            QMessageBox.warning(dialog,'انتخاب سقف','یکی از سیستم‌های سقف دارای قرارداد تخصصی را انتخاب کنید');return
        from app.roof_detail_editor import open_roof_editor
        open_roof_editor(service,parent=dialog,project_id=project.text().strip(),floor_id=floor.text().strip(),kind=kind.currentData())
    roof_button.clicked.connect(open_specialist_roof)
    dialog.roof_button=roof_button
    steel_button=QPushButton('فرم تخصصی سازه فولادی و عرشه فولادی');outer.addWidget(steel_button);dialog.steel_button=steel_button
    def open_specialist_steel():
        if kind.currentData() not in ('steel_frame','steel_deck'):
            QMessageBox.warning(dialog,'انتخاب سیستم','اسکلت فولادی یا سقف عرشه فولادی را انتخاب کنید');return
        from app.steel_detail_editor import open_steel_editor
        open_steel_editor(service,parent=dialog,project_id=project.text().strip(),floor_id=floor.text().strip(),kind=kind.currentData())
    steel_button.clicked.connect(open_specialist_steel)
    architecture_button=QPushButton('فرم تخصصی دیوارچینی، اندود و کف‌سازی');outer.addWidget(architecture_button);dialog.architecture_button=architecture_button
    def open_specialist_architecture():
        if kind.currentData() not in ('block_wall','brick_wall','plaster_finish','floor_finish'):
            QMessageBox.warning(dialog,'انتخاب عملیات','دیوار، اندود یا کف‌سازی را انتخاب کنید');return
        from app.architecture_detail_editor import open_architecture_editor
        open_architecture_editor(service,parent=dialog,project_id=project.text().strip(),floor_id=floor.text().strip(),kind=kind.currentData())
    architecture_button.clicked.connect(open_specialist_architecture)
    state = {"draft": None, "revision": 0, "editing_component": None,
             "project_id": None, "changed": False}

    def context() -> tuple[str, str, str, str]:
        pid, fl, code, sid = (
            project.text().strip(), floor.text().strip(),
            kind.currentData(), system.text().strip(),
        )
        if not pid or not fl or not code or not sid:
            raise ValueError("پروژه، طبقه، نوع سیستم و شناسه عضو باید مشخص شوند")
        if service.open_project(pid) is None:
            raise ValueError("پروژه موردنظر در پایگاه داده وجود ندارد")
        return pid, fl, code, sid

    def show_failure(exc):
        QMessageBox.warning(dialog, "کنترل مهندسی متره", str(exc))

    def ensure_draft():
        pid, fl, code, sid = context()
        draft = state["draft"]
        if draft is None or state["project_id"] != pid or (
            draft["kind"], draft["floor_id"], draft["system_id"],
        ) != (code, fl, sid):
            current = service.get_aec_system(pid, code, fl, sid)
            if current:
                state["draft"], state["revision"] = deepcopy(current["data"]), current["revision"]
            else:
                state["draft"] = service.new_aec_system(code, fl, sid)
                state["revision"] = 0
            state["editing_component"] = None
            state["project_id"] = pid
            state["changed"] = False
        return state["draft"]

    def paint_component():
        d = ensure_draft()
        name = group_selector.currentData()
        if name not in d["components"]:
            return
        part = d["components"][name]
        status = part.get("status", "unreviewed")
        choice.setCurrentIndex(max(0, choice.findData(status)))
        approver.setText(str(part.get("approved_by") or ""))
        exclusion_reason.setText(str(part.get("reason") or ""))
        exclusion_ref.setText(str(part.get("source_ref") or ""))
        grid.setRowCount(0)
        for entry in part.get("items") or ():
            grid.insertRow(grid.rowCount())
            for col, (key, _) in enumerate(_COLUMNS):
                value = entry.get(key, "")
                grid.setItem(grid.rowCount()-1, col, QTableWidgetItem(str(value)))
        state["editing_component"] = name

    def populate_components():
        d = ensure_draft()
        group_selector.blockSignals(True)
        group_selector.clear()
        meta = service.aec_system_types()[d["kind"]]
        for name in meta["components"]:
            label = f"{name} — {'الزامی' if name in meta['essential'] else 'قابل بررسی'}"
            group_selector.addItem(label, name)
        group_selector.blockSignals(False)
        paint_component()

    def capture_component(name=None):
        d = ensure_draft()
        name = name or group_selector.currentData()
        before = deepcopy(d["components"].get(name))
        if name not in d["components"]:
            raise ValueError("گروه عملیات انتخاب نشده است")
        status = choice.currentData()
        reviewer = approver.text().strip()
        if status == "confirmed":
            if not reviewer:
                raise ValueError("تأییدکننده مقدار مستند الزامی است")
            items = []
            for row in range(grid.rowCount()):
                raw = {}
                for col, (key, _) in enumerate(_COLUMNS):
                    cell = grid.item(row, col)
                    raw[key] = cell.text().strip() if cell else ""
                if not all(raw[x] for x in (
                        "line_id", "item_code", "description", "quantity",
                        "unit", "source_ref", "measurement_ref", "formula")):
                    raise ValueError(f"ردیف {row+1}: کد، مقدار، واحد، سند و فرمول ناقص است")
                try:
                    raw["quantity"] = float(raw["quantity"])
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"ردیف {row+1}: مقدار عددی نامعتبر است") from exc
                raw.update({"mode": "measured",
                            "domain": (
                                "mechanical" if d["kind"] in MECHANICAL_SYSTEMS else
                                "electrical" if d["kind"] in ELECTRICAL_SYSTEMS else
                                "civil" if d["kind"] in CIVIL_SYSTEMS else "building"),
                })
                items.append(raw)
            if not items:
                raise ValueError("برای تأیید یک گروه، حداقل یک ریزقلم واقعی لازم است")
            d["components"][name] = {"status": "confirmed", "approved_by": reviewer,
                                      "items": items}
        elif status == "not_applicable":
            if name in service.aec_system_types()[d["kind"]]["essential"]:
                raise ValueError("برای گروه ضروری، عدم کاربرد مجاز نیست")
            reason = exclusion_reason.text().strip()
            ref = exclusion_ref.text().strip()
            if not (reviewer and reason and ref):
                raise ValueError("عدم کاربرد به تأییدکننده، دلیل و مرجع واقعی نیاز دارد")
            d["components"][name] = {
                "status": "not_applicable", "approved_by": reviewer,
                "reason": reason, "source_ref": ref,
            }
        else:
            d["components"][name] = {"status": "unreviewed"}
        state["editing_component"] = name
        if before != d["components"][name]:
            state["changed"] = True
        report.setText(f"گروه «{name}» در پیش‌نویس اعمال شد؛ هنوز ثبت قطعی نشده است.")

    def load():
        try:
            state["draft"] = None
            state["revision"] = 0
            populate_components()
            identity.setText(str(state["draft"].get("source", {}).get("source_id") or ""))
            report.setText("نسخه فعلی بارگذاری شد؛ گروه‌ها را تکمیل و سپس ذخیره کنید.")
        except Exception as exc:
            show_failure(exc)

    def change_component(_index):
        try:
            # Unsubmitted edits must never silently be discarded.
            former = state["editing_component"]
            if former and former != group_selector.currentData():
                try:
                    capture_component(former)
                except Exception:
                    idx = group_selector.findData(former)
                    group_selector.blockSignals(True)
                    group_selector.setCurrentIndex(idx)
                    group_selector.blockSignals(False)
                    raise
            paint_component()
        except Exception as exc:
            show_failure(exc)

    def prepare_save():
        d = ensure_draft()
        src = identity.text().strip()
        if not src:
            raise ValueError("شناسه واقعی منبع برداشت را وارد کنید")
        source = {"mode": "manual", "source_id": src}
        if d.get("source") != source:
            state["changed"] = True
        d["source"] = source
        return d

    def save():
        try:
            capture_component()
            draft = prepare_save()
            pid, *_ = context()
            entry = service.save_aec_system_draft(
                pid, draft, expected_revision=state["revision"])
            state["revision"] = entry["revision"]
            state["changed"] = False
            report.setText(f"پیش‌نویس در SQLite ثبت شد؛ نسخه {entry['revision']}.")
        except Exception as exc:
            show_failure(exc)

    def preview():
        try:
            capture_component()
            d = prepare_save()
            from core.takeoff.engine import TakeoffEngine
            from core.takeoff.reviewed_aec import preview_system
            result = preview_system(d, TakeoffEngine())
            if result["ready"]:
                report.setText(
                    f"بازبینی موفق: {len(result['rows'])} ریزقلم؛ "
                    "برای ثبت قطعی ابتدا نسخه پیش‌نویس را ذخیره کنید.")
            else:
                report.setText(
                    "ثبت قطعی مسدود است:\n" + "\n".join(result["blockers"][:12]))
        except Exception as exc:
            show_failure(exc)

    def commit():
        try:
            pid, fl, code, sid = context()
            capture_component()
            prepare_save()
            if state["changed"]:
                raise ValueError("پیش از ثبت قطعی، همه تغییرات و منبع برداشت را در SQLite ذخیره کنید")
            if state["revision"] < 1:
                raise ValueError("ابتدا پیش‌نویس را در SQLite ذخیره کنید")
            result = service.commit_aec_system(
                pid, code, fl, sid, expected_revision=state["revision"])
            report.setText(f"ثبت قطعی در ریزمتره و BOQ: {result['takeoff_rows']} ردیف.")
        except Exception as exc:
            show_failure(exc)

    add_row.clicked.connect(lambda: grid.insertRow(grid.rowCount()))
    def remove_selected():
        selected = sorted({index.row() for index in grid.selectedIndexes()}, reverse=True)
        for n in selected:
            grid.removeRow(n)
    remove_row.clicked.connect(remove_selected)
    store_group.clicked.connect(lambda: _run(capture_component))
    load_button.clicked.connect(load)
    save_button.clicked.connect(save)
    preview_button.clicked.connect(preview)
    commit_button.clicked.connect(commit)
    group_selector.currentIndexChanged.connect(change_component)
    def _run(f):
        try:
            f()
        except Exception as exc:
            show_failure(exc)
    load()
    return dialog.exec()
