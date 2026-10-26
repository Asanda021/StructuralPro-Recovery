"""E3 Windows RTL project-start dialog; preview and explicit atomic create."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,QVBoxLayout,QFormLayout,QLineEdit,QComboBox,QSpinBox,
    QLabel,QPlainTextEdit,QHBoxLayout,QPushButton
)
from core.projects.start_templates import TEMPLATES


class ProjectStartWizard(QDialog):
    def __init__(self, service, *, parent=None, on_created=None):
        super().__init__(parent)
        self.service=service
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
        self.project_id=QLineEdit();self.project_id.setObjectName("E3ProjectId")
        self.name=QLineEdit();self.name.setObjectName("E3ProjectName")
        self.floors=QSpinBox();self.floors.setObjectName("E3FloorCount")
        self.floors.setRange(0,1000);self.floors.setValue(0)
        self.floor_names=QLineEdit();self.floor_names.setObjectName("E3FloorNames")
        self.floor_names.setPlaceholderText("اختیاری: نام هر طبقه با «،» جدا شود")
        for label,widget in (
            ("قالب ساختار",self.kind),("شناسه یکتای پروژه",self.project_id),
            ("نام واقعی پروژه",self.name),("تعداد طبقات صریح",self.floors),
            ("نام‌های اختصاصی طبقات",self.floor_names)):
            form.addRow(label,widget)
        self.status=QLabel("برای آغاز، قالب و داده‌های صریح را وارد کنید.")
        self.status.setWordWrap(True);layout.addWidget(self.status)
        self.summary=QPlainTextEdit();self.summary.setReadOnly(True);layout.addWidget(self.summary,1)
        actions=QHBoxLayout();layout.addLayout(actions)
        self.preview_button=QPushButton("پیش‌نمایش بدون ثبت")
        self.preview_button.setObjectName("E3Preview")
        self.create_button=QPushButton("تأیید و ایجاد پروژه")
        self.create_button.setObjectName("E3Create")
        self.create_button.setEnabled(False)
        self.cancel_button=QPushButton("انصراف")
        for w in (self.preview_button,self.create_button,self.cancel_button):actions.addWidget(w)
        for item in (self.project_id,self.name,self.floor_names):item.textChanged.connect(self.invalidate)
        self.floors.valueChanged.connect(self.invalidate)
        self.kind.currentIndexChanged.connect(self.invalidate)
        self.preview_button.clicked.connect(self.preview)
        self.create_button.clicked.connect(self.create)
        self.cancel_button.clicked.connect(self.reject)

    def args(self):
        names=self.floor_names.text().strip()
        return {
            "project_id":self.project_id.text().strip(),
            "name":self.name.text().strip(),
            "floor_count":self.floors.value(),
            "floor_names": [x.strip() for x in names.replace(",", "،").split("،")] if names else None,
        }

    def invalidate(self,*_):
        self.preview_data=None
        self.create_button.setEnabled(False)
        self.summary.clear()
        self.status.setText("ورودی تغییر کرده؛ پیش‌نمایش تازه لازم است.")

    def preview(self):
        self.invalidate()
        try:
            self.preview_data=self.service.preview_project_start(self.kind.currentData(),**self.args())
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
            fresh=self.service.preview_project_start(self.kind.currentData(),**self.args())
            if fresh!=self.preview_data:
                raise RuntimeError("ورودی‌ها از پیش‌نمایش تغییر کرده‌اند.")
            saved=self.service.create_project_from_template(self.kind.currentData(),**self.args())
            self.created_project_id=saved["id"]
            self.status.setText("پروژه ساختاری بدون متره یا قیمت ایجاد شد.")
            if self.on_created:self.on_created(saved["id"])
            self.accept()
            return saved
        except Exception as exc:
            self.invalidate()
            self.status.setText("پروژه ثبت نشد: "+str(exc))
            return None
