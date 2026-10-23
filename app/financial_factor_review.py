"""Explicit evidence review for the existing sequential estimate engine."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QFormLayout,QLineEdit,QPushButton,QLabel,QFileDialog


class FactorReviewDialog(QDialog):
    def __init__(self, service, project_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle('بازبینی مدرک ضرایب برآورد')
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.service, self.project_id = service, project_id
        self.digest = service.store.current_digest(project_id)
        form = QFormLayout(self)
        self.inputs = {}
        for name, label in [('FactorEvidencePath','فایل JSON مدرک نسخه‌دار'),('FactorEvidenceSHA256','SHA-256 مدرک'),('FactorAuthor','ثبت‌کننده'),('FactorReviewer','بازبین مستقل')]:
            entry=QLineEdit();entry.setObjectName(name);self.inputs[name]=entry;form.addRow(label,entry)
        choose=QPushButton('انتخاب مدرک');choose.clicked.connect(self.choose);form.addRow(choose)
        note=QLabel('مدرک باید سال، واحد پولی، تاریخ اثر، نسخه و فهرست مرتب ضرایب با مبنای sequential_compound داشته باشد. هیچ ضریبی حدس زده نمی‌شود.');note.setWordWrap(True);form.addRow(note)
        approve=QPushButton('تأیید و ثبت مدرک ضرایب');approve.setObjectName('ApproveFactors');approve.clicked.connect(self.approve);form.addRow(approve)
        self.status=QLabel('در انتظار مدرک و تأیید مستقل');self.status.setObjectName('FactorReviewStatus');self.status.setWordWrap(True);form.addRow(self.status)

    def choose(self):
        path=QFileDialog.getOpenFileName(self,'مدرک ضرایب','','JSON (*.json)')[0]
        if path:self.inputs['FactorEvidencePath'].setText(path)

    def approve(self):
        try:
            text=lambda key:self.inputs[key].text().strip()
            self.service.review_project_factors(self.project_id,text('FactorEvidencePath'),sha256=text('FactorEvidenceSHA256'),author=text('FactorAuthor'),reviewer=text('FactorReviewer'),expected_digest=self.digest)
            self.digest=self.service.store.current_digest(self.project_id)
            self.status.setText('مدرک ضرایب ثبت شد؛ محاسبه از مسیر برآورد موجود انجام می‌شود.')
        except (ValueError,RuntimeError,OSError,KeyError,TypeError) as exc:
            self.status.setText('مدرک یا درخواست نامعتبر: '+str(exc))
