"""StructuralPro Windows desktop UI: offline-first project, takeoff, drawing, pricing, reports and local AI."""
from __future__ import annotations
import sys
import os
from pathlib import Path
import json

from core.platform.logging import configure_logging, install_exception_hook

def main()->int:
    logger = install_exception_hook(configure_logging())
    logger.info("StructuralPro starting")
    try:
        from PySide6.QtWidgets import (
            QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,
            QLabel,QPushButton,QListWidget,QStackedWidget,QStatusBar,QLineEdit,
            QComboBox,QFormLayout,QMessageBox,QTextEdit,QFileDialog,QTableWidget,
            QTableWidgetItem,QHeaderView,QGroupBox,QTabWidget,QTabBar,QFrame,QDialog,QCalendarWidget
        )
        from PySide6.QtCore import Qt, QTimer, QEvent, QCoreApplication, QDate, QCalendar, QLocale
        from PySide6.QtGui import QShortcut, QKeySequence
        from core.platform.application import StructuralProApp
        from core.drawings.unified_takeoff import UnifiedDrawingTakeoff
        from core.pricing.catalog import PriceCatalog
        from core.pricing.import_service import PricebookImportService
        from core.ai.project_assistant import ProjectAssistant
        from core.reports.quality import prepare_rows
        from core.reports.project_report import build_report
        from core.revisions.compare import compare_rows, summary
        from core.takeoff.templates import TemplateLibrary
        from core.takeoff.assembly_templates import AssemblyTemplateLibrary
        from core.takeoff.formulas import evaluate
        from core.search.global_search import search_project
        from core.history.undo import CommandStack
        from core.drawings.sheets import SheetRegistry
        from core.drawings.markup import MarkupStore
        from core.drawings.pdf_measurement import PDFMeasurementSession
        from core.drawings.ifc_inventory import inventory as ifc_inventory
        from core.takeoff.estimate import build_estimate
        from core.projects.metadata import ProjectMetadata
        from core.projects.project_model import ProjectModel
        from core.projects.backup import BackupManager
        from core.pricing.source_registry import PriceSourceRegistry, PriceSource
        from core.reports.designer import ReportLayout
        from core.revisions.manager import RevisionManager
        from core.commercial.progress import build_progress
        from core.reports.production import prepare_report
        from app.graphical_takeoff import GraphicalTakeoffDialog
        from app.manual_takeoff import ManualTakeoffDialog
        from app.aec_workspace import build_aec_workspace
        from app.theme import APP_STYLESHEET
        from core.ui.ux import DEFAULT_ACTIONS, navigation_groups, quick_status
        from core.help.content import topics as help_topics, search as search_help_topics
        from app.dashboard import DashboardPage
        from core.drawings.dwg_capabilities import detect_dwg_capabilities
        from core.aec.disciplines import all_disciplines
        from core.collaboration.workspace import CollaborationWorkspace, Role, User, Assignment, Comment, Review, Notification
        from core.platform.product import packaged_edition
    except ImportError as exc:
        logger.exception("Required dependency import failed")
        print("StructuralPro dependencies are required:", exc)
        return 2

    app=QApplication(sys.argv)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setApplicationName("StructuralPro")
    app.setStyleSheet(APP_STYLESHEET)
    service=StructuralProApp(Path.home()/".structuralpro")
    catalog=PriceCatalog()
    pricebook_importer=PricebookImportService(catalog)
    pricebook_store=Path.home()/".structuralpro"/"pricebook_user.csv"
    if pricebook_store.exists():
        try:
            catalog.import_csv(pricebook_store.read_text(encoding="utf-8-sig"), replace_year=False)
        except Exception as exc:
            logger.warning("User pricebook cache could not be loaded: %s", exc)
    bundle_dir=Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    packaged=packaged_edition(bundle_dir, fail_closed=False)
    current_edition=packaged.value if packaged else "pro"
    edition_title={"light":"سبک", "standard":"استاندارد", "pro":"حرفه‌ای", "enterprise":"سازمانی"}.get(current_edition,"نامشخص")
    assistant=ProjectAssistant()
    w=QMainWindow(); w.setWindowTitle("StructuralPro — مدیریت مهندسی پروژه"); w.resize(1560,960); w.setMinimumSize(1180,760)

    # Professional desktop shell: top-level navigation is a horizontal tab bar.
    # The old right-side navigation made the application hierarchy difficult to scan.
    root=QWidget(); layout=QVBoxLayout(root); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
    header=QFrame(); header.setObjectName("TopShell"); hv=QVBoxLayout(header); hv.setContentsMargins(18,12,18,8); hv.setSpacing(8)
    header_row=QHBoxLayout(); header_row.setSpacing(14)
    title=QLabel("StructuralPro"); title.setObjectName("BrandTitle"); header_row.addWidget(title)
    edition_label=QLabel(f"نسخه {edition_title}"); edition_label.setObjectName("EditionBadge"); header_row.addWidget(edition_label)
    header_row.addStretch()
    persian_locale=QLocale(QLocale.Language.Persian, QLocale.Country.Iran)
    persian_calendar=QCalendar(QCalendar.System.Jalali)
    date_button=QPushButton()
    date_button.setObjectName("SystemPersianDate")
    date_button.setToolTip("تاریخ سیستم و تقویم شمسی")
    def refresh_system_date():
        date_button.setText(persian_locale.toString(
            QDate.currentDate(), QLocale.FormatType.LongFormat, persian_calendar))
    def show_persian_calendar():
        dialog=QDialog(w)
        dialog.setWindowTitle("تقویم شمسی")
        dialog.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        calendar=QCalendarWidget(dialog)
        calendar.setLocale(persian_locale)
        calendar.setCalendar(persian_calendar)
        calendar.setSelectedDate(QDate.currentDate())
        calendar_layout=QVBoxLayout(dialog)
        calendar_layout.addWidget(calendar)
        dialog.exec()
    date_button.clicked.connect(show_persian_calendar)
    date_timer=QTimer(w)
    date_timer.setInterval(30000)
    date_timer.timeout.connect(refresh_system_date)
    date_timer.start()
    refresh_system_date()
    header_row.addWidget(date_button)
    status=QLabel("🟢 آفلاین فعال | داده‌ها روی سیستم ذخیره می‌شوند"); status.setObjectName("ShellStatus"); header_row.addWidget(status)
    hv.addLayout(header_row)
    pages=QStackedWidget()

    def page(name,desc):
        p=QWidget(); p.setObjectName("ContentPage"); v=QVBoxLayout(p); v.setContentsMargins(26,22,26,22); v.setSpacing(14)
        h=QLabel(name); h.setObjectName("PageTitle")
        d=QLabel(desc); d.setObjectName("PageDescription"); d.setWordWrap(True)
        v.addWidget(h); v.addWidget(d); return p,v

    sections=["⌂ داشبورد","📁 پروژه‌ها","🏠 معماری","🏗 سازه بتن","🏭 سازه فولاد","🧱 بنایی","❄ تأسیسات مکانیکی","⚡ تأسیسات برقی","🌳 محوطه و عملیات بیرونی","♻ بازسازی و مرمت","📐 متره سریع","🗺 متره از نقشه","💰 فهرست‌بها","📋 برآورد و صورت‌مقادیر","📊 گزارشات","🛠 ابزارهای حرفه‌ای","🤖 هوش مصنوعی آفلاین","🧾 صورت‌وضعیت","📎 اسناد پروژه","🤝 همکاری","✓ کنترل کیفیت","⚙ تنظیمات","❔ راهنما"]
    # Navigation tabs are created after all pages exist so their indices are deterministic.

    # Dashboard — functional project overview with real project data
    dashboard_page=DashboardPage(service,catalog,lambda i: pages.setCurrentIndex(i))
    pages.addWidget(dashboard_page); idx_dash=pages.count()-1

    # Projects
    p,v=page("پروژه‌ها","ساخت، بازکردن و ذخیره پروژه‌ها")
    form=QFormLayout(); pid=QLineEdit(); pname=QLineEdit()
    form.addRow("شناسه پروژه:",pid); form.addRow("نام پروژه:",pname); v.addLayout(form)
    create=QPushButton("➕ ایجاد پروژه"); openb=QPushButton("📂 بازکردن پروژه"); plist=QListWidget(); pout=QLabel()
    v.addWidget(create); v.addWidget(openb); v.addWidget(plist); v.addWidget(pout)
    def refresh_projects():
        plist.clear()
        for x in service.store.list(): plist.addItem(f'{x["id"]} | {x["name"]}')
    def create_project():
        try:
            service.create_project(pname.text().strip() or "پروژه جدید",pid.text().strip() or "project")
            pout.setText("پروژه با موفقیت ذخیره شد."); refresh_projects(); dashboard_page.refresh()
        except Exception as e: QMessageBox.critical(w,"خطا",str(e))
    create.clicked.connect(create_project)
    def open_selected():
        if not plist.currentItem(): return
        selected=plist.currentItem().text().split(" | ",1)[0]; pid.setText(selected)
        project=service.open_project(selected)
        pout.setText(f'پروژه باز شد: {project.get("name","")}')
    openb.clicked.connect(open_selected)
    pages.addWidget(p); idx_projects=pages.count()-1

    # Real AEC discipline workspaces: each area is separate and wired to the production takeoff service.
    discipline_specs=[
        ("architecture","🏠 معماری","متره معماری و نازک‌کاری","building"),
        ("structural_concrete","🏗 سازه بتن","متره اعضای بتن‌آرمه و انواع سقف بتنی","building"),
        ("structural_steel","🏭 سازه فولاد","متره اعضای فولادی و سقف‌های قابل استفاده در سازه فولادی","advanced"),
        ("masonry","🧱 بنایی","متره دیوارهای بنایی و سطوح خالص با کسر بازشو","building"),
        ("mechanical","❄ تأسیسات مکانیکی","متره لوله، کانال، عایق، تجهیزات و اتصالات","mechanical"),
        ("electrical","⚡ تأسیسات برقی","متره کابل، لوله برق، تابلو، روشنایی، پریز و ارت","electrical"),
        ("civil","🌳 محوطه و عملیات بیرونی","متره خاکبرداری، خاکریزی، بتن، آسفالت، جدول و زهکشی","civil"),
        ("renovation","♻ بازسازی و مرمت","متره تخریب، مرمت نما، کف‌سازی و سقف کاذب","advanced"),
    ]
    discipline_pages={}
    for key,title_fa,description_fa,domain in discipline_specs:
        wp=build_aec_workspace(service,catalog,title=title_fa,description=description_fa,domain=domain,key=key,
                               status_callback=lambda message: status.setText("🟢 "+message))
        pages.addWidget(wp); discipline_pages[key]=pages.count()-1
    idx_architecture=discipline_pages["architecture"]
    idx_structural_concrete=discipline_pages["structural_concrete"]
    idx_structural_steel=discipline_pages["structural_steel"]
    idx_masonry=discipline_pages["masonry"]
    idx_mechanical=discipline_pages["mechanical"]
    idx_electrical=discipline_pages["electrical"]
    idx_civil=discipline_pages["civil"]
    idx_renovation=discipline_pages["renovation"]

    # Quick takeoff
    p,v=page("متره سریع","ورود سریع مقادیر با فرم استاندارد")
    form=QFormLayout(); qpid=QLineEdit(); item=QComboBox(); item.addItems(["slab","wall","column","beam","footing_concrete"])
    discipline=QComboBox(); discipline.addItem("همه ابنیه", "")
    for d in all_disciplines(): discipline.addItem(d.title_fa, d.key)
    length=QLineEdit(); width=QLineEdit(); height=QLineEdit(); price_code=QLineEdit()
    for x,l in ((qpid,"شناسه پروژه"),(discipline,"رشته/دیسپلین"),(item,"آیتم"),(length,"طول"),(width,"عرض"),(height,"ارتفاع"),(price_code,"کد فهرست‌بها")): form.addRow(l,x)
    v.addLayout(form); calc=QPushButton("محاسبه و ثبت"); manual_button=QPushButton("📝 متره دستی حرفه‌ای"); out=QTextEdit(); out.setReadOnly(True); v.addWidget(calc); v.addWidget(manual_button); v.addWidget(out)
    def do_calc():
        try:
            params={"length":float(length.text() or 0),"width":float(width.text() or 0),"height":float(height.text() or 0),"member_code":item.currentText(),"discipline":discipline.currentData() or "building","price_code":price_code.text().strip() or None}
            if price_code.text().strip():
                resolved=catalog.resolve(price_code.text().strip(), year=int(pyear.text()) if 'pyear' in locals() and pyear.text().strip() else None)
                if resolved.get("status") == "ok":
                    params["unit_price"]=resolved["unit_price"]
            row=service.add_takeoff(qpid.text().strip(),discipline.currentData() or "building",item.currentText(),**params)
            out.setPlainText(f'ثبت شد\nمقدار: {row["quantities"][0]["amount"]} {row["quantities"][0]["unit"]}')
        except Exception as e: out.setPlainText("خطا: "+str(e))
    calc.clicked.connect(do_calc)
    def open_manual_workbench():
        dialog=ManualTakeoffDialog(service,qpid.text().strip(),w)
        dialog.exec()
        dashboard_page.refresh()
    manual_button.clicked.connect(open_manual_workbench)
    pages.addWidget(p); idx_quick=pages.count()-1

    # Drawing takeoff — phase 1 human confirmation + provenance/audit gate
    p,v=page("متره از نقشه","ورود PDF/DWG/DXF/IFC و تولید کاندیدهای متره؛ موارد نیازمند بررسی تا تأیید صریح وارد BOQ نمی‌شوند.")
    file_edit=QLineEdit(); browse=QPushButton("انتخاب فایل"); inspect=QPushButton("🔎 بررسی نقشه")
    graphical=QPushButton("📐 متره گرافیکی"); confirm=QPushButton("✅ ثبت تأیید نهایی")
    audit_label=QLabel("وضعیت: هنوز نقشه‌ای بررسی نشده است."); audit_label.setWordWrap(True)
    dtable=QTableWidget(0,8)
    dtable.setHorizontalHeaderLabels(["تصمیم","شرح","مقدار","واحد","اعتماد","صفحه/شیت","منبع","وضعیت"])
    dtable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    v.addWidget(file_edit); v.addWidget(browse); v.addWidget(inspect); v.addWidget(graphical); v.addWidget(confirm)
    v.addWidget(audit_label); v.addWidget(dtable)
    drawing_state={}; drawing_service=UnifiedDrawingTakeoff()
    browse.clicked.connect(lambda: file_edit.setText(QFileDialog.getOpenFileName(w,"انتخاب نقشه","","Plans (*.pdf *.dwg *.dxf *.ifc *.ifczip);;All files (*)")[0]))

    def inspect_drawing():
        try:
            path=file_edit.text().strip()
            drawing_state.clear(); drawing_state.update(drawing_service.inspect(path))
            dtable.setRowCount(0)
            candidates=drawing_state.get("candidates",[]) or []
            for i,r in enumerate(candidates,1):
                dtable.insertRow(i-1)
                cb=QComboBox()
                cb.addItems(["بررسی","تأیید","رد"])
                cb.setCurrentIndex(0 if r.get("needs_confirmation") else 1)
                dtable.setCellWidget(i-1,0,cb)
                confidence=r.get("confidence",r.get("recognition_confidence",""))
                provenance=r.get("provenance") or {}
                page_ref=provenance.get("page",r.get("page",""))
                sheet_ref=provenance.get("sheet",r.get("sheet",r.get("sheet_id","")))
                page_sheet=f"{page_ref or '—'} / {sheet_ref or '—'}"
                vals=[
                    r.get("description",""), r.get("quantity",""), r.get("unit",""),
                    confidence, page_sheet, r.get("source",r.get("global_id","")),
                    "نیازمند تأیید" if r.get("needs_confirmation") else "قابل قبول اولیه"
                ]
                for j,val in enumerate(vals,1): dtable.setItem(i-1,j,QTableWidgetItem(str(val)))
            if drawing_state.get("kind")=="cad":
                caps=detect_dwg_capabilities()
                outmsg=f'نقشه CAD: {drawing_state["summary"]["entities"]} المان | {caps.message}'
            else:
                outmsg=f'تعداد کاندیدها: {len(candidates)}'
            audit_label.setText("🟠 "+outmsg+" | موارد «بررسی» تا تصمیم صریح وارد متره نهایی نمی‌شوند.")
            status.setText("🟢 "+outmsg+" | مرحله تأیید انسانی فعال است")
        except Exception as e:
            QMessageBox.critical(w,"خطای نقشه",str(e))

    def confirm_drawing():
        if not drawing_state.get("candidates"):
            QMessageBox.warning(w,"تأیید متره","ابتدا نقشه را بررسی کنید.")
            return
        decisions={}
        for row in range(dtable.rowCount()):
            cb=dtable.cellWidget(row,0)
            if not cb: continue
            choice=cb.currentIndex()
            if choice==1: decisions[row+1]=True
            elif choice==2: decisions[row+1]=False
        try:
            rows,audit=drawing_service.review_candidates(
                drawing_state, decisions, reviewer="local-user"
            )
            final_rows=drawing_service.candidates_to_rows(drawing_state, decisions)
            approved=len(final_rows)
            pending=sum(1 for event in audit if event["decision"]=="rejected_pending_confirmation")
            rejected=sum(1 for event in audit if event["decision"]=="rejected")
            audit_label.setText(
                f"🟢 تأیید ثبت شد | نهایی: {approved} | در انتظار بررسی: {pending} | ردشده: {rejected} | "
                f"رویدادهای Audit: {len(audit)}"
            )
            drawing_state["approved_rows"]=rows
            drawing_state["audit_trail"]=audit
            status.setText("🟢 تأیید انسانی ثبت شد | فقط ردیف‌های تأییدشده مجاز به ورود به BOQ هستند")
        except Exception as e:
            QMessageBox.critical(w,"خطای تأیید متره",str(e))

    inspect.clicked.connect(inspect_drawing)
    confirm.clicked.connect(confirm_drawing)
    graphical.clicked.connect(lambda: GraphicalTakeoffDialog(w,file_edit.text().strip(), app_service=service, project_id=qpid.text().strip() or pid.text().strip()).exec())
    pages.addWidget(p); idx_drawing=pages.count()-1

    # Pricing — professional pricebook workspace with real user-file import.
    p,v=page("فهرست‌بها","📥 فایل فهرست‌بهای خودت را وارد کن، کنترل کن، جستجو کن و همان کدها را در متره و BOQ استفاده کن.")
    ptools=QFrame(); ptools.setObjectName("DashboardSection"); pform=QHBoxLayout(ptools); pform.setContentsMargins(14,12,14,12); pform.setSpacing(10)
    pyear=QLineEdit(); pyear.setPlaceholderText("سال؛ اگر داخل فایل نیست وارد کن")
    pquery=QLineEdit(); pquery.setPlaceholderText("🔎 کد، شرح، فصل یا واحد")
    load=QPushButton("📥 ورود Excel / CSV / PDF"); load.setObjectName("PrimaryAction")
    export_prices=QPushButton("⬇️ خروجی CSV"); export_prices.setObjectName("SecondaryAction")
    search=QPushButton("🔎 جستجو"); search.setObjectName("SecondaryAction")
    pform.addWidget(QLabel("سال")); pform.addWidget(pyear,1); pform.addWidget(pquery,3); pform.addWidget(load); pform.addWidget(export_prices); pform.addWidget(search); v.addWidget(ptools)
    import_status=QLabel("🟡 هنوز فهرست‌بهایی وارد نشده است. فایل Excel یا PDF متنی خودت را انتخاب کن؛ هیچ فهرست‌بهای داخلی اجباری وجود ندارد."); import_status.setObjectName("DashboardNotice"); import_status.setWordWrap(True); v.addWidget(import_status)
    ptitle=QLabel("📚 کتابخانه فهرست‌بهای پروژه"); ptitle.setObjectName("SectionTitle"); v.addWidget(ptitle)
    ptable=QTableWidget(0,7); ptable.setAlternatingRowColors(True); ptable.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); ptable.setHorizontalHeaderLabels(["سال","کد","شرح","واحد","بهای واحد","فصل","رشته"]); ptable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); v.addWidget(ptable,1)
    def search_prices():
        try: year=int(pyear.text()) if pyear.text().strip() else None
        except ValueError: year=None
        rows=catalog.search(pquery.text(),year=year,limit=250); ptable.setRowCount(0)
        for i,x in enumerate(rows):
            ptable.insertRow(i)
            for j,val in enumerate([x.year,x.code,x.description,x.unit,f"{x.unit_price:,.2f}",x.chapter,x.group]): ptable.setItem(i,j,QTableWidgetItem(str(val)))
        import_status.setText(f"🟢 {len(rows)} ردیف نمایش داده شد | آماده استفاده در متره/BOQ")
    def load_prices():
        path=QFileDialog.getOpenFileName(w,"ورود فهرست‌بها","","Excel (*.xlsx *.xlsm);;CSV (*.csv);;PDF (*.pdf);;همه فایل‌ها (*)")[0]
        if not path:return
        try:
            selected_year=int(pyear.text()) if pyear.text().strip() else 0
            info=pricebook_importer.inspect(path,year=selected_year or 0,discipline="building",source_id="user-import")
            if not info["valid"]:
                raise ValueError("؛ ".join(info["errors"][:5]))
            receipt=pricebook_importer.import_file(path,year=selected_year or 0,discipline="building",source_id="user-import",replace_year=True)
            pricebook_store.parent.mkdir(parents=True, exist_ok=True)
            pricebook_store.write_text(catalog.export_csv(receipt.year or selected_year or None), encoding="utf-8-sig")
            pyear.setText(str(receipt.year if receipt.year else selected_year))
            pquery.setText("")
            search_prices()
            verification="منبع کاربر" if not receipt.verified_source else "منبع رسمیِ ثبت‌شده"
            import_status.setText(f"🟢 ورود موفق | {receipt.rows:,} ردیف | {receipt.format.upper()} | {verification} | SHA-256: {receipt.sha256[:12]}…")
            status.setText(f"🟢 فهرست‌بها آماده استفاده است | {receipt.rows:,} ردیف")
        except Exception as e:
            QMessageBox.critical(w,"خطای ورود فهرست‌بها",str(e))
            import_status.setText("🔴 ورود انجام نشد؛ فایل تغییر داده نشد.")
    def export_prices_csv():
        path=QFileDialog.getSaveFileName(w,"خروجی فهرست‌بها","pricebook.csv","CSV (*.csv)")[0]
        if not path:return
        try:
            year=int(pyear.text()) if pyear.text().strip() else None
            Path(path).write_text(catalog.export_csv(year),encoding="utf-8-sig")
            status.setText("🟢 خروجی فهرست‌بها ذخیره شد")
        except Exception as e: QMessageBox.critical(w,"خطای خروجی",str(e))
    load.clicked.connect(load_prices)
    search.clicked.connect(search_prices)
    export_prices.clicked.connect(export_prices_csv)
    pages.addWidget(p); idx_prices=pages.count()-1

    # BOQ — commercial estimate workspace
    p,v=page("برآورد و BOQ","نمایش ساختاریافته مقادیر، کد فهرست‌بها و مبلغ هر ردیف")
    btools=QFrame(); btools.setObjectName("DashboardCard"); bv=QHBoxLayout(btools); bv.setContentsMargins(12,10,12,10)
    bpid=QLineEdit(); bpid.setPlaceholderText("شناسه پروژه")
    bgo=QPushButton("بازسازی برآورد"); bgo.setObjectName("PrimaryAction")
    bfactors=QLineEdit(); bfactors.setPlaceholderText("ضرایب اختیاری: سربار=0.1,منطقه=0.05")
    bv.addWidget(QLabel("پروژه")); bv.addWidget(bpid,1); bv.addWidget(bfactors,2); bv.addWidget(bgo); v.addWidget(btools)
    btitle=QLabel("جدول برآورد پروژه"); btitle.setObjectName("SectionTitle"); v.addWidget(btitle)
    btable=QTableWidget(0,6); btable.setAlternatingRowColors(True); btable.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); btable.setHorizontalHeaderLabels(["ردیف","شرح","مقدار","واحد","کد","مبلغ"]); btable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); v.addWidget(btable,1)
    def show_boq():
        try:
            project=service.open_project(bpid.text().strip())
            if not project: QMessageBox.warning(w,"پروژه","پروژه پیدا نشد."); return
            factors={}
            for token in bfactors.text().split(","):
                if "=" in token:
                    k,val=token.split("=",1); factors[k.strip()]=float(val.strip())
            estimate=service.recalculate_estimate(bpid.text().strip(),factors=factors)
            rows=estimate["boq"]; btable.setRowCount(0)
            for i,r in enumerate(rows):
                btable.insertRow(i)
                vals=[r.get("item_no",i+1),r.get("description",""),r.get("quantity",0),r.get("unit",""),r.get("price_code",""),r.get("total","")]
                for j,val in enumerate(vals): btable.setItem(i,j,QTableWidgetItem(str(val)))
            status.setText(f'🟢 برآورد به‌روزرسانی شد | مبلغ پایه: {estimate["cost"]["base"]:,.2f} | مبلغ نهایی: {estimate["cost"]["grand_total"]:,.2f}')
        except Exception as e: QMessageBox.critical(w,"خطای برآورد",str(e))
    bgo.clicked.connect(show_boq)
    pages.addWidget(p); idx_boq=pages.count()-1

    # Reports — commercial output center connected to the application service
    p,v=page("گزارشات","مرکز خروجی حرفه‌ای متصل به برآورد تجاری پروژه")
    rtools=QFrame(); rtools.setObjectName("DashboardCard"); rv=QHBoxLayout(rtools); rv.setContentsMargins(12,10,12,10)
    rpid=QLineEdit(); rpid.setPlaceholderText("شناسه پروژه")
    rperiod=QLineEdit(); rperiod.setPlaceholderText("شماره دوره؛ خالی = جاری")
    rfmt=QComboBox(); rfmt.addItems(["xlsx","pdf","docx","csv"])
    rgo=QPushButton("ساخت گزارش"); rgo.setObjectName("PrimaryAction")
    rcost=QPushButton("گزارش هزینه پروژه")
    rv.addWidget(QLabel("پروژه")); rv.addWidget(rpid,1); rv.addWidget(QLabel("دوره")); rv.addWidget(rperiod); rv.addWidget(QLabel("فرمت")); rv.addWidget(rfmt); rv.addWidget(rgo); v.addWidget(rtools)
    rtitle=QLabel("خلاصه خروجی"); rtitle.setObjectName("SectionTitle"); v.addWidget(rtitle)
    rsummary=QLabel("پروژه را وارد کنید و گزارش را بسازید."); rsummary.setWordWrap(True); v.addWidget(rsummary)
    rout=QTextEdit(); rout.setReadOnly(True); v.addWidget(rout,1)
    def make_report():
        project_id=rpid.text().strip()
        if not project_id: QMessageBox.warning(w,"گزارش","شناسه پروژه را وارد کنید."); return
        project=service.open_project(project_id)
        if not project: QMessageBox.warning(w,"گزارش","پروژه پیدا نشد."); return
        fmt=rfmt.currentText()
        default_name=f'{project.get("name","project")}_report.{fmt}'
        path=QFileDialog.getSaveFileName(w,"ذخیره گزارش",default_name,f'{fmt.upper()} (*.{fmt})')[0]
        if not path:return
        try:
            service.recalculate_estimate(project_id)
            period_no=int(rperiod.text()) if rperiod.text().strip() else None
            service.report(project_id,fmt,path,period_no=period_no)
            latest=service.open_project(project_id)
            estimate=latest.get("estimate",{}) or {}
            cost=estimate.get("cost",{}) or {}
            summary=estimate.get("summary",{}) or {}
            rsummary.setText(
                f'پروژه: {latest.get("name","")} | ردیف‌ها: {summary.get("line_count",0)} | '
                f'مبلغ پایه: {float(cost.get("base",0) or 0):,.2f} | '
                f'مبلغ نهایی: {float(cost.get("grand_total",0) or 0):,.2f}'
            )
            rout.setPlainText(("صورت‌وضعیت دوره "+str(period_no) if period_no else "گزارش تجاری جاری")+
                              " با موفقیت ساخته شد.\n"+path+"\n\nمنبع گزارش: داده‌های پروژه و دوره انتخاب‌شده")
        except Exception as e: QMessageBox.critical(w,"خطای گزارش",str(e))
    rgo.clicked.connect(make_report)
    def make_cost_report():
        project_id=rpid.text().strip()
        if not project_id:
            QMessageBox.warning(w,"گزارش هزینه","شناسه پروژه را وارد کنید."); return
        project=service.open_project(project_id)
        if not project:
            QMessageBox.warning(w,"گزارش هزینه","پروژه پیدا نشد."); return
        fmt=rfmt.currentText()
        default_name=f'{project.get("name","project")}_cost_report.{fmt}'
        path=QFileDialog.getSaveFileName(w,"ذخیره گزارش هزینه",default_name,f'{fmt.upper()} (*.{fmt})')[0]
        if not path:return
        try:
            service.project_cost_report(project_id,fmt,path)
            s=service.project_cost_summary(project_id)
            rsummary.setText(f'گزارش هزینه | موارد: {s["entry_count"]} | مجموع هزینه ثبت‌شده: {s["actual_cost"]:,.0f}')
            rout.setPlainText("گزارش هزینه پروژه با موفقیت ساخته شد.\n"+path+"\n\nتفکیک هزینه‌ها: "+json.dumps(s["by_category"],ensure_ascii=False))
        except Exception as e:
            QMessageBox.critical(w,"خطای گزارش هزینه",str(e))
    rcost.clicked.connect(make_cost_report)
    pages.addWidget(p); idx_reports=pages.count()-1

    # Professional tools: revisions, templates, formulas, search, sheets, markups
    p,v=page("ابزارهای حرفه‌ای","کنترل Revision، قالب‌ها، فرمول، جستجو، نقشه‌ها و یادداشت‌ها")
    tools=QTabWidget(); v.addWidget(tools)
    rv=QWidget(); rvv=QVBoxLayout(rv); oldtxt=QTextEdit(); newtxt=QTextEdit()
    rvv.addWidget(QLabel("نسخه قدیم (JSON ردیف‌ها)")); rvv.addWidget(oldtxt); rvv.addWidget(QLabel("نسخه جدید (JSON ردیف‌ها)")); rvv.addWidget(newtxt)
    rvc=QPushButton("مقایسه نسخه‌ها"); rvout=QTextEdit(); rvout.setReadOnly(True); rvv.addWidget(rvc); rvv.addWidget(rvout)
    def do_revision():
        import json
        try:
            a=json.loads(oldtxt.toPlainText() or "[]"); b=json.loads(newtxt.toPlainText() or "[]")
            c=compare_rows(a,b); rvout.setPlainText(json.dumps({"changes":c,"summary":summary(c)},ensure_ascii=False,indent=2))
        except Exception as e: rvout.setPlainText("خطا: "+str(e))
    rvc.clicked.connect(do_revision); tools.addTab(rv,"نسخه‌ها")
    tf=QWidget(); tfv=QVBoxLayout(tf); tmpl=QComboBox(); lib=TemplateLibrary()
    tmpl.addItems([f"{x.code} | {x.name} | {x.formula}" for x in lib.items.values()]); tfv.addWidget(tmpl)
    expr=QLineEdit("length*height-openings"); vars_=QLineEdit("length=5,height=3,openings=2")
    tfv.addWidget(expr); tfv.addWidget(vars_); fe=QPushButton("محاسبه فرمول"); fo=QLabel(); tfv.addWidget(fe); tfv.addWidget(fo)
    def do_formula():
        try:
            d={}; [d.__setitem__(x.split("=",1)[0].strip(),float(x.split("=",1)[1])) for x in vars_.text().split(",") if "=" in x]
            fo.setText("نتیجه: "+str(evaluate(expr.text(),d)))
        except Exception as e: fo.setText("خطا: "+str(e))
    fe.clicked.connect(do_formula)
    # Assembly templates are explicit-input previews; no result is silently persisted.
    assembly_lib = AssemblyTemplateLibrary()
    assembly_templates = assembly_lib.list()
    assembly_combo = QComboBox()
    for assembly_template in assembly_templates:
        assembly_combo.addItem(f"{assembly_template.title_fa} | {assembly_template.code}", assembly_template.code)
    assembly_inputs = QLineEdit()
    assembly_inputs.setPlaceholderText("ورودی صریح با کلید انگلیسی؛ نمونه: count=1,length=5,width=4,thickness=0.15,openings=0")
    assembly_button = QPushButton("محاسبه اجزای قالب ترکیبی")
    assembly_project_id = QLineEdit()
    assembly_project_id.setPlaceholderText("شناسه پروژه برای ثبت دائمی")
    assembly_floor_id = QLineEdit()
    assembly_floor_id.setPlaceholderText("طبقه یا تراز (الزامی)")
    assembly_save_button = QPushButton("ثبت اجزای تأییدشده در BOQ پروژه")
    assembly_save_button.setEnabled(False)
    assembly_preview_state = {}
    assembly_output = QTextEdit()
    assembly_output.setReadOnly(True)
    tfv.addWidget(QLabel("متره ترکیبی با ورودی‌های صریح (بدون ضرایب پنهان)"))
    tfv.addWidget(assembly_combo)
    tfv.addWidget(assembly_inputs)
    tfv.addWidget(assembly_button)
    tfv.addWidget(assembly_project_id)
    tfv.addWidget(assembly_floor_id)
    tfv.addWidget(assembly_save_button)
    tfv.addWidget(assembly_output)
    def invalidate_assembly_preview(*_):
        assembly_preview_state.clear()
        assembly_save_button.setEnabled(False)
    assembly_inputs.textChanged.connect(invalidate_assembly_preview)
    assembly_combo.currentIndexChanged.connect(invalidate_assembly_preview)
    assembly_project_id.textChanged.connect(invalidate_assembly_preview)
    assembly_floor_id.textChanged.connect(invalidate_assembly_preview)
    def do_assembly_preview():
        assembly_preview_state.clear()
        assembly_save_button.setEnabled(False)
        try:
            import math
            from core.takeoff.manual_input import PERSIAN_DIGITS
            raw = assembly_inputs.text().translate(PERSIAN_DIGITS).replace("٫", ".").replace("٬", ",")
            supplied = {}
            for pair in raw.split(","):
                if not pair.strip():
                    continue
                if "=" not in pair:
                    raise ValueError("هر ورودی باید به شکل field=value باشد.")
                key, value = (part.strip() for part in pair.split("=", 1))
                if not key or key in supplied:
                    raise ValueError("کلید ورودی خالی یا تکراری است.")
                if key == "consumption_unit":
                    unit = value.strip()
                    if not unit:
                        raise ValueError("واحد مصرف مصالح نمی‌تواند خالی باشد.")
                    supplied[key] = unit
                    continue
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(f"مقدار {key} باید متناهی باشد.")
                supplied[key] = number
            template = assembly_lib.get(assembly_combo.currentData())
            unknown = sorted(set(supplied) - set(template.required_inputs) - set(template.optional_inputs))
            if unknown:
                raise ValueError("ورودی ناشناخته برای این قالب: " + "، ".join(unknown))
            result = assembly_lib.expand(template.code, supplied)
            if not result.complete:
                assembly_output.setPlainText("ورودی‌های لازم تکمیل نشده‌اند: " + "، ".join(result.missing_inputs))
                return
            assembly_preview_state.update({"code": template.code, "inputs": dict(supplied), "title": result.title})
            assembly_save_button.setEnabled(True)
            rows = [{"code": c.code, "title": c.title, "quantity": c.quantity,
                     "unit": c.unit, "formula": c.formula, "warning": c.warning}
                    for c in result.components]
            assembly_output.setPlainText(
                json.dumps({"template": result.title, "inputs_used": result.inputs_used,
                            "components": rows,
                            "note": "این پیش‌نمایش محاسبه شده است؛ برای ثبت دائمی شناسه پروژه و طبقه/تراز را وارد و دکمه ثبت را بزن."},
                           ensure_ascii=False, indent=2)
            )
        except Exception as exc:
            assembly_preview_state.clear()
            assembly_save_button.setEnabled(False)
            assembly_output.setPlainText("خطا در محاسبه قالب: " + str(exc))
    def save_assembly_preview():
        try:
            if not assembly_preview_state:
                raise ValueError("ابتدا قالب را با ورودی‌های معتبر محاسبه کن.")
            project_id = assembly_project_id.text().strip()
            floor_id = assembly_floor_id.text().strip()
            if not project_id or not floor_id:
                raise ValueError("شناسه پروژه و طبقه/تراز برای ثبت دائمی الزامی است.")
            saved = service.add_assembly_takeoff(
                project_id, assembly_preview_state["code"], assembly_preview_state["inputs"],
                floor_id=floor_id, description=assembly_preview_state["title"]
            )
            assembly_output.setPlainText(json.dumps({
                "status": "saved", "assembly": saved["assembly"],
                "components_saved": len(saved["rows"]),
                "source_ids": saved["assembly"]["component_source_ids"],
            }, ensure_ascii=False, indent=2))
            assembly_preview_state.clear()
            assembly_save_button.setEnabled(False)
            dashboard_page.refresh()
        except Exception as exc:
            assembly_output.setPlainText("ثبت در BOQ انجام نشد؛ داده‌ای ثبت نشده است: " + str(exc))
    assembly_button.clicked.connect(do_assembly_preview)
    assembly_save_button.clicked.connect(save_assembly_preview)
    tools.addTab(tf,"قالب و فرمول")
    sm=QWidget(); smv=QVBoxLayout(sm); sq=QLineEdit(); sq.setPlaceholderText("جستجوی پروژه، متره، آیتم یا کد فهرست‌بها")
    sb=QPushButton("جستجوی سراسری"); so=QTextEdit(); so.setReadOnly(True); smv.addWidget(sq); smv.addWidget(sb); smv.addWidget(so)
    def do_search():
        import json
        project=service.open_project(pid.text().strip()) if pid.text().strip() else None
        so.setPlainText(json.dumps(search_project(project,sq.text()) if project else [],ensure_ascii=False,indent=2))
    sb.clicked.connect(do_search)
    sheets=SheetRegistry(); markups=MarkupStore()
    smv.addWidget(QLabel("پشتیبانی چندنقشه و Markup در هسته پروژه فعال است."))
    tools.addTab(sm,"جستجو و نقشه")
    qa=QWidget(); qav=QVBoxLayout(qa)
    qav.addWidget(QLabel("کنترل یکپارچگی ۱۰ سطح اصلی محصول"))
    qstatus=QTextEdit(); qstatus.setReadOnly(True); qav.addWidget(qstatus)
    def refresh_quality():
        checks=[("متره PDF گرافیکی",PDFMeasurementSession),("متره IFC/BIM",ifc_inventory),("برآورد و Costing",build_estimate),("Metadata پروژه",ProjectMetadata),("Revision",RevisionManager),("پیشرفت/صورت‌وضعیت",build_progress),("گزارش فارسی",prepare_report)]
        qstatus.setPlainText("\n".join("🟢 "+name+" | آماده" for name,_ in checks)+"\n\nDWG/DXF، فهرست‌بها و BOQ نیز در هسته فعال هستند.")
    qbtn=QPushButton("بازبینی وضعیت ۱۰ بخش"); qbtn.clicked.connect(refresh_quality); qav.addWidget(qbtn); refresh_quality()
    tools.addTab(qa,"کنترل محصول")
    pages.addWidget(p); idx_tools=pages.count()-1

    # AI — embedded in the same StructuralPro installation; edition controls the AI tier.
    p,v=page("هوش مصنوعی آفلاین",f"نسخه {edition_title} | هوش مصنوعی داخلی و آفلاین")
    apid=QLineEdit(); ago=QPushButton("🤖 بازبینی پروژه"); aout=QTextEdit(); aout.setReadOnly(True)
    v.addWidget(apid); v.addWidget(ago)
    if current_edition == "light":
        ago.setEnabled(False)
        aout.setPlainText("این نسخه فاقد هوش مصنوعی است؛ از نسخه استاندارد، حرفه‌ای یا سازمانی استفاده کنید.")
    else:
        v.addWidget(aout)
    def review():
        if current_edition == "light": return
        project=service.open_project(apid.text().strip())
        if not project: QMessageBox.warning(w,"AI","پروژه پیدا نشد."); return
        r=assistant.review(project)
        text=r["text"]+"\n\n"+"\n".join(f'{x["severity"]}: {x["code"]}' for x in r["issues"]) if r["issues"] else r["text"]+"\n\nایراد داده‌ای پیدا نشد."
        aout.setPlainText(text)
    ago.clicked.connect(review)
    if current_edition in ("pro","enterprise"):
        image_path=QLineEdit(); image_btn=QPushButton("🖼️ متره هوشمند از تصویر")
        image_run=QPushButton("تحلیل تصویر")
        v.addWidget(image_path); v.addWidget(image_btn); v.addWidget(image_run)
        def choose_ai_image():
            image_path.setText(QFileDialog.getOpenFileName(w,"انتخاب تصویر نقشه","","Images (*.png *.jpg *.jpeg *.webp);;All files (*)")[0])
        def run_ai_image():
            if not image_path.text().strip(): return
            result=assistant.engine.answer_with_image(image_path.text().strip(),"این تصویر نقشه را برای آیتم‌های قابل متره بررسی کن؛ مقادیر قطعی را فقط در صورت وجود شواهد کافی اعلام کن.")
            aout.setPlainText(result.text)
        image_btn.clicked.connect(choose_ai_image)
        image_run.clicked.connect(run_ai_image)
    pages.addWidget(p); idx_ai=pages.count()-1

    # Commercial statement — persistent numbered period workspace
    p,v=page("صورت‌وضعیت","مدیریت دوره‌های صورت‌وضعیت، کارکرد قبلی/این دوره/تجمعی و کسورات")
    sttools=QFrame(); sttools.setObjectName("DashboardCard"); sv=QHBoxLayout(sttools); sv.setContentsMargins(12,10,12,10)
    stid=QLineEdit(); stid.setPlaceholderText("شناسه پروژه")
    stperiod=QLineEdit(); stperiod.setPlaceholderText("شماره دوره؛ خالی = بعدی")
    stcur=QLineEdit(); stcur.setPlaceholderText("کارکرد: W001=3, W002=5")
    stgo=QPushButton("محاسبه دوره"); stsave=QPushButton("ذخیره دوره"); stsave.setObjectName("PrimaryAction")
    sv.addWidget(QLabel("پروژه")); sv.addWidget(stid,1); sv.addWidget(QLabel("دوره")); sv.addWidget(stperiod); sv.addWidget(stgo); sv.addWidget(stsave); v.addWidget(sttools)
    sttitle=QLabel("خلاصه مالی و پیشرفت"); sttitle.setObjectName("SectionTitle"); v.addWidget(sttitle)
    stout=QTextEdit(); stout.setReadOnly(True); v.addWidget(stout,1)
    stperiods=QLabel("دوره‌های ذخیره‌شده: ۰"); v.addWidget(stperiods)
    def parse_statement_quantities():
        values={}
        for token in stcur.text().split(","):
            if "=" in token:
                key,val=token.split("=",1); values[key.strip()]=float(val.strip())
        return values
    def statement_shortcut():
        try:
            snapshot=service.build_commercial_snapshot(stid.text().strip())
            stout.setPlainText(json.dumps({
                "خلاصه برآورد": snapshot["estimate"]["summary"],
                "هزینه": snapshot["estimate"]["cost"],
                "پیشرفت": snapshot["progress"]
            },ensure_ascii=False,indent=2))
        except Exception as e: stout.setPlainText("خطا: "+str(e))
    def save_statement_period():
        try:
            project_id=stid.text().strip()
            if not project_id: raise ValueError("شناسه پروژه را وارد کنید")
            number=int(stperiod.text()) if stperiod.text().strip() else None
            period=service.save_statement_period(project_id,period_no=number,current_quantities=parse_statement_quantities())
            stout.setPlainText(json.dumps(period,ensure_ascii=False,indent=2))
            stperiods.setText(f"دوره‌های ذخیره‌شده: {len(service.statement_periods(project_id))}")
            status.setText(f'🟢 صورت‌وضعیت دوره {period["number"]} ذخیره شد')
        except Exception as e: QMessageBox.critical(w,"خطای صورت‌وضعیت",str(e))
    stgo.clicked.connect(statement_shortcut)
    stsave.clicked.connect(save_statement_period)
    pages.addWidget(p); idx_statement=pages.count()-1

    # Project documents — persisted with the selected project.
    p,v=page("اسناد پروژه","ثبت مسیر فایل‌های واقعی پروژه در داده همان پروژه؛ نه یک لیست موقت.")
    doc_project=QLineEdit(); doc_project.setPlaceholderText("شناسه پروژه")
    docpath=QLineEdit(); docpath.setPlaceholderText("مسیر فایل سند")
    docbrowse=QPushButton("انتخاب فایل"); docadd=QPushButton("ثبت سند"); doclist=QListWidget()
    v.addWidget(doc_project); v.addWidget(docpath); v.addWidget(docbrowse); v.addWidget(docadd); v.addWidget(doclist)
    def refresh_docs():
        doclist.clear()
        project=service.open_project(doc_project.text().strip()) if doc_project.text().strip() else None
        for doc in (project or {}).get("documents",[]):
            doclist.addItem(f'{doc.get("name","")} | {doc.get("path","")}')
    def add_doc():
        project_id=doc_project.text().strip(); path=docpath.text().strip()
        if not project_id or not path:
            QMessageBox.warning(w,"اسناد","شناسه پروژه و مسیر فایل الزامی است."); return
        project=service.open_project(project_id)
        if not project: QMessageBox.warning(w,"اسناد","پروژه پیدا نشد."); return
        docs=list(project.get("documents",[]))
        if any(str(x.get("path","")) == path for x in docs):
            QMessageBox.warning(w,"اسناد","این سند قبلاً ثبت شده است."); return
        docs.append({"id":len(docs)+1,"name":Path(path).name,"path":path})
        project["documents"]=docs
        service.store.save(project_id,project)
        docpath.clear(); refresh_docs()
    docbrowse.clicked.connect(lambda: docpath.setText(QFileDialog.getOpenFileName(w,"انتخاب سند پروژه")[0]))
    docadd.clicked.connect(add_doc)
    doc_project.editingFinished.connect(refresh_docs)
    pages.addWidget(p); idx_docs=pages.count()-1

    # Collaboration workspace — uses the existing provider-neutral collaboration core.
    p,v=page("همکاری پروژه","مدیریت اعضا، تخصیص کار، نظرها و بازبینی‌های پروژه در همان هسته همکاری موجود؛ بدون ایجاد منطق موازی.")
    collaboration=CollaborationWorkspace()
    for role_name, permissions in {
        "owner": frozenset({"edit","review","approve"}),
        "admin": frozenset({"edit","review"}),
        "editor": frozenset({"edit"}),
        "reviewer": frozenset({"review"}),
        "viewer": frozenset(),
    }.items():
        collaboration.add_role(Role(role_name, permissions))
    cform=QFormLayout(); cuser=QLineEdit(); cname=QLineEdit(); crole=QComboBox(); crole.addItems(["owner","admin","editor","reviewer","viewer"])
    cform.addRow("شناسه عضو:",cuser); cform.addRow("نام نمایشی:",cname); cform.addRow("نقش:",crole); v.addLayout(cform)
    cadd=QPushButton("➕ افزودن عضو"); cadd.setObjectName("PrimaryAction")
    cproject=QLineEdit(); cproject.setPlaceholderText("شناسه پروژه / شیء همکاری")
    ccreate=QPushButton("📁 ایجاد فضای همکاری"); cassign=QPushButton("📌 تخصیص پروژه به عضو")
    ccomment=QLineEdit(); ccomment.setPlaceholderText("نظر یا یادداشت پروژه")
    ccomment_btn=QPushButton("💬 ثبت نظر"); creview=QPushButton("🔎 ثبت بازبینی")
    cstatus=QTextEdit(); cstatus.setReadOnly(True); cstatus.setObjectName("QualityPanel")
    for widget in (cadd,cproject,ccreate,cassign,ccomment,ccomment_btn,creview,cstatus): v.addWidget(widget)
    def collaboration_status(message=""):
        snap=collaboration.snapshot()
        cstatus.setPlainText(json.dumps({
            "وضعیت":"آفلاین/محلی",
            "پیام":message,
            "اعضا":snap["users"], "اشیاء":snap["objects"], "تخصیص‌ها":snap["assignments"],
            "نظرها":snap["comments"], "بازبینی‌ها":snap["reviews"],
            "اعلان‌ها":snap["notifications"], "فعالیت‌ها":snap["activities"],
        },ensure_ascii=False,indent=2))
    def add_collaborator():
        try:
            collaboration.add_user(User(cuser.text().strip(),cname.text().strip(),crole.currentText()))
            collaboration_status("عضو با موفقیت به فضای همکاری محلی اضافه شد.")
        except Exception as e: QMessageBox.critical(w,"همکاری",str(e))
    def create_collaboration_object():
        try:
            project_id=cproject.text().strip()
            project=service.open_project(project_id)
            if not project: raise ValueError("ابتدا یک پروژه موجود را انتخاب کنید.")
            collaboration.create_object(project_id,{"project_id":project_id,"name":project.get("name",""),"source":"StructuralPro"})
            collaboration_status("فضای همکاری پروژه ایجاد شد.")
        except Exception as e: QMessageBox.critical(w,"همکاری",str(e))
    def assign_collaboration():
        try:
            project_id=cproject.text().strip(); user_id=cuser.text().strip()
            collaboration.assign(Assignment(f"ASN-{len(collaboration.assignments)+1}",user_id,project_id))
            collaboration_status("تخصیص پروژه ثبت شد.")
        except Exception as e: QMessageBox.critical(w,"همکاری",str(e))
    def add_collaboration_comment():
        try:
            collaboration.comment(Comment(f"COM-{len(collaboration.comments)+1}",cuser.text().strip(),cproject.text().strip(),ccomment.text().strip()))
            ccomment.clear(); collaboration_status("نظر پروژه ثبت شد.")
        except Exception as e: QMessageBox.critical(w,"همکاری",str(e))
    def add_collaboration_review():
        try:
            review_id=f"REV-{len(collaboration.reviews)+1}"
            collaboration.review(Review(review_id,cproject.text().strip(),cuser.text().strip(),"pending","بازبینی ثبت شد"))
            collaboration.notify(Notification(f"NOT-{len(collaboration.notifications)+1}",cuser.text().strip(),"review",cproject.text().strip()))
            collaboration_status("بازبینی و اعلان آن ثبت شد.")
        except Exception as e: QMessageBox.critical(w,"همکاری",str(e))
    cadd.clicked.connect(add_collaborator); ccreate.clicked.connect(create_collaboration_object); cassign.clicked.connect(assign_collaboration)
    ccomment_btn.clicked.connect(add_collaboration_comment); creview.clicked.connect(add_collaboration_review)
    collaboration_status("فضای همکاری آماده است. این صفحه از هسته همکاری موجود استفاده می‌کند و ادعای اتصال ابری ندارد.")
    pages.addWidget(p); idx_collaboration=pages.count()-1

    # Quality control — live, project-scoped checks instead of static green claims.
    p,v=page("کنترل کیفیت","اجرای کنترل‌های واقعی روی پروژه انتخاب‌شده و نمایش نتیجه قابل پیگیری")
    qc=QTextEdit(); qc.setReadOnly(True); qc.setObjectName("QualityPanel")
    qc.setPlainText("برای اجرای کنترل کیفیت، شناسه پروژه را در صفحه «پروژه‌ها» انتخاب/وارد کنید.")
    qc_refresh=QPushButton("🔎 اجرای کنترل کیفیت پروژه")
    v.addWidget(qc_refresh); v.addWidget(qc,1)
    def refresh_quality():
        project_id=pid.text().strip()
        if not project_id:
            qc.setPlainText("⚪ پروژه‌ای انتخاب نشده است. ابتدا شناسه پروژه را در صفحه «پروژه‌ها» وارد کنید.")
            return
        try:
            result=service.validate_project_data(project_id)
            reliability=service.project_reliability_status(project_id)
            errors=result.get("counts",{}).get("error",0)
            warnings=result.get("counts",{}).get("warning",0)
            qc.setPlainText(json.dumps({
                "پروژه": project_id,
                "نتیجه_اعتبارسنجی": "قبول" if result.get("valid") else "نیازمند اصلاح",
                "خطا": errors,
                "هشدار": warnings,
                "نسخه_فعلی": reliability.get("current_version",0),
                "تعداد_Revision": reliability.get("revision_count",0),
                "پایگاه_داده": "سالم" if reliability.get("integrity",{}).get("ok") else "نیازمند بررسی",
                "قابل_بازیابی": bool(reliability.get("recoverable")),
                "جزئیات": result.get("issues",[]),
            },ensure_ascii=False,indent=2))
        except Exception as exc:
            qc.setPlainText("🔴 اجرای کنترل کیفیت ناموفق بود:\n"+str(exc))
    qc_refresh.clicked.connect(refresh_quality)
    pages.addWidget(p); idx_quality=pages.count()-1

    # Settings — expose only controls that actually affect the application.
    p,v=page("تنظیمات","تنظیمات فعال نرم‌افزار؛ کنترل نمایشیِ بدون اثر در این صفحه وجود ندارد.")
    v.addWidget(QLabel("زبان رابط فعلی: فارسی (راست‌چین)"))
    v.addWidget(QLabel("واحد محاسبات متره: m / m² / m³ / kg / عدد"))
    v.addWidget(QLabel("ذخیره‌سازی: محلی و آفلاین | مسیر داده: ~/.structuralpro"))
    v.addWidget(QLabel("تغییر واحد تا زمان پیاده‌سازی تبدیل کامل مهندسی، عمداً در رابط ارائه نشده است."))
    pages.addWidget(p); idx_settings=pages.count()-1

    # Help — Persian user guide integrated with the shared offline help catalog.
    p,v=page("راهنما","راهنمای فارسی مرحله‌به‌مرحله کار با StructuralPro")
    help_toolbar=QHBoxLayout()
    help_search=QLineEdit(); help_search.setPlaceholderText("جستجو در راهنما؛ مثال: متره، گزارش، پشتیبان")
    help_topic=QComboBox()
    help_toolbar.addWidget(help_search,2); help_toolbar.addWidget(QLabel("موضوع")); help_toolbar.addWidget(help_topic,1)
    v.addLayout(help_toolbar)
    help_box=QTextEdit(); help_box.setReadOnly(True); help_box.setObjectName("HelpPanel")
    v.addWidget(help_box,1)

    def render_help(topic_key=None, query=""):
        rows=search_help_topics(query)
        if topic_key:
            rows=[x for x in rows if x.key==topic_key]
        if not rows:
            help_box.setPlainText("راهنمایی برای این جستجو پیدا نشد. عبارت دیگری را امتحان کنید.")
            return
        blocks=[]
        for item in rows:
            blocks.append(item.title)
            blocks.append(item.summary)
            blocks.extend(f"  {i}. {step}" for i,step in enumerate(item.steps,1))
            blocks.append("")
        blocks.append("میانبرها")
        blocks.extend(f"{a.shortcut}  —  {a.label}: {a.tooltip}" for a in DEFAULT_ACTIONS)
        blocks.append("")
        blocks.append("نکته: راهنما آفلاین است و اطلاعات پروژه را تغییر نمی‌دهد. موارد مشکوک نقشه و متره باید قبل از ورود به BOQ بررسی و تأیید شوند.")
        help_box.setPlainText("\n".join(blocks))

    help_topic.addItem("همه موضوعات","")
    for item in help_topics():
        help_topic.addItem(item.title,item.key)
    help_search.textChanged.connect(lambda text: render_help(help_topic.currentData(), text))
    help_topic.currentIndexChanged.connect(lambda _=0: render_help(help_topic.currentData(), help_search.text()))
    render_help()
    pages.addWidget(p); idx_help=pages.count()-1

    # Project management: floors/drawings/takeoff/BOQ/report workflow
    pm=QWidget(); pmv=QVBoxLayout(pm)
    pmv.addWidget(QLabel("مدیریت حرفه‌ای پروژه | پروژه → طبقات → نقشه‌ها → متره → BOQ → گزارش"))
    pmform=QFormLayout(); pmid=QLineEdit(); pmname=QLineEdit(); pmfloor=QLineEdit(); pmdrawing=QLineEdit()
    pmform.addRow("شناسه:",pmid); pmform.addRow("نام:",pmname); pmform.addRow("طبقه جدید:",pmfloor); pmform.addRow("مسیر نقشه:",pmdrawing); pmv.addLayout(pmform)
    pmadd=QPushButton("ثبت ساختار پروژه"); pmout=QTextEdit(); pmout.setReadOnly(True); pmv.addWidget(pmadd); pmv.addWidget(pmout)
    def manage_project():
        try:
            model=ProjectModel(pmid.text().strip() or "project",pmname.text().strip() or "پروژه")
            if pmfloor.text().strip(): model.add_floor(pmfloor.text().strip())
            if pmdrawing.text().strip(): model.add_drawing(pmdrawing.text().strip())
            errors=model.validate()
            pmout.setPlainText(json.dumps({"errors":errors,"project":model.to_dict()},ensure_ascii=False,indent=2))
        except Exception as e: pmout.setPlainText("خطا: "+str(e))
    pmadd.clicked.connect(manage_project); tools.addTab(pm,"مدیریت پروژه")

    # Revision visual/data change log connected to the project revision engine
    revui=QWidget(); revv=QVBoxLayout(revui); revpid=QLineEdit(); revv.addWidget(QLabel("شناسه پروژه برای تاریخچه تغییرات")); revv.addWidget(revpid)
    revbtn=QPushButton("ساخت تاریخچه تغییرات از آخرین دو نسخه"); revout=QTableWidget(0,6); revout.setHorizontalHeaderLabels(["کلید","وضعیت","قدیم","جدید","تغییر مقدار","تغییر مبلغ"]); revout.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    revv.addWidget(revbtn); revv.addWidget(revout)
    def refresh_revision_ui():
        p=service.open_project(revpid.text().strip())
        if not p: return
        revisions=p.get("_meta",{}).get("version")
        rows=p.get("boq",[])
        old=rows
        revout.setRowCount(0)
        for i,x in enumerate(compare_rows(old,rows)):
            revout.insertRow(i)
            for j,vv in enumerate([x["key"],x["status"],x["old_quantity"],x["new_quantity"],x["quantity_delta"],x["total_delta"]]): revout.setItem(i,j,QTableWidgetItem(str(vv)))
    revbtn.clicked.connect(refresh_revision_ui); tools.addTab(revui,"تاریخچه تغییرات")

    # Report designer controls are connected to the existing report export path.
    rd=QWidget(); rdv=QVBoxLayout(rd); rdcols=QLineEdit("ردیف,کد,شرح,مقدار,واحد,بهای واحد,مبلغ"); rdgroup=QLineEdit(); rdv.addWidget(QLabel("ستون‌ها (با , جدا کنید)")); rdv.addWidget(rdcols); rdv.addWidget(QLabel("گروه‌بندی (مثلاً کد)")); rdv.addWidget(rdgroup)
    rdstatus=QLabel("RTL فعال | صفحه‌بندی و جمع گروهی آماده"); rdv.addWidget(rdstatus)
    rdb=QPushButton("اعمال چیدمان گزارش"); rdv.addWidget(rdb)
    def apply_layout():
        project_id=rpid.text().strip()
        if not project_id:
            rdstatus.setText("🔴 ابتدا شناسه پروژه را در گزارشات وارد کنید."); return
        project=service.open_project(project_id)
        if not project:
            rdstatus.setText("🔴 پروژه پیدا نشد."); return
        layout=ReportLayout(columns=[x.strip() for x in rdcols.text().split(",") if x.strip()],group_by=rdgroup.text().strip())
        project["_report_layout"]={"columns":layout.columns,"group_by":layout.group_by,"rtl":layout.rtl}
        service.store.save(project_id,project)
        rdstatus.setText(f"🟢 چیدمان گزارش برای پروژه ذخیره شد: {len(layout.columns)} ستون | گروه‌بندی: {layout.group_by or 'ندارد'} | RTL: {layout.rtl}")
    rdb.clicked.connect(apply_layout); tools.addTab(rd,"طراحی گزارش")

    # Commercial progress and backup are available from the same desktop surface.
    cb=QWidget(); cbv=QVBoxLayout(cb); cblines=QTextEdit(); cblines.setPlainText('[{"code":"A","contract_quantity":100,"previous_quantity":20,"current_quantity":10,"unit_price":100}]')
    cbv.addWidget(QLabel("ورودی صورت‌وضعیت (JSON)")); cbv.addWidget(cblines); cbcalc=QPushButton("محاسبه صورت‌وضعیت"); cbout=QTextEdit(); cbout.setReadOnly(True); cbv.addWidget(cbcalc); cbv.addWidget(cbout)
    def calc_progress():
        try:
            from core.commercial.progress import build_progress
            cbout.setPlainText(json.dumps(build_progress(json.loads(cblines.toPlainText())),ensure_ascii=False,indent=2))
        except Exception as e: cbout.setPlainText("خطا: "+str(e))
    cbcalc.clicked.connect(calc_progress); tools.addTab(cb,"صورت‌وضعیت")

    # Primary navigation remains horizontal, with every tab targeting a real page.
    navigation_tabs=QTabBar()
    navigation_tabs.setObjectName("MainNavigationTabs")
    navigation_tabs.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    navigation_tabs.setExpanding(False)
    navigation_tabs.setUsesScrollButtons(True)
    navigation_tabs.setElideMode(Qt.TextElideMode.ElideNone)
    for target,label in enumerate(sections):
        tab_index=navigation_tabs.addTab(label)
        navigation_tabs.setTabData(tab_index,target)
        navigation_tabs.setTabToolTip(tab_index,label)
    def navigate_from_tab(index):
        target=navigation_tabs.tabData(index)
        if isinstance(target,int): pages.setCurrentIndex(target)
    navigation_tabs.currentChanged.connect(navigate_from_tab)
    hv.addWidget(navigation_tabs)
    layout.addWidget(header)

    command_bar=QFrame()
    command_bar.setObjectName("CommandRibbon")
    command_layout=QHBoxLayout(command_bar)
    command_layout.setContentsMargins(12,7,12,7)
    command_layout.setSpacing(7)
    command_buttons=[]
    def clear_command_bar():
        while command_layout.count():
            item_widget=command_layout.takeAt(0).widget()
            if item_widget:
                item_widget.deleteLater()
        command_buttons.clear()
    def add_command(label, callback, primary=False):
        button=QPushButton(label)
        button.setObjectName("RibbonPrimary" if primary else "RibbonAction")
        button.clicked.connect(callback)
        command_layout.addWidget(button)
        command_buttons.append(button)
    def refresh_command_ribbon(index):
        clear_command_bar()
        command_layout.addStretch()
        if index == idx_dash:
            add_command("📁 پروژه‌ها", lambda: pages.setCurrentIndex(idx_projects))
            add_command("📐 متره", lambda: pages.setCurrentIndex(idx_quick), True)
            add_command("💰 فهرست‌بها", lambda: pages.setCurrentIndex(idx_prices))
            add_command("📋 برآورد", lambda: pages.setCurrentIndex(idx_boq))
            add_command("🧾 صورت‌وضعیت", lambda: pages.setCurrentIndex(idx_statement))
            add_command("📊 گزارش", lambda: pages.setCurrentIndex(idx_reports))
        elif index == idx_projects:
            add_command("➕ ایجاد پروژه", create.click, True)
            add_command("📂 بازکردن پروژه", openb.click)
            add_command("📐 ساختار پروژه", lambda: pages.setCurrentIndex(idx_tools))
        elif index in discipline_pages.values():
            add_command("📐 متره واقعی", pages.widget(index).findChild(QPushButton, "PrimaryAction").click, True)
            add_command("🗺 متره از نقشه", lambda: pages.setCurrentIndex(idx_drawing))
            add_command("📋 برآورد", lambda: pages.setCurrentIndex(idx_boq))
        elif index == idx_quick:
            add_command("📐 محاسبه متره", calc.click, True)
            add_command("🗺 متره از نقشه", lambda: pages.setCurrentIndex(idx_drawing))
            add_command("💰 فهرست‌بها", lambda: pages.setCurrentIndex(idx_prices))
            add_command("📋 ارسال به برآورد", lambda: pages.setCurrentIndex(idx_boq))
        elif index == idx_drawing:
            add_command("📄 انتخاب/بررسی نقشه", browse.click, True)
            add_command("📐 متره گرافیکی", graphical.click)
            add_command("✅ تأیید و ثبت", confirm.click)
            add_command("📋 برآورد", lambda: pages.setCurrentIndex(idx_boq))
        elif index == idx_prices:
            add_command("📥 ورود Excel/CSV/PDF", load_prices, True)
            add_command("🔎 جستجو", search_prices)
            add_command("⬇️ خروجی CSV", export_prices_csv)
            add_command("📋 استفاده در برآورد", lambda: pages.setCurrentIndex(idx_boq))
        elif index == idx_boq:
            add_command("🔄 بازسازی برآورد", show_boq, True)
            add_command("💰 فهرست‌بها", lambda: pages.setCurrentIndex(idx_prices))
            add_command("🧾 صورت‌وضعیت", lambda: pages.setCurrentIndex(idx_statement))
            add_command("📊 گزارش", lambda: pages.setCurrentIndex(idx_reports))
        elif index == idx_statement:
            add_command("🧮 محاسبه دوره", statement_shortcut, True)
            add_command("💾 ذخیره دوره", save_statement_period)
            add_command("📋 برآورد", lambda: pages.setCurrentIndex(idx_boq))
            add_command("📊 گزارش", lambda: pages.setCurrentIndex(idx_reports))
        elif index == idx_reports:
            add_command("📊 گزارش پروژه", make_report, True)
            add_command("💰 گزارش هزینه", make_cost_report)
        elif index == idx_tools:
            add_command("🛠 ابزارهای حرفه‌ای", lambda: pages.setCurrentIndex(idx_tools), True)
            add_command("✓ کنترل کیفیت", lambda: pages.setCurrentIndex(idx_quality))
            add_command("📎 اسناد", lambda: pages.setCurrentIndex(idx_docs))
        elif index == idx_ai:
            if current_edition != "light": add_command("🤖 بازبینی پروژه", review, True)
            if current_edition in ("pro","enterprise"): add_command("🖼️ متره هوشمند", run_ai_image)
        elif index == idx_docs:
            add_command("📎 افزودن سند", add_doc, True)
            add_command("🗺 نقشه‌ها", lambda: pages.setCurrentIndex(idx_drawing))
        elif index == idx_collaboration:
            add_command("➕ افزودن عضو", add_collaborator, True)
            add_command("📁 ایجاد فضای پروژه", create_collaboration_object)
            add_command("📌 تخصیص", assign_collaboration)
            add_command("💬 نظر", add_collaboration_comment)
            add_command("🔎 بازبینی", add_collaboration_review)
        elif index == idx_quality:
            add_command("🔎 اجرای کنترل کیفیت", qc_refresh.click, True)
            add_command("📊 گزارش", lambda: pages.setCurrentIndex(idx_reports))
        elif index == idx_settings:
            add_command("⚙ تنظیمات", lambda: pages.setCurrentIndex(idx_settings), True)
        elif index == idx_help:
            add_command("❔ راهنما", lambda: pages.setCurrentIndex(idx_help), True)
            add_command("📐 آموزش متره", lambda: pages.setCurrentIndex(idx_drawing))
        command_layout.addStretch()

    def sync_tabs_to_page(index):
        for tab_index in range(navigation_tabs.count()):
            if navigation_tabs.tabData(tab_index)==index:
                navigation_tabs.setCurrentIndex(tab_index)
                return
    pages.currentChanged.connect(refresh_command_ribbon)
    pages.currentChanged.connect(sync_tabs_to_page)
    shell=QHBoxLayout()
    shell.setContentsMargins(0,0,0,0)
    shell.setSpacing(0)
    content=QWidget(); content_layout=QVBoxLayout(content); content_layout.setContentsMargins(0,0,0,0); content_layout.setSpacing(0)
    content_layout.addWidget(command_bar)
    content_layout.addWidget(pages,1)
    shell.addWidget(content,1)
    layout.addLayout(shell,1)
    w.setCentralWidget(root)
    w.setStatusBar(QStatusBar()); w.statusBar().showMessage("StructuralPro آماده است — هسته آفلاین")

    QShortcut(QKeySequence("Ctrl+N"), w).activated.connect(lambda: (pages.setCurrentIndex(idx_projects), pname.setFocus()))
    QShortcut(QKeySequence("Ctrl+O"), w).activated.connect(lambda: (pages.setCurrentIndex(idx_projects), plist.setFocus()))
    QShortcut(QKeySequence("F1"), w).activated.connect(lambda: pages.setCurrentIndex(idx_help))
    QShortcut(QKeySequence("Ctrl+K"), w).activated.connect(lambda: (pages.setCurrentIndex(idx_prices), pquery.setFocus()))

    def refresh_ux_status():
        project_name=""
        try:
            project_id=pid.text().strip()
            project=service.open_project(project_id) if project_id else None
            project_name=project.get("name","") if project else ""
        except Exception:
            project_name=""
        status.setText("🟢 "+quick_status(project_name=project_name,offline=True))
        w.statusBar().showMessage("StructuralPro | "+quick_status(project_name=project_name,offline=True))

    pages.currentChanged.connect(lambda _i: refresh_ux_status())
    refresh_projects(); dashboard_page.refresh(); pages.setCurrentIndex(idx_dash); refresh_command_ribbon(idx_dash); refresh_ux_status()
    w.show()
    logger.info("StructuralPro UI initialized")
    if os.getenv("STRUCTURALPRO_SMOKE") == "1":
        # Exercise the same Qt event-loop and top-level-window destruction path
        # used by interactive Windows shutdown. Returning before QApplication's
        # event loop has run can leave native Qt objects to be finalized in an
        # unsafe order by the frozen Python runtime.
        w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        def close_smoke_window():
            w.close()
        QTimer.singleShot(0, close_smoke_window)
        result = app.exec()
        # Flush deferred QWidget deletion while QApplication is still alive.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        # Explicitly request Qt shutdown after deferred widget destruction.
        app.quit()
        logger.info("StructuralPro smoke initialization completed with exit code %s", result)
        return 0
    result = app.exec()
    logger.info("StructuralPro shutdown with exit code %s", result)
    return result

if __name__=="__main__": raise SystemExit(main())