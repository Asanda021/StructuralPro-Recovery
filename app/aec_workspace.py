"""Functional AEC takeoff workspaces: concrete/steel/architecture and real roof quantity rules."""
from __future__ import annotations
from core.takeoff.assembly import calculate_assembly
from core.takeoff.manual_input import parse_manual_batch
from core.takeoff.assembly_templates import AssemblyTemplateLibrary
from core.takeoff.units import normalize_unit
from uuid import uuid4
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QCheckBox,QComboBox,QDoubleSpinBox,QFormLayout,QGroupBox,QLabel,QLineEdit,QMessageBox,
    QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget,QHeaderView,QScrollArea
)

ITEMS={
"architecture":[
("wall","دیوار",("length","height","openings")),("slab","کف / سطح",("length","width")),
("plaster","گچ‌کاری",("length","height","openings","count")),("tile","کاشی / سرامیک",("length","height","openings","waste")),
("roof_insulation","عایق‌کاری بام",("length","width","layers")),("door","درب",("count",)),("window","پنجره",("count",)),
("facade","نما",("length","height","openings")),("ceiling","سقف کاذب",("length","width","count"))],
"structural_concrete":[
("footing_concrete","پی / فونداسیون بتنی",("length","width","thickness","count")),
("tie_beam","شناژ / کلاف بتنی",("length","width","depth","count")),
("column","ستون بتنی",("width","depth","height","count")),("beam","تیر بتنی",("length","width","depth","count")),
("shear_wall","دیوار برشی بتنی",("length","thickness","height","count")),
("stair_concrete","پله بتنی",("sloped_length","width","waist_thickness","count")),
("formwork","قالب‌بندی",("perimeter","height","count")),("rebar","آرماتور با دیتایل صریح",("length","unit_weight","count","diameter_mm","bend_length","hook_length","lap_length")),
("solid_slab_roof","سقف دال بتنی توپر / دال تخت — حجم بتن",("length","width","thickness","count")),
("joist_block_roof","سقف تیرچه‌بلوک — حجم بتن",("length","width","topping_thickness","joist_spacing","joist_width","joist_depth","count")),
("joist_foam_roof","سقف تیرچه‌فوم — حجم بتن",("length","width","topping_thickness","joist_spacing","joist_width","joist_depth","count")),
("hollow_core_roof","سقف دال مجوف — حجم بتن",("length","width","thickness","void_diameter","void_count","count")),
("waffle_roof","سقف وافل — حجم بتن",("length","width","top_thickness","spacing_x","spacing_y","rib_width","rib_depth","count")),
("uboot_roof","سقف یوبوت — حجم بتن خالص",("length","width","thickness","void_length","void_width","void_height","void_count","count")),
("cobiax_roof","سقف کوبیاکس — حجم بتن خالص",("length","width","thickness","void_volume","void_count","count"))],
"structural_steel":[
("steel","عضو فولادی / تیر / ستون",("length","unit_weight","count")),
("steel_roof_deck_area","سقف عرشه فولادی — مساحت عرشه",("length","width","count")),
("steel_roof_deck_weight","سقف عرشه فولادی — وزن ورق",("length","width","sheet_weight","count")),
("steel_roof_composite_concrete","سقف کامپوزیت — حجم بتن",("length","width","thickness","count")),
("steel_roof_composite_deck","سقف کامپوزیت — وزن ورق",("length","width","sheet_weight","count")),
("kromit_roof","سقف تیرچه کرومیت — وزن تیرچه",("joist_length","joist_unit_weight","joist_count","count")),
("steel_truss_roof","سقف خرپایی فولادی — وزن فولاد",("steel_length","unit_weight","count")),
("steel_sandwich_roof","سقف ساندویچ‌پنل روی سازه فولادی — مساحت پنل",("length","width","count"))],
"masonry":[("wall","دیوار بنایی",("length","height","openings")),("block_wall","دیوار بلوکی — Assembly",("length","height","thickness","openings","block_length","block_height","block_thickness","joint_thickness","cement_parts","sand_parts","block_waste_factor","mortar_waste_factor"))],
"mechanical":[("pipe","لوله",("length","count")),("duct","کانال",("length","count")),("duct_area","سطح کانال",("width","height","length")),("insulation","عایق لوله",("diameter","length")),("equipment","تجهیزات",("count",)),("valve","شیر / اتصال",("count",))],
"electrical":[("cable","کابل / سیم",("length","count")),("conduit","لوله برق",("length","count")),("panel","تابلو",("count",)),("light","روشنایی",("count",)),("socket","پریز",("count",)),("earthing","ارت",("length",)),("cable_tray","سینی کابل",("length","count"))],
"civil":[("excavation","خاکبرداری",("length","width","depth")),("backfill","خاکریزی",("excavation","deductions")),("paving","بتن محوطه",("length","width","thickness")),("asphalt","آسفالت",("length","width","thickness")),("curb","جدول",("length","count")),("drainage","زهکشی",("length",)),("fence_wall","دیوارکشی",("length","height"))],
"renovation":[("demolition","تخریب",("length","width","height","count")),("facade","نما / مرمت نما",("length","height","openings")),("screed","کف‌سازی",("length","width","thickness","count")),("ceiling","سقف کاذب",("length","width","count"))],
}

