"""Functional AEC takeoff workspaces: concrete/steel/architecture and real roof quantity rules."""
from __future__ import annotations
from core.takeoff.assembly import calculate_assembly
from core.takeoff.manual_input import parse_manual_batch

from PySide6.QtWidgets import (
    QCheckBox,QComboBox,QDoubleSpinBox,QFormLayout,QGroupBox,QLabel,QLineEdit,QMessageBox,
    QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget,QHeaderView,QScrollArea
)

ITEMS={
"architecture":[
("wall","دیوار",("length","height","openings","count")),("slab","کف / سطح",("length","width")),
("plaster","گچ‌کاری",("length","height","openings","count")),("tile","کاشی / سرامیک",("length","height","openings","waste")),
("roof_insulation","عایق‌کاری بام",("length","width","layers")),("door","درب",("count",)),("window","پنجره",("count",)),
("facade","نما",("length","height","openings","count")),("ceiling","سقف کاذب",("length","width","count"))],
"structural_concrete":[
("footing_concrete","پی / فونداسیون بتنی",("length","width","thickness","count")),
("tie_beam","شناژ / کلاف بتنی",("length","width","depth","count")),
("column","ستون بتنی",("width","depth","height","count")),("beam","تیر بتنی",("length","width","depth","count")),
("shear_wall","دیوار برشی بتنی",("length","thickness","height","count")),
("stair_concrete","پله بتنی",("sloped_length","width","waist_thickness","count")),
("formwork","قالب‌بندی",("perimeter","height","count")),("rebar","آرماتور",("length","unit_weight","count")),
("solid_slab_roof","سقف دال بتنی توپر / دال تخت — حجم بتن",("length","width","thickness","count")),
("joist_block_roof","سقف تیرچه‌بلوک — حجم بتن",("length","width","topping_thickness","joist_spacing","joist_width","joist_depth","joist_count","count")),
("joist_foam_roof","سقف تیرچه‌فوم — حجم بتن",("length","width","topping_thickness","joist_spacing","joist_width","joist_depth","joist_count","count")),
("hollow_core_roof","سقف دال مجوف — حجم بتن",("length","width","thickness","void_diameter","void_count","count")),
("waffle_roof","سقف وافل — حجم بتن",("length","width","top_thickness","spacing_x","spacing_y","rib_width","rib_depth","count")),
("uboot_roof","سقف یوبوت — حجم بتن خالص",("length","width","thickness","void_length","void_width","void_height","void_count","count")),
("cobiax_roof","سقف کوبیاکس — حجم بتن خالص",("length","width","thickness","void_length","void_width","void_height","void_count","count"))],
"structural_steel":[
("steel","عضو فولادی / تیر / ستون",("length","unit_weight","count")),
("steel_roof_deck_area","سقف عرشه فولادی — مساحت عرشه",("length","width","count")),
("steel_roof_deck_weight","سقف عرشه فولادی — وزن ورق",("length","width","sheet_weight","count")),
("steel_roof_composite_concrete","سقف کامپوزیت — حجم بتن",("length","width","thickness","count")),
("steel_roof_composite_deck","سقف کامپوزیت — وزن ورق",("length","width","sheet_weight","count")),
("kromit_roof","سقف تیرچه کرومیت — وزن تیرچه",("joist_length","joist_unit_weight","joist_count","count")),
("steel_truss_roof","سقف خرپایی فولادی — وزن فولاد",("steel_length","unit_weight","count")),
("steel_sandwich_roof","سقف ساندویچ‌پنل روی سازه فولادی — مساحت پنل",("length","width","count"))],
"masonry":[("wall","دیوار بنایی",("length","height","openings","count")),("block_wall","دیوار بلوکی — Assembly",("length","height","thickness","openings","block_length","block_height","block_thickness","joint_thickness","cement_parts","sand_parts","block_waste_factor","mortar_waste_factor"))],
"mechanical":[("pipe","لوله",("length","count")),("duct","کانال",("length","count")),("duct_area","سطح کانال",("width","height","length")),("insulation","عایق لوله",("diameter","length")),("equipment","تجهیزات",("count",)),("valve","شیر / اتصال",("count",))],
"electrical":[("cable","کابل / سیم",("length","count")),("conduit","لوله برق",("length","count")),("panel","تابلو",("count",)),("light","روشنایی",("count",)),("socket","پریز",("count",)),("earthing","ارت",("length",)),("cable_tray","سینی کابل",("length","count"))],
"civil":[("excavation","خاکبرداری",("length","width","depth")),("backfill","خاکریزی",("excavation","deductions")),("paving","بتن محوطه",("length","width","thickness")),("asphalt","آسفالت",("length","width","thickness")),("curb","جدول",("length","count")),("drainage","زهکشی",("length",)),("fence_wall","دیوارکشی",("length","height"))],
"renovation":[("demolition","تخریب",("length","width","height","count")),("facade","نما / مرمت نما",("length","height","openings","count")),("screed","کف‌سازی",("length","width","thickness","count")),("ceiling","سقف کاذب",("length","width","count"))],
}

