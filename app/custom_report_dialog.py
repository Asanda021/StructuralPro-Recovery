"""Real RTL report-template editor over the read-only E7 service."""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QLineEdit,QComboBox,QListWidget,QListWidgetItem,QCheckBox,QPushButton,
    QTableWidget,QTableWidgetItem,QFileDialog,QScrollArea,QWidget,QTabWidget,QAbstractItemView)
from core.reports.custom_batch import (TemplateStore,FIELDS,validate_template,
    preview_custom_report,export_custom_report_batch,migrate_template_v1)
from core.reports.designer import ReportLayout

class CustomReportDialog(QDialog):
    def __init__(self,service,project_id,parent=None,*,legacy_layout=None):
        super().__init__(parent)
        self.setObjectName("P7CustomReportDialog");self.setWindowTitle("گزارش‌ساز و صدور گروهی")
        self.setLayoutDirection(Qt.RightToLeft);self.resize(950,740)
        self.service=service;self.project_id=project_id;self.snapshot=service.open_project(project_id)
        self.store=TemplateStore(service,project_id);self.selected_version=0;self.selected_id=None
        self.last_destination=None;self._logo=None
        root=QVBoxLayout(self);self.tabs=QTabWidget();root.addWidget(self.tabs)
        editor=QWidget();form=QFormLayout(editor);form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(editor);self.tabs.addTab(scroll,"قالب و فیلترها")
        self.templates=QComboBox();self.load_button=QPushButton("بازیابی قالب")
        row=QWidget();bar=QHBoxLayout(row);bar.addWidget(self.templates,1);bar.addWidget(self.load_button);form.addRow("قالب ذخیره‌شده",row)
        self.template_id=QLineEdit("default");self.title=QLineEdit("گزارش متره مستند")
        self.header=QLineEdit();self.footer=QLineEdit();self.actor=QLineEdit();self.reason=QLineEdit()
        for label,field in (("شناسه کوتاه قالب",self.template_id),("عنوان",self.title),("سربرگ",self.header),("پابرگ",self.footer),("ثبت‌کننده",self.actor),("علت تغییر قالب",self.reason)):form.addRow(label,field)
        self.kind=QComboBox()
        for label,value in (("صورت‌مقادیر بدون قیمت","boq"),("ریزمتره","takeoff"),("برآورد با قیمت تأییدشده","estimate")):self.kind.addItem(label,value)
        form.addRow("نوع گزارش",self.kind)
        self.columns=QListWidget();self.columns.setDragDropMode(QAbstractItemView.InternalMove);self.columns.setMaximumHeight(145)
        defaults=["item_no","item_code","description","quantity","unit","source_id"]
        for key in defaults+[k for k in FIELDS if k not in defaults]:
            item=QListWidgetItem(FIELDS[key]);item.setData(Qt.UserRole,key);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if key in defaults else Qt.Unchecked);self.columns.addItem(item)
        form.addRow("ستون‌ها؛ ترتیب با کشیدن",self.columns)
        self.group=QComboBox()
        for label,key in (("بدون گروه‌بندی",""),("طبقه","floor"),("رشته","discipline"),("زون","zone"),("واحد","unit"),("فصل","chapter")):self.group.addItem(label,key)
        form.addRow("گروه‌بندی",self.group)
        self.floors=self._selector(self.snapshot.get("floors",[]));form.addRow("طبقات؛ خالی یعنی همه",self.floors)
        self.disciplines=self._selector(self.snapshot.get("disciplines",[]));form.addRow("رشته‌ها؛ خالی یعنی همه",self.disciplines)
        self.zones=self._selector(self.snapshot.get("zones",[]));form.addRow("زون‌ها؛ خالی یعنی همه",self.zones)
        self.revision=QLineEdit();self.revision.setPlaceholderText("نسخه پروژه؛ خالی یعنی جاری");form.addRow("فیلتر نسخه",self.revision)
        self.paper=QComboBox();self.paper.addItems(["A4","A3"]);form.addRow("اندازه کاغذ",self.paper)
        self.orientation=QComboBox();self.orientation.addItem("افقی","landscape");self.orientation.addItem("عمودی","portrait");form.addRow("جهت چاپ",self.orientation)
        self.totals=QCheckBox("جمع کل و زیرجمع با تفکیک واحد");self.totals.setChecked(True)
        self.sources=QCheckBox("نمایش ستون منبع");self.sources.setChecked(True)
        self.separate=QCheckBox("هر طبقه منتخب، یک گزارش جداگانه");self.separate.setChecked(True)
        for check in (self.totals,self.sources,self.separate):form.addRow(check)
        self.logo_label=QLabel("لوگو انتخاب نشده است");logo_row=QWidget();logo_bar=QHBoxLayout(logo_row)
        self.logo_button=QPushButton("انتخاب لوگوی PNG");clear=QPushButton("حذف لوگو")
        for control in (self.logo_label,self.logo_button,clear):logo_bar.addWidget(control)
        form.addRow("نشان پروژه",logo_row)
        self.preview_table=QTableWidget();self.preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.tabs.addTab(self.preview_table,"پیش‌نمایش")
        self.status=QLabel("داده‌های گزارش فقط خوانده می‌شوند؛ برآورد دوباره محاسبه نمی‌شود.");self.status.setWordWrap(True);root.addWidget(self.status)
        buttons=QHBoxLayout();root.addLayout(buttons)
        self.preview_button=QPushButton("پیش‌نمایش");self.save_button=QPushButton("ذخیره نسخه قالب");self.export_button=QPushButton("صدور گروهی چهارقالبی")
        for button,name,handler in ((self.preview_button,"P7ReportPreview",self._preview),(self.save_button,"P7ReportSaveTemplate",self._save),(self.load_button,"P7ReportLoadTemplate",self._load),(self.export_button,"P7ReportExportBatch",self._export)):
            button.setObjectName(name);button.clicked.connect(lambda checked=False,fn=handler:self._run(fn))
        for button in (self.preview_button,self.save_button,self.export_button):buttons.addWidget(button)
        self.logo_button.clicked.connect(lambda:self._run(self._choose_logo));clear.clicked.connect(self._clear_logo)
        self._refresh()
        if legacy_layout is not None and not self.store.list_versions():
            layout=asdict(ReportLayout());layout.update(legacy_layout)
            self._show(migrate_template_v1(dict(schema_version=1,template_id="legacy",version=1,layout=layout)))
            self.status.setText("چیدمان قدیمی بازخوانی شد؛ برای مهاجرت صریح، نسخه قالب را ذخیره کنید.")

    def _selector(self,records):
        widget=QListWidget();widget.setMaximumHeight(80)
        for record in records:
            item=QListWidgetItem(str(record.get("name") or record.get("title") or record["id"]));item.setData(Qt.UserRole,str(record["id"]));item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);widget.addItem(item)
        return widget

    def _run(self,fn):
        try:fn()
        except Exception as exc:
            self.preview_table.setRowCount(0);self.status.setText("خطا: "+str(exc));self.last_destination=None

    def _checked(self,widget):
        return [widget.item(i).data(Qt.UserRole) for i in range(widget.count()) if widget.item(i).checkState()==Qt.Checked]

    def _filters(self):
        result={}
        for key,widget in (("floor",self.floors),("discipline",self.disciplines),("zone",self.zones)):
            values=self._checked(widget)
            if values:result[key]=values
        if self.revision.text().strip():result["revision"]=[self.revision.text().strip()]
        return result

    def _candidate(self,version=None):
        return validate_template(dict(schema_version=2,template_id=self.template_id.text().strip(),version=version or self.selected_version or 1,report_type=self.kind.currentData(),
            layout=asdict(ReportLayout(title=self.title.text(),columns=self._checked(self.columns),group_by=self.group.currentData(),header=self.header.text(),footer=self.footer.text())),
            filters=self._filters(),page_format=self.paper.currentText(),orientation=self.orientation.currentData(),show_source=self.sources.isChecked(),include_totals=self.totals.isChecked(),logo=self._logo))

    def _refresh(self):
        self.templates.clear();self.templates.addItem("انتخاب قالب",None)
        for id,version in self.store.list_versions():self.templates.addItem(id+" / نسخه "+str(version),(id,version))

    def _show(self,t):
        self.template_id.setText(t["template_id"]);self.title.setText(t["layout"]["title"]);self.header.setText(t["layout"]["header"]);self.footer.setText(t["layout"]["footer"])
        self.kind.setCurrentIndex(self.kind.findData(t["report_type"]));self.group.setCurrentIndex(self.group.findData(t["layout"]["group_by"]));self.paper.setCurrentText(t["page_format"]);self.orientation.setCurrentIndex(self.orientation.findData(t["orientation"]))
        self.columns.clear()
        for key in t["layout"]["columns"]+[k for k in FIELDS if k not in t["layout"]["columns"]]:
            item=QListWidgetItem(FIELDS[key]);item.setData(Qt.UserRole,key);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if key in t["layout"]["columns"] else Qt.Unchecked);self.columns.addItem(item)
        for key,widget in (("floor",self.floors),("discipline",self.disciplines),("zone",self.zones)):
            known={widget.item(i).data(Qt.UserRole) for i in range(widget.count())}
            if set(t["filters"].get(key,[]))-known:raise ValueError("فیلتر قالب به شناسه ناموجود ارجاع دارد")
            for i in range(widget.count()):widget.item(i).setCheckState(Qt.Checked if widget.item(i).data(Qt.UserRole) in t["filters"].get(key,[]) else Qt.Unchecked)
        self.revision.setText((t["filters"].get("revision") or [""])[0]);self.sources.setChecked(t["show_source"]);self.totals.setChecked(t["include_totals"])
        self._logo=t["logo"];self.logo_label.setText("لوگوی معتبر پروژه" if self._logo else "لوگو انتخاب نشده است")

    def _load(self):
        selected=self.templates.currentData()
        if selected is None:raise ValueError("یک قالب را انتخاب کنید")
        record=self.store.load(*selected);self._show(record["template"]);self.selected_id,self.selected_version=selected;self.status.setText("قالب و نسخه ذخیره‌شده بازیابی شد.")

    def _save(self):
        id=self.template_id.text().strip();next_version=1+max((v for key,v in self.store.list_versions() if key==id),default=0)
        record=self.store.save(self._candidate(next_version),actor=self.actor.text(),reason=self.reason.text())
        self.selected_id=id;self.selected_version=record["template"]["version"];self._refresh()
        self.templates.setCurrentIndex(next(i for i in range(self.templates.count()) if self.templates.itemData(i)==(id,self.selected_version)))
        self.status.setText("نسخه "+str(self.selected_version)+" قالب ذخیره شد.")

    def _preview(self):
        candidate=self._candidate();result=preview_custom_report(self.service,project_id=self.project_id,expected_project_version=self.snapshot["_meta"]["version"],template=candidate)
        keys=candidate["layout"]["columns"];self.preview_table.setColumnCount(len(keys));self.preview_table.setHorizontalHeaderLabels([FIELDS[k] for k in keys]);self.preview_table.setRowCount(len(result["rows"]))
        for i,row in enumerate(result["rows"]):
            for j,key in enumerate(keys):self.preview_table.setItem(i,j,QTableWidgetItem(str(row.get(key) if row.get(key) is not None else "")))
        totals=result["summary"].get("report_totals",{})
        self.tabs.setCurrentIndex(1);self.status.setText("پیش‌نمایش داده ثبت‌شده؛ "+"، ".join(str(k)+": "+str(v) for k,v in totals.items()))

    def _export(self):
        if not self.selected_id or self.template_id.text().strip()!=self.selected_id:raise ValueError("ابتدا قالب را ذخیره یا بازیابی کنید")
        saved=self.store.load(self.selected_id,self.selected_version)["template"];current=self._candidate(self.selected_version)
        if {k:v for k,v in saved.items() if k!="filters"}!={k:v for k,v in current.items() if k!="filters"}:raise ValueError("تغییرات قالب را پیش از صدور ذخیره کنید")
        parent=QFileDialog.getExistingDirectory(self,"پوشه خروجی بسته گزارش")
        if not parent:return
        filters=self._filters();parts=[filters]
        if self.separate.isChecked() and filters.get("floor"):parts=[filters|{"floor":[floor]} for floor in filters["floor"]]
        requests=tuple(dict(template_id=self.selected_id,version=self.selected_version,filters=f) for f in parts)
        destination=Path(parent)/("reports-"+datetime.now().strftime("%Y%m%d-%H%M%S")+"-"+uuid4().hex[:6])
        result=export_custom_report_batch(self.service,project_id=self.project_id,expected_project_version=self.snapshot["_meta"]["version"],requests=requests,destination=destination)
        self.last_destination=result["destination"];self.status.setText("بسته گزارش با موفقیت صادر شد: "+result["destination"])

    def _choose_logo(self):
        path=QFileDialog.getOpenFileName(self,"انتخاب لوگو","","PNG (*.png)")[0]
        if path:self._logo=self.store.import_logo(path);self.logo_label.setText("لوگوی معتبر پروژه انتخاب شد")

    def _clear_logo(self):
        self._logo=None;self.logo_label.setText("لوگو انتخاب نشده است")