FIELDS={
"length":"طول","width":"عرض","height":"ارتفاع","depth":"عمق","thickness":"ضخامت","perimeter":"محیط",
"void_volume":"حجم واقعی هر حفره طبق مشخصات (m³)","diameter_mm":"قطر میلگرد (mm)",
"bend_length":"طول اضافه خم (m)","hook_length":"طول اضافه قلاب (m)","lap_length":"طول اضافه وصله (m)",
"sloped_length":"طول مایل پله (m)","waist_thickness":"ضخامت دال مایل پله (m)",
"count":"تعداد","unit_weight":"وزن واحد (kg/m)","openings":"کسر بازشو (m²)","waste":"ضریب پرت",
"layers":"تعداد لایه","diameter":"قطر","excavation":"حجم خاکبرداری","deductions":"کسرها",
"topping_thickness":"ضخامت بتن رویه","joist_spacing":"فاصله آکس تیرچه","joist_width":"عرض تیرچه",
"joist_depth":"عمق مؤثر تیرچه","void_diameter":"قطر فضای خالی","void_count":"تعداد فضای خالی",
"top_thickness":"ضخامت رویه","spacing_x":"فاصله آکس در جهت X","spacing_y":"فاصله آکس در جهت Y",
"rib_width":"عرض تیرچه وافل","rib_depth":"عمق مؤثر تیرچه وافل","void_length":"طول فضای خالی",
"void_width":"عرض فضای خالی","void_height":"ارتفاع فضای خالی","sheet_weight":"وزن ورق (kg/m²)",
"joist_length":"طول تیرچه","joist_unit_weight":"وزن واحد تیرچه (kg/m)","joist_count":"تعداد تیرچه",
"steel_length":"طول کل فولاد","block_length":"طول بلوک","block_height":"ارتفاع بلوک","block_thickness":"ضخامت بلوک",
"joint_thickness":"ضخامت بند ملات","cement_parts":"سهم سیمان در ملات","sand_parts":"سهم ماسه در ملات",
"block_waste_factor":"پرت تأمین بلوک","mortar_waste_factor":"پرت تأمین ملات","foam_length":"طول بلوک یونولیت",
"foam_width":"عرض بلوک یونولیت","foam_height":"ارتفاع بلوک یونولیت","mesh_unit_weight":"وزن واحد مش (kg/m²)",
}

ITEM_DOMAINS={"block_wall":"building","footing_concrete":"advanced","steel":"advanced","steel_roof_deck_area":"advanced",
"steel_roof_deck_weight":"advanced","steel_roof_composite_concrete":"building",
"steel_roof_composite_deck":"advanced","kromit_roof":"advanced","steel_truss_roof":"advanced",
"steel_sandwich_roof":"advanced","facade":"advanced","ceiling":"advanced","screed":"advanced","demolition":"advanced"}