FIELDS={
"length":"طول","width":"عرض","height":"ارتفاع","depth":"عمق","thickness":"ضخامت","perimeter":"محیط",
"sloped_length":"طول شیب‌دار واقعی پله (متر)","waist_thickness":"ضخامت واقعی دال شیب‌دار (متر)",
"count":"تعداد","unit_weight":"وزن واحد (kg/m)","openings":"کسر بازشو (m²)","waste":"ضریب پرت",
"layers":"تعداد لایه","diameter":"قطر","excavation":"حجم خاکبرداری","deductions":"کسرها",
"topping_thickness":"ضخامت بتن رویه","joist_spacing":"فاصله آکس تیرچه","joist_width":"عرض تیرچه",
"joist_depth":"عمق مؤثر تیرچه","void_diameter":"قطر فضای خالی","void_count":"تعداد فضای خالی",
"top_thickness":"ضخامت رویه","spacing_x":"فاصله آکس در جهت X","spacing_y":"فاصله آکس در جهت Y",
"rib_width":"عرض تیرچه وافل","rib_depth":"عمق مؤثر تیرچه وافل","void_length":"طول فضای خالی",
"void_width":"عرض فضای خالی","void_height":"ارتفاع فضای خالی","sheet_weight":"وزن ورق (kg/m²)",
"joist_length":"طول تیرچه","joist_unit_weight":"وزن واحد تیرچه (kg/m)","joist_count":"تعداد تیرچه",
"steel_length":"طول کل فولاد","block_length":"طول بلوک","block_width":"عرض واقعی بلوک سقفی","block_height":"ارتفاع بلوک","block_thickness":"ضخامت بلوک",
"block_count":"تعداد واقعی بلوک سقفی","foam_count":"تعداد واقعی یونولیت",
"cast_rib_count":"تعداد جان بتنی درجا","cast_rib_length_m":"طول واقعی جان درجا",
"cast_rib_area_m2":"سطح مقطع واقعی جان درجا",
"joint_thickness":"ضخامت بند ملات","cement_parts":"سهم سیمان در ملات","sand_parts":"سهم ماسه در ملات",
"block_waste_factor":"پرت تأمین بلوک","mortar_waste_factor":"پرت تأمین ملات","foam_length":"طول بلوک یونولیت",
"foam_width":"عرض بلوک یونولیت","foam_height":"ارتفاع بلوک یونولیت","mesh_unit_weight":"وزن واحد مش (kg/m²)",
}

ITEM_DOMAINS={"block_wall":"building","footing_concrete":"advanced","steel":"advanced","steel_roof_deck_area":"advanced",
"steel_roof_deck_weight":"advanced","steel_roof_composite_concrete":"building",
"steel_roof_composite_deck":"advanced","kromit_roof":"advanced","steel_truss_roof":"advanced",
"facade":"advanced","ceiling":"advanced","demolition":"advanced","screed":"advanced","steel_sandwich_roof":"advanced"}

