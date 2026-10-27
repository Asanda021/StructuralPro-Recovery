"""E3 Windows RTL project-start dialog; preview and explicit atomic create."""
from PySide6.QtCore import Qt, QSettings
import json
from PySide6.QtWidgets import (
    QDialog,QVBoxLayout,QFormLayout,QLineEdit,QComboBox,QSpinBox,
    QLabel,QPlainTextEdit,QHBoxLayout,QPushButton
)
from core.projects.start_templates import TEMPLATES
from core.project.domains import DISCIPLINES


class ProjectStartWizard(QDialog):
    def __init__(self, service, *, parent=None, on_created=None, settings=None):
        super().__init__(parent)
        self.service=service
        self.settings=settings if settings is not None else QSettings('StructuralPro','StructuralPro')
        self.on_created=on_created
        self.created_project_id=None
        self.preview_data=None
        self.setObjectName("P6E3ProjectStartWizard")
        self.setWindowTitle("پروژه‌ساز مهندسی، پیش‌نمایش و تأیید")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(650,590)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel("قالب فقط ساختار اولیه پیشنهاد می‌دهد؛ هیچ متره، مقدار، نرخ، عضو یا مدت ساخته نمی‌شود."))
        form=QFormLayout();layout.addLayout(form)
        self.kind=QComboBox();self.kind.setObjectName("E3Template")
        self.kind.addItem("الگوی شروع را انتخاب کنید",None)
        for code,entry in TEMPLATES.items():self.kind.addItem(entry["title"],code)
        self._load_profiles()
        self.project_id=QLineEdit();self.project_id.setObjectName("E3ProjectId")
        self.name=QLineEdit();self.name.setObjectName("E3ProjectName")
        self.floors=QSpinBox();self.floors.setObjectName("E3FloorCount")
        self.floors.setRange(0,1000);self.floors.setValue(0)
        self.floor_names=QLineEdit();self.floor_names.setObjectName("E3FloorNames")
        self.floor_names.setPlaceholderText("اختیاری: نام هر طبقه با «،» جدا شود")
        self.profile_name=QLineEdit();self.profile_name.setObjectName("E3CustomProfileName")
        self.profile_disciplines=QLineEdit();self.profile_disciplines.setObjectName("E3CustomDisciplines")
        self.profile_disciplines.setPlaceholderText("کد رشته‌ها، با ویرگول جدا شود")
        for label,widget in (
            ("قالب ساختار",self.kind),("شناسه یکتای پروژه",self.project_id),
            ("نام واقعی پروژه",self.name),("تعداد طبقات صریح",self.floors),
            ("نام‌های اختصاصی طبقات",self.floor_names),("نام الگوی شخصی",self.profile_name),("رشته‌های شخصی",self.profile_disciplines)):
            form.addRow(label,widget)
        self.status=QLabel("برای آغاز، قالب و داده‌های صریح را وارد کنید.")
        self.status.setWordWrap(True);layout.addWidget(self.status)
        self.summary=QPlainTextEdit();self.summary.setReadOnly(True);layout.addWidget(self.summary,1)
        profile_actions=QHBoxLayout();layout.addLayout(profile_actions)
        self.profile_save=QPushButton("ذخیره الگوی شخصی")
        self.profile_save.setObjectName("E3SaveCustomProfile")
        self.profile_delete=QPushButton("حذف الگوی شخصی")
        self.profile_delete.setObjectName("E3DeleteCustomProfile")
        profile_actions.addWidget(self.profile_save);profile_actions.addWidget(self.profile_delete)
        actions=QHBoxLayout();layout.addLayout(actions)
        self.preview_button=QPushButton("پیش‌نمایش بدون ثبت")
        self.preview_button.setObjectName("E3Preview")
        self.create_button=QPushButton("تأیید و ایجاد پروژه")
        self.create_button.setObjectName("E3Create")
        self.create_button.setEnabled(False)
        self.cancel_button=QPushButton("انصراف")
        for w in (self.preview_button,self.create_button,self.cancel_button):actions.addWidget(w)
        for item in (self.project_id,self.name,self.floor_names,self.profile_disciplines):item.textChanged.connect(self.invalidate)
        self.floors.valueChanged.connect(self.invalidate)
        self.kind.currentIndexChanged.connect(self.choose_template)
        self.profile_save.clicked.connect(self.save_profile)
        self.profile_delete.clicked.connect(self.delete_profile)
        self.preview_button.clicked.connect(self.preview)
        self.create_button.clicked.connect(self.create)
        self.cancel_button.clicked.connect(self.reject)


    def _profiles(self):
        try:
            rows=json.loads(self.settings.value("e3/custom", "[]"))
            if not isinstance(rows,list) or len(rows)>30:raise ValueError("profile list")
            for p in rows:
                if (not isinstance(p,dict) or not isinstance(p.get("name"),str)
                    or not p["name"].strip() or len(p["name"])>80
                    or p.get("base") not in TEMPLATES
                    or not isinstance(p.get("disciplines"),list)
                    or not p["disciplines"] or len(set(p["disciplines"]))!=len(p["disciplines"])
                    or any(d not in DISCIPLINES for d in p["disciplines"])):
                    raise ValueError("profile data")
            if len({p["name"] for p in rows})!=len(rows):raise ValueError("duplicates")
            return rows
        except (TypeError, ValueError):return []

    def _load_profiles(self):
        for p in self._profiles():
            self.kind.addItem("شخصی: "+p["name"],"custom:"+p["name"])

    def _disciplines(self):
        raw=self.profile_disciplines.text().strip()
        if not raw:return None
        ds=[x.strip() for x in raw.replace("،",",").split(",")]
        if not all(ds) or len(set(ds))!=len(ds) or any(x not in DISCIPLINES for x in ds):
            raise ValueError("رشته‌های نامعتبر یا تکراری")
        return ds

    def _base(self):
        code=self.kind.currentData()
        if isinstance(code,str) and code.startswith("custom:"):
            p=next((x for x in self._profiles() if "custom:"+x["name"]==code),None)
            if not p:raise ValueError("الگوی شخصی حذف شده است")
            if self._disciplines()!=p["disciplines"]:
                raise ValueError("رشته‌ها تغییر کرده‌اند؛ الگو باید دوباره ذخیره شود")
            return p["base"]
        return code

    def choose_template(self,*_):
        code=self.kind.currentData()
        if isinstance(code,str) and code.startswith("custom:"):
            p=next((x for x in self._profiles() if "custom:"+x["name"]==code),None)
            if p:
                self.profile_name.setText(p["name"])
                self.profile_disciplines.setText(",".join(p["disciplines"]))
        else:
            self.profile_name.clear()
            self.profile_disciplines.clear()
        self.invalidate()

    def save_profile(self):
        try:
            title=self.profile_name.text().strip()
            if not title or len(title)>80:raise ValueError("نام الگو لازم است")
            code=self._base()
            if code not in TEMPLATES:raise ValueError("الگوی پایه نامعتبر")
            ds=self._disciplines() or list(TEMPLATES[code]["disciplines"])
            profiles=[p for p in self._profiles() if p["name"]!=title]
            if len(profiles)>=30:raise ValueError("حداکثر ۳۰ الگو")
            profiles.append({"name":title,"base":code,"disciplines":ds})
            self.settings.setValue("e3/custom",json.dumps(profiles,ensure_ascii=False))
            self.settings.sync()
            key="custom:"+title
            if self.kind.findData(key)<0:self.kind.addItem("شخصی: "+title,key)
            self.kind.setCurrentIndex(self.kind.findData(key))
            self.invalidate()
            self.status.setText("الگو محلی ذخیره شد؛ پروژه‌ای ایجاد نشد.")
            return True
        except (ValueError,TypeError) as exc:
            self.status.setText("ذخیره الگو انجام نشد: "+str(exc))
            return False

    def delete_profile(self):
        code=self.kind.currentData()
        if not isinstance(code,str) or not code.startswith("custom:"):return False
        profiles=self._profiles()
        filtered=[p for p in profiles if "custom:"+p["name"]!=code]
        if len(filtered)==len(profiles):return False
        self.settings.setValue("e3/custom",json.dumps(filtered,ensure_ascii=False))
        self.settings.sync()
        self.kind.removeItem(self.kind.currentIndex());self.kind.setCurrentIndex(0)
        self.invalidate()
        self.status.setText("الگوی شخصی حذف شد؛ هیچ پروژه‌ای تغییر نکرد.")
        return True

    def args(self):
        names=self.floor_names.text().strip()
        return {
            "project_id":self.project_id.text().strip(),
            "name":self.name.text().strip(),
            "floor_count":self.floors.value(),
            "floor_names": [x.strip() for x in names.replace(",", "،").split("،")] if names else None,
            "disciplines":self._disciplines(),
        }

    def invalidate(self,*_):
        self.preview_data=None
        self.create_button.setEnabled(False)
        self.summary.clear()
        self.status.setText("ورودی تغییر کرده؛ پیش‌نمایش تازه لازم است.")

    def preview(self):
        self.invalidate()
        try:
            self.preview_data=self.service.preview_project_start(self._base(),**self.args())
            p=self.preview_data
            lines=[
                "الگو: "+p["template_title"], "نام: "+p["name"],
                "شناسه: "+p["project_id"],
                "طبقات صریح: "+str(len(p["floors"])),
                "رشته‌ها (کدهای معتبر سامانه): "+", ".join(p["disciplines"]),
                "چک‌لیست اولیه پیشنهادی (تأیید اجرایی نشده):",
                *["• "+x for x in p["checklist"]],
                "طبقات: "+", ".join(x["name"] for x in p["floors"]),
                "متره/BOQ/قیمت/هندسه: ایجاد نمی‌شود.",
            ]
            self.summary.setPlainText("\n".join(lines))
            self.create_button.setEnabled(True)
            self.status.setText("پیش‌نمایش فقط‌خواندنی آماده است؛ ایجاد نیازمند کلیک صریح است.")
            return p
        except Exception as exc:
            self.status.setText("پیش‌نمایش معتبر نیست: "+str(exc))
            return None

    def create(self):
        if self.preview_data is None:
            self.status.setText("ابتدا پیش‌نمایش معتبر ایجاد کنید.")
            return None
        try:
            fresh=self.service.preview_project_start(self._base(),**self.args())
            if fresh!=self.preview_data:
                raise RuntimeError("ورودی‌ها از پیش‌نمایش تغییر کرده‌اند.")
            saved=self.service.create_project_from_template(self._base(),**self.args())
            self.created_project_id=saved["id"]
            self.status.setText("پروژه ساختاری بدون متره یا قیمت ایجاد شد.")
            if self.on_created:self.on_created(saved["id"])
            self.accept()
            return saved
        except Exception as exc:
            self.invalidate()
            self.status.setText("پروژه ثبت نشد: "+str(exc))
            return None