def build_aec_workspace(service,catalog,*,title,description,domain,key,status_callback=None):
    root=QWidget(); root.setLayoutDirection(Qt.LayoutDirection.RightToLeft); root.setObjectName("AECWorkspace"); outer=QVBoxLayout(root); outer.setSpacing(14)
    h=QLabel(title); h.setObjectName("PageTitle"); d=QLabel(description); d.setObjectName("PageDescription"); d.setWordWrap(True)
    outer.addWidget(h); outer.addWidget(d)
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
    grid.addRow("پروژه",project); grid.addRow("آیتم / نوع سقف",item); grid.addRow("کد فهرست‌بها (اختیاری)",price)
    floor=QLineEdit(); floor.setObjectName("TakeoffFloor"); floor.setPlaceholderText("طبقه / تراز؛ برای Assembly الزامی")
    location=QLineEdit(); location.setObjectName("TakeoffLocation"); location.setPlaceholderText("شناسه ثابت عضو / محل؛ برای Assembly الزامی")
    detail=QLineEdit(); detail.setObjectName("TakeoffDetailReference"); detail.setPlaceholderText("مرجع دیتایل میلگرد یا مشخصات حجم حفره")
    grid.addRow("طبقه / تراز",floor); grid.addRow("شناسه ثابت عضو / محل",location); grid.addRow("مرجع مشخصات معتبر",detail)
    assembly_mode=QCheckBox("متره به‌صورت Assembly (عملیات → اجزای مستقل)")
    grid.addRow("روش متره",assembly_mode)
    fields={}
    for name,label in FIELDS.items():
        w=QDoubleSpinBox(); w.setDecimals(4); w.setRange(0,1000000000); w.setSingleStep(.1)
        w.setObjectName("TakeoffField_"+name)
        w.setValue(1 if name in {"count","layers","waste"} else 0); fields[name]=w; grid.addRow(label,w)
    calc=QPushButton("محاسبه و ثبت واقعی"); calc.setObjectName("PrimaryAction"); grid.addRow(calc)
    form_scroll=QScrollArea(); form_scroll.setObjectName("TakeoffFormScroll")
    form_scroll.setWidgetResizable(True); form_scroll.setWidget(box); outer.addWidget(form_scroll,2)
    note=QLabel("هیچ ضریب یا مقدار ثابت برای سقف‌های غیر یکنواخت اعمال نمی‌شود؛ ابعاد واقعی نقشه/مشخصات فنی باید وارد شود.")
    note.setObjectName("DashboardNotice"); note.setWordWrap(True); outer.addWidget(note)
    result=QLabel("نتیجه پس از محاسبه در پروژه و BOQ ثبت می‌شود."); result.setWordWrap(True); outer.addWidget(result)
    table=QTableWidget(0,8); table.setHorizontalHeaderLabels(["شناسه","آیتم","مقدار","واحد","فرمول","کد فهرست‌بها","منبع","هشدار"]); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); outer.addWidget(table,1)
    ASSEMBLY_CODES={"block_wall","joist_foam_roof","joist_block_roof"}
    ASSEMBLY_MAPPING={"block_wall":"block_wall","joist_foam_roof":"joist_foam_roof_assembly","joist_block_roof":"joist_block_roof_assembly"}
    def update_fields():
        active=set(specs[item.currentData()])
        if assembly_mode.isChecked() and item.currentData() in ASSEMBLY_CODES:
            if item.currentData() != "block_wall": active.update({"foam_length","foam_width","foam_height","mesh_unit_weight"})
        grid.setRowVisible(detail,item.currentData() in {"rebar","cobiax_roof"})
        for n,w in fields.items():
            w.setEnabled(n in active)
            grid.setRowVisible(w,n in active)
            if n not in active: w.setValue(0)
            elif n in {"count","layers","waste"} and w.value()==0: w.setValue(1)
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
        code=item.currentData(); params={n:float(w.value()) for n,w in fields.items() if w.isEnabled()}; params["member_code"]=code
        if code == "rebar": params["detail_ref"]=detail.text().strip()
        if code == "cobiax_roof": params["void_spec_ref"]=detail.text().strip()
        pc=price.text().strip()
        if pc:
            resolved=catalog.resolve(pc)
            if resolved.get("status")!="ok":
                QMessageBox.warning(root,"فهرست‌بها","کد در فهرست‌بهای واردشده پیدا نشد."); return
            params["price_code"]=pc; params["unit_price"]=resolved["unit_price"]
        else: params["price_code"]=None
        try:
            p=service.open_project(pid); source_id=f"manual:{key}:{code}:{uuid4().hex}"
            if assembly_mode.isChecked() and code in ASSEMBLY_CODES:
                if pc:
                    raise ValueError("قیمت واحد مشترک برای اجزای ناهم‌واحد مجاز نیست؛ هر جزء باید مستقل به فهرست‌بها نگاشت شود.")
                if not floor.text().strip() or not location.text().strip():
                    raise ValueError("طبقه و شناسه ثابت محل برای Assembly الزامی است.")
                template=AssemblyTemplateLibrary().get(ASSEMBLY_MAPPING[code])
                inputs={n:v for n,v in params.items() if n in template.required_inputs+template.optional_inputs}
                # The same engine previews and the existing service persists all components atomically.
                ar=calculate_assembly(template.code, **inputs)
                if not ar.complete:
                    QMessageBox.warning(root,"Assembly ناقص", "برای متره مرکب این مشخصات لازم است:\n" + "\n".join(ar.missing_inputs))
                    return
                saved=service.add_assembly_takeoff(pid,assembly_code=ar.code,inputs=inputs,
                    floor_id=floor.text().strip(),location_id=location.text().strip(),description=labels[code])
                result.setText(f"🟢 Assembly ثبت شد | {ar.title} | {len(saved['rows'])} جزء مستقل")
            else:
                effective_domain=ITEM_DOMAINS.get(code,domain)
                preview=service.takeoff.calculate(effective_domain,code,**params)
                if pc and normalize_unit(resolved["item"].unit) != normalize_unit(preview.unit):
                    raise ValueError("واحد فهرست‌بها با واحد متره سازگار نیست.")
                row=service.add_takeoff(pid,effective_domain,code,source_id=source_id,description=labels[code],
                    system=floor.text().strip(),manual_location_id=location.text().strip(),**params)
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
                field.setValue(1 if name in {"count","layers","waste"} and field.isEnabled() else 0)
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