def build_aec_workspace(service,catalog,*,title,description,domain,key,status_callback=None):
    root=QWidget(); root.setObjectName("AECWorkspace"); outer=QVBoxLayout(root); outer.setSpacing(14)
    h=QLabel(title); h.setObjectName("PageTitle"); d=QLabel(description); d.setObjectName("PageDescription"); d.setWordWrap(True)
    outer.addWidget(h); outer.addWidget(d)
    complete_editor = QPushButton("متره دستی جامع و بازبینی‌شده همه خانواده‌های ابنیه")
    complete_editor.setObjectName("OpenAECReviewedManualEditor")
    outer.addWidget(complete_editor)
    def open_complete_editor():
        from app.reviewed_aec_manual_editor import open_reviewed_aec_editor
        open_reviewed_aec_editor(service, parent=root, project_id=project.text().strip(),
                                 floor_id=floor_input.text().strip())
        refresh()
    complete_editor.clicked.connect(open_complete_editor)
    if key == "structural_concrete":
        structural_editor = QPushButton("فرم تخصصی متره دستی ستون، شناژ، پی و شمع")
        structural_editor.setObjectName("OpenReviewedStructuralEditor")
        outer.addWidget(structural_editor)
        def open_structural_editor():
            from app.reviewed_structural_manual_editor import open_manual_structural_editor
            open_manual_structural_editor(service, parent=root,
                project_id=project.text().strip(), floor_id=floor_input.text().strip())
            refresh()
        structural_editor.clicked.connect(open_structural_editor)
    quick=QGroupBox("⚡ متره سریع دستی — بدون فرم‌های طولانی")
    quick_layout=QVBoxLayout(quick)
    quick_input=QLineEdit()
    quick_input.setPlaceholderText("مثال: 12 ستون 50cmx50cm ارتفاع 3m")
    quick_apply=QPushButton("اعمال ورودی سریع")
    quick_hint=QLabel("ورودی فشرده را وارد کنید؛ فقط اطلاعات ناموجود را در فرم پایین تکمیل کنید.")
    quick_hint.setWordWrap(True)
    quick_layout.addWidget(quick_input); quick_layout.addWidget(quick_apply); quick_layout.addWidget(quick_hint)
    outer.addWidget(quick)
    box=QGroupBox("ریزمتره و محاسبه واقعی"); grid=QFormLayout(box)
    project=QLineEdit(); project.setPlaceholderText("شناسه پروژه موجود")
    project.setObjectName("TakeoffProject")
    item=QComboBox(); item.setObjectName("TakeoffItem"); price=QLineEdit(); price.setPlaceholderText("اختیاری؛ کد فهرست‌بهای واردشده توسط کاربر")
    specs={c:f for c,_,f in ITEMS[key]}; labels={c:l for c,l,_ in ITEMS[key]}
    for c,l,_ in ITEMS[key]: item.addItem(l,c)
    floor_input = QLineEdit()
    floor_input.setObjectName("TakeoffFloor")
    floor_input.setPlaceholderText("شناسه طبقه یا ناحیه واقعی")
    grid.addRow("پروژه",project)
    grid.addRow("طبقه / ناحیه",floor_input)
    evidence_id=QLineEdit()
    evidence_id.setObjectName("TakeoffLocation")
    evidence_id.setPlaceholderText("مرجع اندازه‌گیری و شماره برداشت دستی")
    grid.addRow("مرجع متره", evidence_id)
    reviewer=QLineEdit()
    reviewer.setObjectName("TakeoffReviewer")
    reviewer.setPlaceholderText("نام واقعی مسئول تأیید متره مرکب")
    grid.addRow("تأییدکننده متره", reviewer)
    mesh_source=QLineEdit()
    mesh_source.setPlaceholderText("شماره جدول یا دیتایل مش تأییدشده")
    grid.addRow("مرجع وزن مش", mesh_source)
    grid.addRow("آیتم / نوع سقف",item)
    grid.addRow("کد فهرست‌بها (اختیاری)",price)
    assembly_mode=QCheckBox("متره به‌صورت Assembly (عملیات → اجزای مستقل)")
    grid.addRow("روش متره",assembly_mode)
    fields={}
    for name,label in FIELDS.items():
        w=QDoubleSpinBox(); w.setDecimals(4); w.setRange(0,1000000000); w.setSingleStep(.1)
        w.setObjectName("TakeoffField_"+name)
        w.setValue(0); fields[name]=w; grid.addRow(label,w)
    calc=QPushButton("محاسبه و ثبت واقعی"); calc.setObjectName("PrimaryAction"); grid.addRow(calc)
    form_scroll=QScrollArea(); form_scroll.setObjectName("TakeoffFormScroll")
    form_scroll.setWidgetResizable(True); form_scroll.setWidget(box); outer.addWidget(form_scroll,2)
    note=QLabel("هیچ ضریب یا مقدار ثابت برای سقف‌های غیر یکنواخت اعمال نمی‌شود؛ ابعاد واقعی نقشه/مشخصات فنی باید وارد شود.")
    note.setObjectName("DashboardNotice"); note.setWordWrap(True); outer.addWidget(note)
    result=QLabel("نتیجه پس از محاسبه در پروژه و BOQ ثبت می‌شود."); result.setWordWrap(True); outer.addWidget(result)
    table=QTableWidget(0,8); table.setHorizontalHeaderLabels(["شناسه","آیتم","مقدار","واحد","فرمول","کد فهرست‌بها","منبع","هشدار"]); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); outer.addWidget(table,1)
    ASSEMBLY_CODES={"block_wall":"block_wall", "joist_foam_roof":"joist_foam_roof_assembly",
                    "joist_block_roof":"joist_block_roof_assembly"}
    def update_fields():
        active=set(specs[item.currentData()])
        if assembly_mode.isChecked() and item.currentData() in ASSEMBLY_CODES:
            from core.takeoff.assembly_templates import AssemblyTemplateLibrary
            template=AssemblyTemplateLibrary().get(ASSEMBLY_CODES[item.currentData()])
            active = set(template.required_inputs) | set(template.optional_inputs)
        grid.setRowVisible(mesh_source, assembly_mode.isChecked() and
            item.currentData() in {"joist_foam_roof", "joist_block_roof"})
        for n,w in fields.items():
            w.setEnabled(n in active)
            grid.setRowVisible(w,n in active)
            if n not in active: w.setValue(0)
            # Required values are never silently initialized to 1.
            # The user must enter a positive count/layer/factor before saving.
    def refresh():
        pid=project.text().strip()
        if not pid:return
        try:
            p=service.open_project(pid)
            if not p:return
            rows=[q for t in p.get("takeoffs",[]) for q in t.get("quantities",[]) if q.get("code")==item.currentData()]
            table.setRowCount(0)
            for i,q in enumerate(rows[-100:]):
                table.insertRow(i)
                vals=[q.get("id",""),q.get("title",""),q.get("amount",""),q.get("unit",""),q.get("formula",""),q.get("price_code","") or "—",q.get("source","manual"),q.get("warning","") or "—"]
                for j,v in enumerate(vals): table.setItem(i,j,QTableWidgetItem(str(v)))
        except Exception: pass
    def calculate():
        pid=project.text().strip()
        if not pid: QMessageBox.warning(root,"متره","ابتدا شناسه پروژه را وارد کنید."); return
        code=item.currentData()
        if assembly_mode.isChecked() and code not in ASSEMBLY_CODES:
            QMessageBox.warning(root, "عملیات مرکب", "برای این آیتم هنوز قالب مرکب تأییدشده وجود ندارد؛ تیک متره مرکب را بردارید")
            return
        if assembly_mode.isChecked():
            from core.takeoff.assembly_templates import AssemblyTemplateLibrary
            template=AssemblyTemplateLibrary().get(ASSEMBLY_CODES[code])
            required_fields=tuple(n for n in template.required_inputs if n in fields)
        else:
            required_fields=specs[code]
        unfilled=[n for n in required_fields if n not in {"openings"} and fields[n].value()<=0]
        if unfilled:
            QMessageBox.warning(root, "دیتایل ناقص", "این فیلدها باید صریح تکمیل شوند: " + "، ".join(unfilled))
            return
        params={n:float(w.value()) for n,w in fields.items() if w.isEnabled()}
        if code in {"waffle_roof","uboot_roof","cobiax_roof","hollow_core_roof","steel_roof_composite_concrete"}:
            QMessageBox.warning(root, "کنترل مهندسی", "این سقف به دیتایل‌های واقعی و مسیر متره تأییدشده نیاز دارد؛ محاسبه مستقیم تقریبی مسدود است.")
            return
        pid_floor=floor_input.text().strip()
        input_source=evidence_id.text().strip()
        if not pid_floor or not input_source:
            QMessageBox.warning(root,"مرجع متره","طبقه و مرجع واقعی برداشت دستی الزامی‌اند")
            return
        pc=price.text().strip()
        if pc:
            resolved=catalog.resolve(pc)
            if resolved.get("status")!="ok":
                QMessageBox.warning(root,"فهرست‌بها","کد در فهرست‌بهای واردشده پیدا نشد."); return
            params["price_code"]=pc; params["unit_price"]=resolved["unit_price"]
        else: params["price_code"]=None
        try:
            p=service.open_project(pid)
            source_id=f"manual:{pid}:{pid_floor}:{key}:{code}:{input_source}"
            if assembly_mode.isChecked() and code in ASSEMBLY_CODES:
                if pc:
                    raise ValueError("برای عملیات مرکب، هر ریزجزء کد فهرست‌بهای مستقل لازم دارد؛ یک قیمت برای تمام اجزا مجاز نیست")
                floor_id=pid_floor
                from core.takeoff.assembly_templates import AssemblyTemplateLibrary
                assembly_code=ASSEMBLY_CODES[code]
                template=AssemblyTemplateLibrary().get(assembly_code)
                allowed=set(template.required_inputs)|set(template.optional_inputs)
                inputs={k:v for k,v in params.items() if k in allowed and (k in template.required_inputs or v>0)}
                if "mesh_unit_weight" in inputs:
                    if not mesh_source.text().strip():
                        raise ValueError("مرجع وزن واحد مش باید صریح وارد شود")
                    inputs["mesh_unit_weight_source"]=mesh_source.text().strip()
                result_bundle=service.add_assembly_takeoff(
                    pid, assembly_code, inputs, floor_id=floor_id,
                    description=labels[code], measurement_source=input_source,
                    approved_by=reviewer.text().strip())
                saved=result_bundle["rows"]
                result.setText(f"🟢 عملیات مرکب ثبت شد | {labels[code]} | {len(saved)} ریزجزء مستقل")
            else:
                effective_domain=ITEM_DOMAINS.get(code,domain)
                preview=service.takeoff.calculate(effective_domain,code,**params)
                if pc:
                    from core.takeoff.units import normalize_unit
                    imported_unit = resolved.get("unit") or getattr(resolved.get("item"), "unit", None)
                    if not imported_unit or normalize_unit(imported_unit) != normalize_unit(preview.unit):
                        raise ValueError("واحد فهرست‌بها با واحد متره سازگار نیست.")
                row=service.add_takeoff(pid,effective_domain,code,source_id=source_id,
                                        system=pid_floor,description=labels[code],**params)
                q=row["quantities"][0]
                result.setText(f"🟢 ثبت شد | {labels[code]} | {q['amount']:,.4f} {q['unit']} | فرمول: {q['formula']}")
            refresh()
            if status_callback: status_callback(f"متره {title} ثبت شد")
        except Exception as exc: QMessageBox.critical(root,"خطای متره",str(exc))
    def apply_quick():
        try:
            entries=parse_manual_batch(quick_input.text())
            if len(entries)!=1:
                raise ValueError("در ورودی سریع این فرم، هر بار فقط یک ردیف وارد کنید؛ برای چند ردیف از متره دستی حرفه‌ای استفاده کنید.")
            first=entries[0]
            idx=item.findData(first.code)
            if idx < 0: raise ValueError("این عملیات در بخش فعلی وجود ندارد.")
            item.setCurrentIndex(idx)
            # A new draft must not inherit dimensions from the previous item.
            for name,field in fields.items():
                field.setValue(0)
            for name,value in first.params.items():
                if name in fields:
                    fields[name].setValue(value)
            for name in first.missing:
                if name in fields:
                    fields[name].setValue(0)
            missing=", ".join(first.missing)
            quick_hint.setText("🟢 ورودی سریع اعمال شد" + (f" | موارد لازم: {missing}" if missing else " | کامل و آماده محاسبه"))
        except Exception as exc:
            quick_hint.setText("🟡 " + str(exc))
    quick_apply.clicked.connect(apply_quick)
    item.currentIndexChanged.connect(update_fields); assembly_mode.toggled.connect(update_fields); calc.clicked.connect(calculate); project.editingFinished.connect(refresh); update_fields()
    return root
